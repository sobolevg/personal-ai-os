"""Read-only review helpers for the Personal AI OS event log."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from integrations.automations.telegram_to_inbox import resolve_event_store_path
from integrations.events.event_log import JsonlEventStore, VALID_EVENT_STATUSES


@dataclass(frozen=True)
class EventReviewItem:
    event_id: str
    idempotency_key: str
    created_at: str
    status: str
    action: str
    source_platform: str
    source_message_id: str
    route: str | None
    target: str | None
    write_policy: str | None
    normalized_text: str | None
    needs_confirmation: bool | None
    confidence: float | None
    notion_page_id: str | None
    error: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EventReviewSummary:
    event_count: int
    pending_count: int
    status_counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def read_event_log(path: str | Path | None = None) -> list[dict[str, Any]]:
    return JsonlEventStore(resolve_event_store_path(path)).iter_events()


def summarize_events(events: Iterable[dict[str, Any]]) -> EventReviewSummary:
    materialized_events = list(events)
    status_counts = {status: 0 for status in VALID_EVENT_STATUSES}
    for event in materialized_events:
        status = str(event.get("status") or "")
        if status not in status_counts:
            status_counts[status] = 0
        status_counts[status] += 1

    pending_count = len(list_pending_events(materialized_events))
    return EventReviewSummary(
        event_count=len(materialized_events),
        pending_count=pending_count,
        status_counts=status_counts,
    )


def list_pending_events(
    events: Iterable[dict[str, Any]],
    limit: int | None = None,
) -> list[EventReviewItem]:
    latest_events = latest_event_by_idempotency_key(events)
    pending = [
        _review_item(event)
        for event in latest_events.values()
        if event.get("status") == "planned"
    ]
    pending.sort(key=lambda item: item.created_at)
    if limit is not None:
        return pending[:limit]
    return pending


def latest_event_by_idempotency_key(
    events: Iterable[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for event in events:
        idempotency_key = str(event.get("idempotency_key") or "")
        if not idempotency_key:
            continue
        if event.get("status") == "skipped_duplicate":
            continue
        latest[idempotency_key] = event
    return latest


def format_summary(summary: EventReviewSummary) -> str:
    status_lines = [
        f"  {status}: {count}"
        for status, count in sorted(summary.status_counts.items())
        if count
    ]
    if not status_lines:
        status_lines = ["  none: 0"]

    return "\n".join(
        [
            "Personal AI OS event log summary",
            "",
            f"Events:  {summary.event_count}",
            f"Pending: {summary.pending_count}",
            "Statuses:",
            *status_lines,
        ]
    )


def format_pending_events(items: Iterable[EventReviewItem]) -> str:
    materialized_items = list(items)
    if not materialized_items:
        return "No pending planned events."

    lines = ["Pending planned events", ""]
    for index, item in enumerate(materialized_items, 1):
        lines.extend(
            [
                f"{index}. {item.normalized_text or '(no text)'}",
                f"   key: {item.idempotency_key}",
                f"   source: {item.source_platform}:{item.source_message_id}",
                f"   route/action: {item.route or '-'} / {item.action}",
                f"   created: {item.created_at}",
            ]
        )
    return "\n".join(lines)


def _review_item(event: dict[str, Any]) -> EventReviewItem:
    metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
    return EventReviewItem(
        event_id=str(event.get("event_id") or ""),
        idempotency_key=str(event.get("idempotency_key") or ""),
        created_at=str(event.get("created_at") or ""),
        status=str(event.get("status") or ""),
        action=str(event.get("action") or ""),
        source_platform=str(event.get("source_platform") or ""),
        source_message_id=str(event.get("source_message_id") or ""),
        route=_string_or_none(event.get("route")),
        target=_string_or_none(event.get("target")),
        write_policy=_string_or_none(event.get("write_policy")),
        normalized_text=_string_or_none(metadata.get("normalized_text")),
        needs_confirmation=_bool_or_none(metadata.get("needs_confirmation")),
        confidence=_float_or_none(metadata.get("confidence")),
        notion_page_id=_string_or_none(event.get("notion_page_id")),
        error=_string_or_none(event.get("error")),
    )


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _bool_or_none(value: object) -> bool | None:
    if value is None:
        return None
    return bool(value)


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Review Personal AI OS event log")
    parser.add_argument("command", choices=("summary", "pending"))
    parser.add_argument("--path", default=None, help="Override event log path")
    parser.add_argument("--limit", type=int, default=None, help="Limit pending rows")
    parser.add_argument("--json", action="store_true", help="Print JSON")
    args = parser.parse_args(argv)

    events = read_event_log(args.path)
    if args.command == "summary":
        summary = summarize_events(events)
        if args.json:
            print(json.dumps(summary.to_dict(), ensure_ascii=False, sort_keys=True))
        else:
            print(format_summary(summary))
        return 0

    pending = list_pending_events(events, limit=args.limit)
    if args.json:
        print(
            json.dumps(
                [item.to_dict() for item in pending],
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    else:
        print(format_pending_events(pending))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
