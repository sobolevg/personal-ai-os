from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from integrations.events.event_log import (
    EventLogError,
    JsonlEventStore,
    build_idempotency_key,
    plan_event_from_dispatch,
)
from integrations.routing.capture_dispatch import build_capture_dispatch_plan

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "events" / "telegram_task_event.expected.json"
)


class EventLogTest(unittest.TestCase):
    def test_event_from_dispatch_matches_expected_core_fields(self) -> None:
        plan = build_capture_dispatch_plan(
            message="todo: renew passport",
            source_platform="telegram",
            source_message_id="tg-event-1",
        )
        event = plan_event_from_dispatch(plan)
        expected = _load_json(FIXTURE_PATH)

        for key, value in expected.items():
            self.assertEqual(event.to_dict()[key], value)

        self.assertEqual(
            event.idempotency_key,
            build_idempotency_key("telegram", "tg-event-1", "notion_task_create"),
        )
        self.assertEqual(event.metadata["normalized_text"], "todo: renew passport")

    def test_jsonl_store_records_once_and_skips_duplicate(self) -> None:
        plan = build_capture_dispatch_plan(
            message="todo: renew passport",
            source_platform="telegram",
            source_message_id="tg-event-1",
        )
        event = plan_event_from_dispatch(plan)

        with tempfile.TemporaryDirectory() as tmp_dir:
            store = JsonlEventStore(Path(tmp_dir) / "events.jsonl")

            first_result = store.record_event(event)
            duplicate_result = store.record_event(event)

            self.assertEqual(first_result.status, "planned")
            self.assertEqual(duplicate_result.status, "skipped_duplicate")
            self.assertEqual(len(store.iter_events()), 1)

    def test_jsonl_store_records_outcome_for_existing_event(self) -> None:
        plan = build_capture_dispatch_plan(
            message="todo: renew passport",
            source_platform="telegram",
            source_message_id="tg-event-2",
        )
        event = plan_event_from_dispatch(plan)

        with tempfile.TemporaryDirectory() as tmp_dir:
            store = JsonlEventStore(Path(tmp_dir) / "events.jsonl")

            planned = store.record_event(event)
            executed = store.record_outcome(
                planned,
                status="executed",
                notion_page_id="page-id-789",
            )

            self.assertEqual(executed.status, "executed")
            self.assertEqual(executed.notion_page_id, "page-id-789")
            self.assertEqual(len(store.iter_events()), 2)

    def test_idempotency_requires_source_and_action(self) -> None:
        with self.assertRaises(EventLogError):
            build_idempotency_key("telegram", "", "notion_task_create")


def _load_json(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8") as json_file:
        return json.load(json_file)
