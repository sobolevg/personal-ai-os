"""Hermes wrapper for personal Notion task capture."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

from integrations.notion.task_capture import (
    DEFAULT_BUCKET,
    TaskCaptureValidationError,
    build_task_create_payload,
    validate_task_capture_input,
)

NOTION_API_URL = "https://api.notion.com/v1/pages"
NOTION_VERSION = "2022-06-28"

try:  # pragma: no cover - exercised inside Hermes runtime, not local unit tests.
    from tools.registry import registry as hermes_registry
    from tools.registry import tool_error as hermes_tool_error
except Exception:  # pragma: no cover - local repo does not vendor Hermes runtime.
    hermes_registry = None
    hermes_tool_error = None


def tool_error(message: str) -> str:
    if hermes_tool_error is not None:
        return hermes_tool_error(message)
    return json.dumps({"error": message}, ensure_ascii=False)


def load_notion_token(env: dict[str, str] | None = None) -> str | None:
    source_env = env or os.environ
    token = source_env.get("NOTION_TOKEN") or source_env.get("NOTION_API_KEY")
    if token:
        return token.strip().strip('"').strip("'")

    env_path = Path(source_env.get("HERMES_HOME", "/root/.hermes")) / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() in {"NOTION_TOKEN", "NOTION_API_KEY"}:
                return value.strip().strip('"').strip("'")
    return None


def post_notion_page(
    payload: dict[str, Any],
    token: str,
    urlopen: Callable[..., Any] = urllib.request.urlopen,
) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        NOTION_API_URL,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        },
    )

    try:
        with urlopen(request, timeout=25) as response:
            body = json.loads(response.read().decode("utf-8"))
            body["_http_status"] = response.status
            return body
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw)
        except Exception:
            body = {"message": raw}
        body["_http_status"] = error.code
        raise RuntimeError(json.dumps(body, ensure_ascii=False)) from error


def notion_task_create(
    title: str,
    bucket: str = DEFAULT_BUCKET,
    comment: str | None = None,
    *,
    token: str | None = None,
    urlopen: Callable[..., Any] = urllib.request.urlopen,
    allow_create: bool | None = None,
) -> str:
    if not _task_creation_enabled(allow_create):
        return tool_error(
            "notion_task_create is disabled; use personal_ai_os_telegram_capture "
            "with execute=false unless PERSONAL_AI_OS_NOTION_TASK_CREATE_ENABLED=1 "
            "is set on the server"
        )

    try:
        task_input = validate_task_capture_input(
            title=title,
            bucket=bucket,
            comment=comment,
        )
        payload = build_task_create_payload(
            title=task_input.title,
            bucket=task_input.bucket,
            comment=task_input.comment,
        )
    except TaskCaptureValidationError as error:
        return tool_error(str(error))

    notion_token = token or load_notion_token()
    if not notion_token:
        return tool_error("NOTION_TOKEN or NOTION_API_KEY is not configured")

    try:
        page = post_notion_page(payload, notion_token, urlopen=urlopen)
    except Exception as error:
        return tool_error(f"Notion create failed: {error}")

    result = {
        "success": True,
        "id": page.get("id"),
        "url": page.get("url"),
        "title": task_input.title,
        "bucket": task_input.bucket,
        "comment": task_input.comment,
    }
    return json.dumps(result, ensure_ascii=False)


def _task_creation_enabled(allow_create: bool | None = None) -> bool:
    if allow_create is not None:
        return allow_create
    return os.environ.get("PERSONAL_AI_OS_NOTION_TASK_CREATE_ENABLED") == "1"


NOTION_TASK_CREATE_SCHEMA = {
    "name": "notion_task_create",
    "description": (
        "Create a personal task in Evgenii's Notion database 'Мои задачи'. "
        "Use this when Evgenii says in Russian or English: add a task, record a task, "
        "dictates a task by voice, 'добавь задачу', 'запиши задачу', 'на потом', "
        "'на сегодня', 'на выходные'. This is NOT the assistant planning todo. "
        "Input is simple: title plus bucket. The tool handles the Notion API payload."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Task title, e.g. 'Уменьшить количество уведомлений в телефоне'.",
            },
            "bucket": {
                "type": "string",
                "enum": ["Сегодня", "На неделе", "Потом", "На выходных"],
                "description": "When to start. Default to 'Потом' if unclear.",
                "default": "Потом",
            },
            "comment": {
                "type": "string",
                "description": "Optional extra context for the Notion 'Комментарий' field.",
            },
        },
        "required": ["title"],
    },
}


def register_tool(registry: Any | None = None) -> bool:
    target_registry = registry or hermes_registry
    if target_registry is None:
        return False

    target_registry.register(
        name="notion_task_create",
        toolset="notion_task",
        schema=NOTION_TASK_CREATE_SCHEMA,
        handler=lambda args, **kw: notion_task_create(
            title=args.get("title", ""),
            bucket=args.get("bucket", DEFAULT_BUCKET),
            comment=args.get("comment"),
        ),
        emoji="📝",
    )
    return True


register_tool()
