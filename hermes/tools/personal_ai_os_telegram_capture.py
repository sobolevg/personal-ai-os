"""Hermes wrapper for Personal AI OS Telegram capture."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable

from integrations.automations.telegram_to_inbox import (
    execute_telegram_capture,
    plan_telegram_capture,
)

try:  # pragma: no cover - exercised inside Hermes runtime, not local unit tests.
    from tools.registry import registry as hermes_registry
    from tools.registry import tool_error as hermes_tool_error
except Exception:  # pragma: no cover - local repo does not vendor Hermes runtime.
    hermes_registry = None
    hermes_tool_error = None


TaskCreator = Callable[..., str]


def tool_error(message: str) -> str:
    if hermes_tool_error is not None:
        return hermes_tool_error(message)
    return json.dumps({"error": message}, ensure_ascii=False)


def personal_ai_os_telegram_capture(
    message: str,
    source_message_id: str,
    execute: bool = False,
    event_store_path: str | None = None,
    source_platform: str = "telegram",
    *,
    task_creator: TaskCreator | None = None,
    allow_execute: bool | None = None,
) -> str:
    """Plan or execute Telegram capture through the repo-owned runtime path."""
    if not message or not message.strip():
        return tool_error("message is required")
    if not source_message_id or not source_message_id.strip():
        return tool_error("source_message_id is required")

    try:
        resolved_event_path = Path(event_store_path) if event_store_path else None
        if execute:
            if not _execution_enabled(allow_execute):
                return tool_error(
                    "execution is disabled; set "
                    "PERSONAL_AI_OS_CAPTURE_EXECUTE_ENABLED=1 on the server to allow writes"
                )
            result = execute_telegram_capture(
                message=message,
                source_message_id=source_message_id,
                event_store_path=resolved_event_path,
                source_platform=source_platform,
                task_creator=task_creator,
            )
        else:
            result = plan_telegram_capture(
                message=message,
                source_message_id=source_message_id,
                event_store_path=resolved_event_path,
                source_platform=source_platform,
            )
    except Exception as error:
        return tool_error(str(error))

    return json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True)


def _execution_enabled(allow_execute: bool | None = None) -> bool:
    if allow_execute is not None:
        return allow_execute
    return os.environ.get("PERSONAL_AI_OS_CAPTURE_EXECUTE_ENABLED") == "1"


PERSONAL_AI_OS_TELEGRAM_CAPTURE_SCHEMA = {
    "name": "personal_ai_os_telegram_capture",
    "description": (
        "Route a Telegram message through Evgenii's Personal AI OS capture path. "
        "By default this only plans and logs capture intent. Set execute=true only "
        "when the Telegram message is ready for the runtime automation path."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "Raw Telegram message text to capture.",
            },
            "source_message_id": {
                "type": "string",
                "description": (
                    "Stable Telegram message id used for idempotency. "
                    "Do not invent a new id for retries."
                ),
            },
            "execute": {
                "type": "boolean",
                "description": (
                    "When false, only plan/log. When true, execution is still blocked "
                    "unless the server enables PERSONAL_AI_OS_CAPTURE_EXECUTE_ENABLED=1."
                ),
                "default": False,
            },
            "event_store_path": {
                "type": "string",
                "description": "Optional JSONL event log override for tests or maintenance.",
            },
            "source_platform": {
                "type": "string",
                "description": "Source platform for idempotency. Defaults to telegram.",
                "default": "telegram",
            },
        },
        "required": ["message", "source_message_id"],
    },
}


def register_tool(registry: Any | None = None) -> bool:
    target_registry = registry or hermes_registry
    if target_registry is None:
        return False

    target_registry.register(
        name="personal_ai_os_telegram_capture",
        toolset="personal_ai_os_capture",
        schema=PERSONAL_AI_OS_TELEGRAM_CAPTURE_SCHEMA,
        handler=lambda args, **kw: personal_ai_os_telegram_capture(
            message=args.get("message", ""),
            source_message_id=args.get("source_message_id", ""),
            execute=bool(args.get("execute", False)),
            event_store_path=args.get("event_store_path"),
            source_platform=args.get("source_platform", "telegram"),
        ),
        emoji="📥",
    )
    return True


register_tool()
