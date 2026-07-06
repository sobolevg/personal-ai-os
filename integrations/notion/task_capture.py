"""Build Notion task payloads for the current personal task contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

TASK_DATABASE_ID = "176a0a22-1593-8122-94e7-cdb420698046"
DEFAULT_BUCKET = "Потом"
VALID_BUCKETS = ("Сегодня", "На неделе", "Потом", "На выходных")

TITLE_PROPERTY = "Обезьянопонятная задача"
BUCKET_PROPERTY = "Когда начать"
STATUS_PROPERTY = "Статус"
DONE_PROPERTY = "Сделано?"
COMMENT_PROPERTY = "Комментарий"
DEFAULT_STATUS = "В плане"


@dataclass(frozen=True)
class TaskCaptureInput:
    title: str
    bucket: str = DEFAULT_BUCKET
    comment: str | None = None


class TaskCaptureValidationError(ValueError):
    """Raised when task capture input cannot produce a Notion payload."""


def validate_task_capture_input(
    title: str | None,
    bucket: str | None = None,
    comment: str | None = None,
) -> TaskCaptureInput:
    normalized_title = (title or "").strip()
    normalized_bucket = (bucket or DEFAULT_BUCKET).strip()
    normalized_comment = (comment or "").strip() or None

    if not normalized_title:
        raise TaskCaptureValidationError("title is required")
    if normalized_bucket not in VALID_BUCKETS:
        raise TaskCaptureValidationError(
            f"bucket must be one of: {', '.join(sorted(VALID_BUCKETS))}"
        )

    return TaskCaptureInput(
        title=normalized_title,
        bucket=normalized_bucket,
        comment=normalized_comment,
    )


def build_task_create_payload(
    title: str | None,
    bucket: str | None = None,
    comment: str | None = None,
) -> dict[str, Any]:
    task_input = validate_task_capture_input(
        title=title,
        bucket=bucket,
        comment=comment,
    )

    properties: dict[str, Any] = {
        TITLE_PROPERTY: {
            "title": [
                {
                    "type": "text",
                    "text": {"content": task_input.title},
                }
            ]
        },
        BUCKET_PROPERTY: {"select": {"name": task_input.bucket}},
        STATUS_PROPERTY: {"select": {"name": DEFAULT_STATUS}},
        DONE_PROPERTY: {"checkbox": False},
    }

    if task_input.comment:
        properties[COMMENT_PROPERTY] = {
            "rich_text": [
                {
                    "type": "text",
                    "text": {"content": task_input.comment},
                }
            ]
        }

    return {
        "parent": {"database_id": TASK_DATABASE_ID},
        "properties": properties,
    }
