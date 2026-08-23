"""Hermes tools for restricted coding-agent delegation to the user's Mac."""

from __future__ import annotations

import json
from typing import Any, Callable

from services.mac_worker.client import call_mac_worker
from services.mac_worker.protocol import WorkerRequest

try:  # pragma: no cover - exercised inside Hermes runtime.
    from tools.registry import registry as hermes_registry
    from tools.registry import tool_error as hermes_tool_error
except Exception:  # pragma: no cover - local repo does not vendor Hermes runtime.
    hermes_registry = None
    hermes_tool_error = None


WorkerCaller = Callable[[WorkerRequest], dict[str, Any]]


def tool_error(message: str) -> str:
    if hermes_tool_error is not None:
        return hermes_tool_error(message)
    return json.dumps({"error": message}, ensure_ascii=False, sort_keys=True)


def mac_worker_run(
    project: str,
    task: str,
    agent: str = "codex",
    allow_commit: bool = False,
    allow_push: bool = False,
    *,
    caller: WorkerCaller = call_mac_worker,
) -> str:
    """Start a background agent job in one server-allowlisted Mac project."""
    try:
        request = WorkerRequest.from_dict(
            {
                "operation": "run",
                "project": project,
                "task": task,
                "agent": agent,
                "allow_commit": allow_commit,
                "allow_push": allow_push,
            }
        )
        result = caller(request)
    except Exception as error:
        return tool_error(str(error))
    return json.dumps(result, ensure_ascii=False, sort_keys=True)


def mac_worker_status(
    job_id: str,
    tail_chars: int = 4_000,
    *,
    caller: WorkerCaller = call_mac_worker,
) -> str:
    """Return job state and a redacted log tail."""
    try:
        request = WorkerRequest.from_dict(
            {"operation": "status", "job_id": job_id, "tail_chars": tail_chars}
        )
        result = caller(request)
    except Exception as error:
        return tool_error(str(error))
    return json.dumps(result, ensure_ascii=False, sort_keys=True)


def mac_worker_stop(
    job_id: str,
    *,
    caller: WorkerCaller = call_mac_worker,
) -> str:
    """Request termination of one background job."""
    try:
        request = WorkerRequest.from_dict({"operation": "stop", "job_id": job_id})
        result = caller(request)
    except Exception as error:
        return tool_error(str(error))
    return json.dumps(result, ensure_ascii=False, sort_keys=True)


def mac_worker_doctor(*, caller: WorkerCaller = call_mac_worker) -> str:
    """Check worker projects and agent binaries without starting a task."""
    try:
        result = caller(WorkerRequest.from_dict({"operation": "doctor"}))
    except Exception as error:
        return tool_error(str(error))
    return json.dumps(result, ensure_ascii=False, sort_keys=True)


MAC_WORKER_RUN_SCHEMA = {
    "name": "mac_worker_run",
    "description": (
        "Delegate a background coding task to Codex or Claude Code on Evgenii's Mac. "
        "The project is an alias from a server-owned allowlist, never a filesystem path. "
        "Commit and push are denied unless the user explicitly asks for them."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "project": {
                "type": "string",
                "description": "Configured project alias, for example personal-ai-os.",
            },
            "task": {"type": "string", "maxLength": 20000},
            "agent": {"type": "string", "enum": ["codex", "claude"], "default": "codex"},
            "allow_commit": {
                "type": "boolean",
                "default": False,
                "description": "True only when the user explicitly requested a local commit.",
            },
            "allow_push": {
                "type": "boolean",
                "default": False,
                "description": "True only when the user explicitly requested push; requires allow_commit.",
            },
        },
        "required": ["project", "task"],
        "additionalProperties": False,
    },
}

MAC_WORKER_STATUS_SCHEMA = {
    "name": "mac_worker_status",
    "description": "Read one Mac worker job state and a server-redacted log tail.",
    "parameters": {
        "type": "object",
        "properties": {
            "job_id": {"type": "string", "pattern": "^[0-9a-f]{32}$"},
            "tail_chars": {"type": "integer", "minimum": 0, "maximum": 12000, "default": 4000},
        },
        "required": ["job_id"],
        "additionalProperties": False,
    },
}

MAC_WORKER_STOP_SCHEMA = {
    "name": "mac_worker_stop",
    "description": "Stop one Mac worker background job by id.",
    "parameters": {
        "type": "object",
        "properties": {"job_id": {"type": "string", "pattern": "^[0-9a-f]{32}$"}},
        "required": ["job_id"],
        "additionalProperties": False,
    },
}

MAC_WORKER_DOCTOR_SCHEMA = {
    "name": "mac_worker_doctor",
    "description": "Check Mac worker connectivity, allowlisted projects, and installed agent CLIs.",
    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
}


def register_tools(registry: Any | None = None) -> bool:
    target = registry or hermes_registry
    if target is None:
        return False
    registrations = (
        ("mac_worker_run", MAC_WORKER_RUN_SCHEMA, lambda args: mac_worker_run(
            project=args.get("project", ""),
            task=args.get("task", ""),
            agent=args.get("agent", "codex"),
            allow_commit=bool(args.get("allow_commit", False)),
            allow_push=bool(args.get("allow_push", False)),
        ), "💻"),
        ("mac_worker_status", MAC_WORKER_STATUS_SCHEMA, lambda args: mac_worker_status(
            job_id=args.get("job_id", ""), tail_chars=args.get("tail_chars", 4000)
        ), "📟"),
        ("mac_worker_stop", MAC_WORKER_STOP_SCHEMA, lambda args: mac_worker_stop(
            job_id=args.get("job_id", "")
        ), "🛑"),
        ("mac_worker_doctor", MAC_WORKER_DOCTOR_SCHEMA, lambda args: mac_worker_doctor(), "🩺"),
    )
    for name, schema, handler, emoji in registrations:
        target.register(
            name=name,
            toolset="mac_worker",
            schema=schema,
            handler=lambda args, _handler=handler, **kw: _handler(args),
            emoji=emoji,
            max_result_size_chars=15_000,
        )
    return True


register_tools()
