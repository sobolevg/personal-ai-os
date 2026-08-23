"""Mac-side forced-command worker with allowlisted projects and background jobs."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
from typing import Any
import uuid

from .protocol import JOB_ID_RE, WorkerConfig, WorkerRequest, decode_request


DEFAULT_CONFIG = Path("~/.config/personal-ai-os/mac-worker.json").expanduser()
SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*:\s*(?:bearer|basic)\s+)[^\s]+"),
    re.compile(r"(?i)\b((?:api[_-]?key|token|secret|password)\s*[=:]\s*)[^\s,;]+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bgh[opusr]_[A-Za-z0-9_]{20,}\b"),
)


def config_path() -> Path:
    return Path(os.environ.get("PERSONAL_AI_OS_MAC_WORKER_CONFIG", str(DEFAULT_CONFIG))).expanduser()


def handle_request(request: WorkerRequest, config: WorkerConfig) -> dict[str, Any]:
    if request.operation == "doctor":
        return doctor(config)
    if request.operation == "run":
        return start_job(request, config)
    if request.operation == "status":
        return job_status(request.job_id or "", request.tail_chars, config)
    if request.operation == "stop":
        return stop_job(request.job_id or "", config)
    raise ValueError("unsupported operation")


def doctor(config: WorkerConfig) -> dict[str, Any]:
    projects: dict[str, str] = {}
    project_errors: dict[str, str] = {}
    for alias in sorted(config.projects):
        try:
            projects[alias] = str(config.project_path(alias))
        except ValueError as error:
            project_errors[alias] = str(error)
    return {
        "success": not project_errors,
        "projects": sorted(projects),
        "project_errors": project_errors,
        "agents": {
            "codex": _agent_status("codex", config.codex_binary),
            "claude": _agent_status("claude", config.claude_binary),
        },
        "jobs_dir": str(config.jobs_dir),
    }


def start_job(request: WorkerRequest, config: WorkerConfig) -> dict[str, Any]:
    if request.project is None or request.task is None:
        raise ValueError("run requires project and task")
    project_path = config.project_path(request.project)
    binary = config.codex_binary if request.agent == "codex" else config.claude_binary
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise ValueError(f"{request.agent} CLI is unavailable")
    if not _agent_status(request.agent, binary).get("authenticated"):
        raise ValueError(f"{request.agent} CLI is not authenticated")

    jobs_dir = _prepare_jobs_dir(config.jobs_dir)
    job_id = uuid.uuid4().hex
    job_dir = jobs_dir / job_id
    job_dir.mkdir(mode=0o700)
    request_file = job_dir / "request.json"
    _write_json(
        request_file,
        {
            "job_id": job_id,
            "project": request.project,
            "project_path": str(project_path),
            "task": request.task,
            "agent": request.agent,
            "allow_commit": request.allow_commit,
            "allow_push": request.allow_push,
            "created_at": _now(),
        },
    )
    command = [sys.executable, "-m", "services.mac_worker.worker", "_execute-job", job_id]
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
        env=_sanitized_environment(),
    )
    _write_json(
        job_dir / "process.json",
        {"pid": process.pid, "started_at": _now()},
    )
    return {
        "success": True,
        "job_id": job_id,
        "state": "running",
        "agent": request.agent,
        "project": request.project,
        "policy": {
            "workspace": "allowlisted project only",
            "sandbox": "workspace-write" if request.agent == "codex" else "Claude permission checks",
            "commit": request.allow_commit,
            "push": request.allow_push,
        },
    }


def job_status(job_id: str, tail_chars: int, config: WorkerConfig) -> dict[str, Any]:
    job_dir = _job_dir(job_id, config)
    request = _read_json(job_dir / "request.json")
    process = _read_json(job_dir / "process.json")
    result_path = job_dir / "result.json"
    stop_path = job_dir / "stop.json"

    if result_path.exists():
        result = _read_json(result_path)
        state = "succeeded" if result.get("exit_code") == 0 else "failed"
    elif stop_path.exists() and not _pid_running(int(process["pid"])):
        result = _read_json(stop_path)
        state = "stopped"
    elif _pid_running(int(process["pid"])):
        result = {}
        state = "running"
    else:
        result = {}
        state = "failed"

    log_tail = ""
    log_path = job_dir / "agent.log"
    if tail_chars and log_path.exists():
        log_tail = redact_log(_read_tail(log_path, tail_chars))
    return {
        "success": True,
        "job_id": job_id,
        "state": state,
        "agent": request["agent"],
        "project": request["project"],
        "created_at": request["created_at"],
        "finished_at": result.get("finished_at") or result.get("stopped_at"),
        "exit_code": result.get("exit_code"),
        "log_tail": log_tail,
    }


def stop_job(job_id: str, config: WorkerConfig) -> dict[str, Any]:
    status = job_status(job_id, 0, config)
    if status["state"] != "running":
        return {"success": True, "job_id": job_id, "state": status["state"], "already_finished": True}
    process = _read_json(_job_dir(job_id, config) / "process.json")
    pid = int(process["pid"])
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    stopped_at = _now()
    _write_json(_job_dir(job_id, config) / "stop.json", {"stopped_at": stopped_at})
    return {"success": True, "job_id": job_id, "state": "stopping", "stopped_at": stopped_at}


def execute_job(job_id: str, config: WorkerConfig) -> int:
    job_dir = _job_dir(job_id, config)
    request = _read_json(job_dir / "request.json")
    project_path = config.project_path(str(request["project"]))
    if str(project_path) != request["project_path"]:
        raise ValueError("allowlisted project path changed after job creation")
    command = build_agent_command(request, config, project_path)
    prompt = build_agent_prompt(request, project_path)
    env = _sanitized_environment()
    env.update(_git_policy_environment(job_dir, request))

    log_path = job_dir / "agent.log"
    with log_path.open("ab", buffering=0) as log_file:
        os.chmod(log_path, 0o600)
        completed = subprocess.run(
            command,
            input=prompt.encode("utf-8"),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            cwd=project_path,
            env=env,
            check=False,
        )
    _write_json(
        job_dir / "result.json",
        {"exit_code": completed.returncode, "finished_at": _now()},
    )
    return completed.returncode


def build_agent_command(request: dict[str, Any], config: WorkerConfig, project_path: Path) -> list[str]:
    if request["agent"] == "codex":
        network_access = "true" if request.get("allow_push") else "false"
        return [
            str(config.codex_binary),
            "--ask-for-approval",
            "never",
            "exec",
            "--sandbox",
            "workspace-write",
            "--cd",
            str(project_path),
            "--ephemeral",
            "--ignore-user-config",
            "--json",
            "-c",
            f"sandbox_workspace_write.network_access={network_access}",
            "-",
        ]
    if request["agent"] == "claude":
        return [
            str(config.claude_binary),
            "--print",
            "--output-format",
            "stream-json",
            "--verbose",
            "--permission-mode",
            "dontAsk",
            "--tools",
            "Read,Edit,Write,Glob,Grep",
            "--no-session-persistence",
        ]
    raise ValueError("unsupported agent")


def build_agent_prompt(request: dict[str, Any], project_path: Path) -> str:
    git_policy = "Commit and push are forbidden."
    if request.get("allow_push"):
        git_policy = "Commit and push were explicitly authorized for this job."
    elif request.get("allow_commit"):
        git_policy = "A local commit was explicitly authorized; push is forbidden."
    return (
        "You are running a remotely delegated task on the user's Mac.\n"
        f"The only authorized project is: {project_path}\n"
        "Do not read or write outside that project. Do not reveal credentials, tokens, "
        "environment values, keychain data, or file contents that appear secret.\n"
        f"{git_policy}\n"
        "Respect existing project instructions. Finish with a concise summary and tests run.\n\n"
        "User task:\n"
        f"{request['task']}\n"
    )


def redact_log(value: str) -> str:
    result = value
    for pattern in SECRET_PATTERNS:
        if pattern.groups:
            result = pattern.sub(lambda match: match.group(1) + "[REDACTED]", result)
        else:
            result = pattern.sub("[REDACTED]", result)
    return result


def serve_ssh(original_command: str, config: WorkerConfig) -> dict[str, Any]:
    parts = original_command.strip().split()
    if len(parts) != 2 or parts[0] != "mac-worker":
        raise ValueError("only the mac-worker RPC command is allowed")
    request = decode_request(parts[1], max_task_chars=config.max_task_chars)
    return handle_request(request, config)


def _git_policy_environment(job_dir: Path, request: dict[str, Any]) -> dict[str, str]:
    hooks_dir = job_dir / "git-hooks"
    hooks_dir.mkdir(mode=0o700, exist_ok=True)
    blocked = ["pre-push"]
    if not request.get("allow_commit"):
        blocked.extend(["pre-commit", "pre-merge-commit"])
    for name in blocked:
        hook = hooks_dir / name
        hook.write_text("#!/bin/sh\necho 'git operation blocked by mac-worker policy' >&2\nexit 78\n", encoding="utf-8")
        hook.chmod(0o700)
    return {
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "core.hooksPath",
        "GIT_CONFIG_VALUE_0": str(hooks_dir),
    }


def _sanitized_environment() -> dict[str, str]:
    allowed = ("HOME", "PATH", "USER", "LOGNAME", "SHELL", "TMPDIR", "LANG", "LC_ALL", "CODEX_HOME")
    result = {key: os.environ[key] for key in allowed if key in os.environ}
    result["PYTHONPATH"] = os.environ.get("PYTHONPATH", "")
    return result


def _binary_status(binary: Path, args: list[str]) -> dict[str, Any]:
    if not binary.is_file() or not os.access(binary, os.X_OK):
        return {"installed": False}
    try:
        completed = subprocess.run(
            [str(binary), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
            env=_sanitized_environment(),
        )
    except (OSError, subprocess.SubprocessError):
        return {"installed": True, "healthy": False}
    version = (completed.stdout or completed.stderr).strip().splitlines()
    return {
        "installed": True,
        "healthy": completed.returncode == 0,
        "version": redact_log(version[0])[:200] if version else None,
    }


def _agent_status(agent: str, binary: Path) -> dict[str, Any]:
    status = _binary_status(binary, ["--version"])
    if not status.get("installed"):
        status["authenticated"] = False
        return status
    try:
        if agent == "codex":
            completed = subprocess.run(
                [str(binary), "login", "status"],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
                env=_sanitized_environment(),
            )
            output = f"{completed.stdout}\n{completed.stderr}".lower()
            authenticated = completed.returncode == 0 and "logged in" in output
        else:
            completed = subprocess.run(
                [str(binary), "auth", "status", "--json"],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
                env=_sanitized_environment(),
            )
            auth = json.loads(completed.stdout) if completed.stdout.strip() else {}
            authenticated = completed.returncode == 0 and auth.get("loggedIn") is True
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        authenticated = False
    status["authenticated"] = authenticated
    return status


def _prepare_jobs_dir(path: Path) -> Path:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)
    return path


def _job_dir(job_id: str, config: WorkerConfig) -> Path:
    if not JOB_ID_RE.fullmatch(job_id):
        raise ValueError("job_id has an invalid format")
    path = config.jobs_dir / job_id
    if not path.is_dir():
        raise ValueError("job_id was not found")
    return path


def _write_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"invalid job state: {path.name}")
    return value


def _read_tail(path: Path, limit: int) -> str:
    with path.open("rb") as stream:
        stream.seek(0, os.SEEK_END)
        size = stream.tell()
        stream.seek(max(0, size - limit * 4))
        return stream.read().decode("utf-8", errors="replace")[-limit:]


def _pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        config = WorkerConfig.load(config_path())
        if args and args[0] == "_execute-job":
            if len(args) != 2:
                raise ValueError("_execute-job requires job_id")
            return execute_job(args[1], config)
        if args == ["serve-ssh"]:
            result = serve_ssh(os.environ.get("SSH_ORIGINAL_COMMAND", ""), config)
        elif len(args) == 1:
            request = decode_request(args[0], max_task_chars=config.max_task_chars)
            result = handle_request(request, config)
        else:
            raise ValueError("expected serve-ssh or one request token")
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
