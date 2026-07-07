from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from integrations.events.event_log import JsonlEventStore, plan_event_from_dispatch
from integrations.events.event_review import (
    format_pending_events,
    format_summary,
    latest_event_by_idempotency_key,
    list_pending_events,
    read_event_log,
    summarize_events,
)
from integrations.routing.capture_dispatch import build_capture_dispatch_plan


class EventReviewTest(unittest.TestCase):
    def test_planned_event_is_pending(self) -> None:
        event = _planned_event("todo: renew passport", "tg-review-1")

        pending = list_pending_events([event.to_dict()])

        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].normalized_text, "todo: renew passport")
        self.assertEqual(pending[0].status, "planned")
        self.assertEqual(pending[0].source_platform, "telegram")

    def test_executed_outcome_removes_pending_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = JsonlEventStore(Path(tmp_dir) / "events.jsonl")
            planned = store.record_event(_planned_event("todo: renew passport", "tg-review-2"))
            store.record_outcome(
                planned,
                status="executed",
                notion_page_id="page-id-123",
            )

            events = store.iter_events()

        self.assertEqual(list_pending_events(events), [])
        summary = summarize_events(events)
        self.assertEqual(summary.event_count, 2)
        self.assertEqual(summary.pending_count, 0)
        self.assertEqual(summary.status_counts["planned"], 1)
        self.assertEqual(summary.status_counts["executed"], 1)

    def test_failed_outcome_removes_pending_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = JsonlEventStore(Path(tmp_dir) / "events.jsonl")
            planned = store.record_event(_planned_event("todo: renew passport", "tg-review-3"))
            store.record_outcome(planned, status="failed", error="Notion unavailable")

            events = store.iter_events()

        self.assertEqual(list_pending_events(events), [])
        self.assertEqual(summarize_events(events).status_counts["failed"], 1)

    def test_skipped_duplicate_does_not_replace_latest_event(self) -> None:
        planned = _planned_event("todo: renew passport", "tg-review-4")
        duplicate = planned.to_dict()
        duplicate["status"] = "skipped_duplicate"

        latest = latest_event_by_idempotency_key([planned.to_dict(), duplicate])

        self.assertEqual(latest[planned.idempotency_key]["status"], "planned")
        self.assertEqual(len(list_pending_events([planned.to_dict(), duplicate])), 1)

    def test_read_event_log_uses_jsonl_store_and_formats_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            event_path = Path(tmp_dir) / "events.jsonl"
            store = JsonlEventStore(event_path)
            store.record_event(_planned_event("todo: renew passport", "tg-review-5"))

            events = read_event_log(event_path)

        summary_text = format_summary(summarize_events(events))
        pending_text = format_pending_events(list_pending_events(events))
        self.assertIn("Events:  1", summary_text)
        self.assertIn("Pending: 1", summary_text)
        self.assertIn("todo: renew passport", pending_text)
        self.assertIn("route/action: task / notion_task_create", pending_text)


def _planned_event(message: str, source_message_id: str):
    plan = build_capture_dispatch_plan(
        message=message,
        source_platform="telegram",
        source_message_id=source_message_id,
    )
    return plan_event_from_dispatch(plan)
