"""Validated wire protocol shared by the VPS bridge and the Mac worker."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any


PROJECT_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
JOB_ID_RE = re.compile(r"^[0-9a-f]{32}$")
OPERATIONS = frozenset({"doctor", "run", "status", "stop"})
AGENTS = frozenset({"codex", "claude"})
MAX_WIRE_BYTES = 32_768


@dataclass(frozen=True)
class WorkerRequest:
    operation: str
    project: str | None = None
    task: str | None = None
    agent: str = "codex"
    job_id: str | None = None
    tail_chars: int = 4_000
    allow_commit: bool = False
    allow_push: bool = False

    @classmethod
    def from_dict(cls, value: dict[str, Any], *, max_task_chars: int = 20_000) -> "WorkerRequest":
        allowed = {
            "operation",
            "project",
            "task",
            "agent",
            "job_id",
            "tail_chars",
            "allow_commit",
            "allow_push",
        }
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"unsupported request fields: {', '.join(sorted(unknown))}")

        operation = value.get("operation")
        if operation not in OPERATIONS:
            raise ValueError("operation must be doctor, run, status, or stop")

        project = value.get("project")
        task = value.get("task")
        agent = value.get("agent", "codex")
        job_id = value.get("job_id")
        tail_chars = value.get("tail_chars", 4_000)
        allow_commit = value.get("allow_commit", False)
        allow_push = value.get("allow_push", False)

        if agent not in AGENTS:
            raise ValueError("agent must be codex or claude")
        if not isinstance(tail_chars, int) or isinstance(tail_chars, bool):
            raise ValueError("tail_chars must be an integer")
        if not 0 <= tail_chars <= 12_000:
            raise ValueError("tail_chars must be between 0 and 12000")
        if not isinstance(allow_commit, bool) or not isinstance(allow_push, bool):
            raise ValueError("allow_commit and allow_push must be booleans")
        if allow_push and not allow_commit:
            raise ValueError("allow_push requires allow_commit")

        if operation == "run":
            if not isinstance(project, str) or not PROJECT_RE.fullmatch(project):
                raise ValueError("project must be a configured project alias")
            if not isinstance(task, str) or not task.strip():
                raise ValueError("task is required")
            if len(task) > max_task_chars:
                raise ValueError(f"task exceeds {max_task_chars} characters")
            if job_id is not None:
                raise ValueError("run does not accept job_id")
        elif operation in {"status", "stop"}:
            if not isinstance(job_id, str) or not JOB_ID_RE.fullmatch(job_id):
                raise ValueError("job_id has an invalid format")
            if project is not None or task is not None:
                raise ValueError(f"{operation} does not accept project or task")
        else:
            if any(item is not None for item in (project, task, job_id)):
                raise ValueError("doctor does not accept project, task, or job_id")

        return cls(
            operation=operation,
            project=project,
            task=task.strip() if isinstance(task, str) else None,
            agent=agent,
            job_id=job_id,
            tail_chars=tail_chars,
            allow_commit=allow_commit,
            allow_push=allow_push,
        )


@dataclass(frozen=True)
class WorkerConfig:
    projects: dict[str, Path]
    allow_roots: tuple[Path, ...]
    jobs_dir: Path
    codex_binary: Path
    claude_binary: Path
    max_task_chars: int = 20_000

    @classmethod
    def load(cls, path: Path) -> "WorkerConfig":
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"cannot load worker config: {error}") from error
        if not isinstance(value, dict):
            raise ValueError("worker config must be a JSON object")

        allowed = {
            "projects",
            "allow_roots",
            "jobs_dir",
            "codex_binary",
            "claude_binary",
            "max_task_chars",
        }
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"unsupported config fields: {', '.join(sorted(unknown))}")

        raw_projects = value.get("projects")
        raw_roots = value.get("allow_roots")
        if not isinstance(raw_projects, dict) or not raw_projects:
            raise ValueError("projects must be a non-empty object")
        if not isinstance(raw_roots, list) or not raw_roots:
            raise ValueError("allow_roots must be a non-empty array")

        roots = tuple(_absolute_path(item, "allow_roots") for item in raw_roots)
        projects: dict[str, Path] = {}
        for alias, raw_path in raw_projects.items():
            if not isinstance(alias, str) or not PROJECT_RE.fullmatch(alias):
                raise ValueError(f"invalid project alias: {alias!r}")
            project_path = _absolute_path(raw_path, f"project {alias}")
            if not any(_is_relative_to(project_path, root) for root in roots):
                raise ValueError(f"project {alias} is outside allow_roots")
            projects[alias] = project_path

        jobs_dir = _absolute_path(value.get("jobs_dir"), "jobs_dir")
        codex_binary = _absolute_path(value.get("codex_binary"), "codex_binary")
        claude_binary = _absolute_path(value.get("claude_binary"), "claude_binary")
        max_task_chars = value.get("max_task_chars", 20_000)
        if not isinstance(max_task_chars, int) or not 1 <= max_task_chars <= 100_000:
            raise ValueError("max_task_chars must be between 1 and 100000")
        return cls(
            projects=projects,
            allow_roots=roots,
            jobs_dir=jobs_dir,
            codex_binary=codex_binary,
            claude_binary=claude_binary,
            max_task_chars=max_task_chars,
        )

    def project_path(self, alias: str) -> Path:
        try:
            configured = self.projects[alias]
        except KeyError as error:
            raise ValueError(f"project is not allowlisted: {alias}") from error
        resolved = configured.resolve(strict=True)
        if not resolved.is_dir():
            raise ValueError(f"allowlisted project is not a directory: {alias}")
        if not any(_is_relative_to(resolved, root.resolve(strict=True)) for root in self.allow_roots):
            raise ValueError(f"resolved project escaped allow_roots: {alias}")
        return resolved


def encode_request(request: WorkerRequest | dict[str, Any]) -> str:
    value = request.__dict__ if isinstance(request, WorkerRequest) else request
    raw = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(raw) > MAX_WIRE_BYTES:
        raise ValueError("request is too large")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_request(token: str, *, max_task_chars: int = 20_000) -> WorkerRequest:
    if not isinstance(token, str) or not token or len(token) > MAX_WIRE_BYTES * 2:
        raise ValueError("invalid request token")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", token):
        raise ValueError("request token is not base64url")
    try:
        padding = "=" * (-len(token) % 4)
        raw = base64.urlsafe_b64decode(token + padding)
        value = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("request token is invalid") from error
    if len(raw) > MAX_WIRE_BYTES or not isinstance(value, dict):
        raise ValueError("request payload is invalid")
    return WorkerRequest.from_dict(value, max_task_chars=max_task_chars)


def _absolute_path(value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be an absolute path")
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError(f"{label} must be an absolute path")
    return path


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
