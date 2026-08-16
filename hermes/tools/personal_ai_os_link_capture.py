"""Hermes tools for prepare -> model distillation -> Notion link capture."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Callable

from hermes.tools.notion_task_create import load_notion_token, post_notion_page
from services.link_capture.capture_state import JsonLinkCaptureStore
from services.link_capture.models import ContentClassification, SourcePlatform
from services.link_capture.notion import build_zettelkasten_page_payload
from services.link_capture.url_detection import detect_urls
from services.link_capture.workflow import (
    DEFAULT_CAPTURE_ROOT,
    DEFAULT_MEDIA_WORK_DIR,
    PreparedLinkCapture,
    prepare_instagram_capture,
)

try:  # pragma: no cover - exercised inside Hermes runtime.
    from tools.registry import registry as hermes_registry
    from tools.registry import tool_error as hermes_tool_error
except Exception:  # pragma: no cover - local repo does not vendor Hermes runtime.
    hermes_registry = None
    hermes_tool_error = None


PageCreator = Callable[[dict[str, Any], str], dict[str, Any]]
PrepareRunner = Callable[..., Any]


def tool_error(message: str) -> str:
    if hermes_tool_error is not None:
        return hermes_tool_error(message)
    return json.dumps({"error": message}, ensure_ascii=False)


def personal_ai_os_link_prepare(
    message: str,
    source_message_id: str,
    *,
    source_platform: str = "telegram",
    state_dir: Path = DEFAULT_CAPTURE_ROOT,
    media_work_dir: Path = DEFAULT_MEDIA_WORK_DIR,
    prepare_runner: PrepareRunner = prepare_instagram_capture,
) -> str:
    """Prepare source + transcript for classification by the current Hermes model."""
    if not message or not message.strip():
        return tool_error("message is required")
    if not source_message_id or not source_message_id.strip():
        return tool_error("source_message_id is required")

    detected = _unique_instagram_urls(message)
    if not detected:
        return tool_error("an Instagram URL is required")
    if len(detected) > 1:
        return tool_error("only one Instagram URL can be captured at a time")

    store = JsonLinkCaptureStore(state_dir)
    try:
        result: PreparedLinkCapture = asyncio.run(
            prepare_runner(
                source_url=detected[0],
                source_message_id=source_message_id,
                source_platform=source_platform,
                store=store,
                media_work_dir=media_work_dir,
            )
        )
    except Exception as error:
        return tool_error(f"link preparation failed: {error}")
    return json.dumps(result.to_model_dict(), ensure_ascii=False, sort_keys=True)


def personal_ai_os_link_save(
    capture_id: str,
    title: str,
    summary: str,
    topics: list[str],
    content_type: str,
    action: str,
    actionability: str,
    why_relevant: str,
    reusable_knowledge: bool,
    suggested_area: str | None = None,
    suggested_project: str | None = None,
    *,
    state_dir: Path = DEFAULT_CAPTURE_ROOT,
    token: str | None = None,
    database_id: str | None = None,
    allow_create: bool | None = None,
    page_creator: PageCreator = post_notion_page,
) -> str:
    """Save a distilled note using server-owned source identity."""
    if not _creation_enabled(allow_create):
        return tool_error(
            "link capture save is disabled; set "
            "PERSONAL_AI_OS_LINK_CAPTURE_EXECUTE_ENABLED=1 on the server"
        )

    store = JsonLinkCaptureStore(state_dir)
    try:
        capture = store.load(capture_id)
    except Exception as error:
        return tool_error(str(error))
    if capture is None:
        return tool_error("capture_id was not prepared")
    if capture.status == "saved":
        return json.dumps(
            {
                "success": True,
                "duplicate": True,
                "capture_id": capture.capture_id,
                "url": capture.notion_page_url,
            },
            ensure_ascii=False,
            sort_keys=True,
        )

    try:
        classification = ContentClassification.from_dict(
            {
                "title": title,
                "summary": summary,
                "topics": topics,
                "content_type": content_type,
                "action": action,
                "actionability": actionability,
                "why_relevant": why_relevant,
                "suggested_area": suggested_area,
                "suggested_project": suggested_project,
                "reusable_knowledge": reusable_knowledge,
            }
        )
    except Exception as error:
        return tool_error(f"invalid Hermes classification: {error}")

    notion_token = token or load_notion_token()
    resolved_database_id = (
        database_id or os.environ.get("NOTION_DATABASE_ID", "")
    ).strip()
    if not notion_token:
        return tool_error("NOTION_TOKEN or NOTION_API_KEY is not configured")
    if not resolved_database_id:
        return tool_error("NOTION_DATABASE_ID is not configured")

    payload = build_zettelkasten_page_payload(
        resolved_database_id,
        capture.content,
        classification,
    )
    try:
        page = page_creator(payload, notion_token)
    except Exception as error:
        return tool_error(f"Notion create failed: {error}")
    page_url = page.get("url")
    if not isinstance(page_url, str) or not page_url:
        return tool_error("Notion create response omitted page URL")

    saved = capture.mark_saved(
        str(page.get("id")) if page.get("id") is not None else None,
        page_url,
    )
    store.save(saved)
    return json.dumps(
        {
            "success": True,
            "duplicate": False,
            "capture_id": capture.capture_id,
            "url": page_url,
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _unique_instagram_urls(message: str) -> list[str]:
    result: list[str] = []
    for detected in detect_urls(message):
        if detected.platform is not SourcePlatform.INSTAGRAM:
            continue
        if detected.source_url not in result:
            result.append(detected.source_url)
    return result


def _creation_enabled(allow_create: bool | None = None) -> bool:
    if allow_create is not None:
        return allow_create
    return os.environ.get("PERSONAL_AI_OS_LINK_CAPTURE_EXECUTE_ENABLED") == "1"


PERSONAL_AI_OS_LINK_PREPARE_SCHEMA = {
    "name": "personal_ai_os_link_prepare",
    "description": (
        "Prepare one Instagram link shared in Telegram. This preserves the exact "
        "original URL, extracts metadata, sends prepared audio to PLAUD, and returns "
        "a transcript for analysis by your current Hermes model. Call this before "
        "personal_ai_os_link_save."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "Raw Telegram message containing the Instagram URL.",
            },
            "source_message_id": {
                "type": "string",
                "description": "Stable Telegram message id. Never invent a new retry id.",
            },
            "source_platform": {
                "type": "string",
                "default": "telegram",
            },
        },
        "required": ["message", "source_message_id"],
    },
}


PERSONAL_AI_OS_LINK_SAVE_SCHEMA = {
    "name": "personal_ai_os_link_save",
    "description": (
        "Save the concise Zettelkasten classification produced by the current Hermes "
        "model after personal_ai_os_link_prepare. The original URL is loaded from "
        "server-owned capture state and cannot be supplied or changed here."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "capture_id": {"type": "string"},
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "topics": {"type": "array", "items": {"type": "string"}},
            "content_type": {"type": "string"},
            "action": {
                "type": "string",
                "enum": ["read", "watch", "try", "buy", "do", "none"],
            },
            "actionability": {
                "type": "string",
                "enum": ["low", "medium", "high"],
            },
            "why_relevant": {"type": "string"},
            "suggested_area": {"type": ["string", "null"]},
            "suggested_project": {"type": ["string", "null"]},
            "reusable_knowledge": {"type": "boolean"},
        },
        "required": [
            "capture_id",
            "title",
            "summary",
            "topics",
            "content_type",
            "action",
            "actionability",
            "why_relevant",
            "reusable_knowledge",
        ],
        "additionalProperties": False,
    },
}


def register_tools(registry: Any | None = None) -> bool:
    target_registry = registry or hermes_registry
    if target_registry is None:
        return False
    target_registry.register(
        name="personal_ai_os_link_prepare",
        toolset="personal_ai_os_link_capture",
        schema=PERSONAL_AI_OS_LINK_PREPARE_SCHEMA,
        handler=lambda args, **kw: personal_ai_os_link_prepare(
            message=args.get("message", ""),
            source_message_id=args.get("source_message_id", ""),
            source_platform=args.get("source_platform", "telegram"),
        ),
        emoji="🔗",
        max_result_size_chars=50_000,
    )
    target_registry.register(
        name="personal_ai_os_link_save",
        toolset="personal_ai_os_link_capture",
        schema=PERSONAL_AI_OS_LINK_SAVE_SCHEMA,
        handler=lambda args, **kw: personal_ai_os_link_save(
            capture_id=args.get("capture_id", ""),
            title=args.get("title", ""),
            summary=args.get("summary", ""),
            topics=args.get("topics", []),
            content_type=args.get("content_type", ""),
            action=args.get("action", "none"),
            actionability=args.get("actionability", "low"),
            why_relevant=args.get("why_relevant", ""),
            suggested_area=args.get("suggested_area"),
            suggested_project=args.get("suggested_project"),
            reusable_knowledge=bool(args.get("reusable_knowledge", False)),
        ),
        emoji="🗂️",
    )
    return True


register_tools()
