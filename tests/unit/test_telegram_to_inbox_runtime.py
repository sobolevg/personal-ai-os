from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from integrations.automations.telegram_to_inbox import plan_telegram_capture
from integrations.events.event_log import JsonlEventStore

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "automations"
    / "telegram_to_inbox_runtime.expected.json"
)


class TelegramToInboxRuntimeTest(unittest.TestCase):
    def test_high_confidence_task_is_ready_after_event_record(self) -> None:
        expected = _load_expected("task")

        with tempfile.TemporaryDirectory() as tmp_dir:
            event_store_path = Path(tmp_dir) / "events.jsonl"
            result = plan_telegram_capture(
                message="todo: renew passport",
                source_message_id="tg-runtime-1",
                event_store_path=event_store_path,
            )

            self.assertEqual(result.dispatch_plan.route, expected["route"])
            self.assertEqual(result.dispatch_plan.action, expected["action"])
            self.assertEqual(result.dispatch_plan.write_policy, expected["write_policy"])
            self.assertEqual(result.event.status, expected["event_status"])
            self.assertEqual(result.should_execute_action, expected["should_execute_action"])
            self.assertEqual(result.confirmation_text, expected["confirmation_text"])
            self.assertEqual(len(JsonlEventStore(event_store_path).iter_events()), 1)

    def test_duplicate_message_does_not_execute_action_twice(self) -> None:
        expected = _load_expected("duplicate")

        with tempfile.TemporaryDirectory() as tmp_dir:
            event_store_path = Path(tmp_dir) / "events.jsonl"
            plan_telegram_capture(
                message="todo: renew passport",
                source_message_id="tg-runtime-1",
                event_store_path=event_store_path,
            )
            duplicate = plan_telegram_capture(
                message="todo: renew passport",
                source_message_id="tg-runtime-1",
                event_store_path=event_store_path,
            )

            self.assertEqual(duplicate.event.status, expected["event_status"])
            self.assertEqual(duplicate.should_execute_action, expected["should_execute_action"])
            self.assertEqual(duplicate.confirmation_text, expected["confirmation_text"])
            self.assertEqual(len(JsonlEventStore(event_store_path).iter_events()), 1)

    def test_resource_capture_stays_draft_only(self) -> None:
        expected = _load_expected("draft")

        with tempfile.TemporaryDirectory() as tmp_dir:
            event_store_path = Path(tmp_dir) / "events.jsonl"
            result = plan_telegram_capture(
                message="https://example.com/article",
                source_message_id="tg-runtime-2",
                event_store_path=event_store_path,
            )

            self.assertEqual(result.dispatch_plan.route, expected["route"])
            self.assertEqual(result.dispatch_plan.action, expected["action"])
            self.assertEqual(result.dispatch_plan.write_policy, expected["write_policy"])
            self.assertEqual(result.event.status, expected["event_status"])
            self.assertEqual(result.should_execute_action, expected["should_execute_action"])
            self.assertEqual(result.confirmation_text, expected["confirmation_text"])


def _load_expected(name: str) -> dict[str, object]:
    with FIXTURE_PATH.open(encoding="utf-8") as json_file:
        cases = json.load(json_file)

    for case in cases:
        if case["name"] == name:
            return case["expected"]

    raise AssertionError(f"missing fixture case: {name}")
