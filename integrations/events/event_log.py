"""Append-only JSONL event log with idempotency helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from integrations.routing.capture_dispatch import CaptureDispatchPlan

VALID_EVENT_STATUSES = ("planned", "executed", "failed", "skipped_duplicate")


class EventLogError(ValueError):
    """Raised when an event cannot be recorded safely."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class PersonalAIEvent:
    event_id: str
    idempotency_key: str
    status: str
    action: str
    source_platform: str
    source_message_id: str
    route: str | None = None
    target: str | None = None
    write_policy: str | None = None
    created_at: str = field(default_factory=_utc_now)
    notion_page_id: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_idempotency_key(
    source_platform: str | None,
    source_message_id: str | None,
    action: str | None,
) -> str:
    normalized_parts = [
        _required_part(source_platform, "source_platform"),
        _required_part(source_message_id, "source_message_id"),
        _required_part(action, "action"),
    ]
    raw_key = "|".join(normalized_parts)
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def plan_event_from_dispatch(plan: CaptureDispatchPlan) -> PersonalAIEvent:
    source_platform = _required_part(plan.source_platform, "source_platform")
    source_message_id = _required_part(plan.source_message_id, "source_message_id")
    idempotency_key = build_idempotency_key(
        source_platform=source_platform,
        source_message_id=source_message_id,
        action=plan.action,
    )

    return PersonalAIEvent(
        event_id=str(uuid4()),
        idempotency_key=idempotency_key,
        status="planned",
        action=plan.action,
        source_platform=source_platform,
        source_message_id=source_message_id,
        route=plan.route,
        target=plan.target,
        write_policy=plan.write_policy,
        metadata={
            "confidence": plan.confidence,
            "needs_confirmation": plan.needs_confirmation,
            "normalized_text": plan.normalized_text,
        },
    )


class JsonlEventStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def record_event(self, event: PersonalAIEvent) -> PersonalAIEvent:
        _validate_event(event)
        if self.has_idempotency_key(event.idempotency_key):
            return PersonalAIEvent(
                event_id=str(uuid4()),
                idempotency_key=event.idempotency_key,
                status="skipped_duplicate",
                action=event.action,
                source_platform=event.source_platform,
                source_message_id=event.source_message_id,
                route=event.route,
                target=event.target,
                write_policy=event.write_policy,
                metadata={"duplicate_of": event.idempotency_key},
            )

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as event_file:
            event_file.write(
                json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True)
            )
            event_file.write("\n")

        return event

    def has_idempotency_key(self, idempotency_key: str) -> bool:
        return any(
            event.get("idempotency_key") == idempotency_key
            for event in self.iter_events()
            if event.get("status") != "skipped_duplicate"
        )

    def iter_events(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []

        events: list[dict[str, Any]] = []
        with self.path.open(encoding="utf-8") as event_file:
            for line in event_file:
                normalized_line = line.strip()
                if normalized_line:
                    events.append(json.loads(normalized_line))
        return events


def _validate_event(event: PersonalAIEvent) -> None:
    if event.status not in VALID_EVENT_STATUSES:
        raise EventLogError(
            f"event status must be one of: {', '.join(VALID_EVENT_STATUSES)}"
        )


def _required_part(value: str | None, name: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise EventLogError(f"{name} is required")
    return normalized

