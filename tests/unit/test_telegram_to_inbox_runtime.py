from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from integrations.automations.telegram_to_inbox import (
    execute_telegram_capture,
    plan_telegram_capture,
    resolve_event_store_path,
)
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

    def test_knowledge_capture_records_agent_draft(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            event_store_path = Path(tmp_dir) / "events.jsonl"
            result = plan_telegram_capture(
                message="подумать над personal ai os как системой агентов вокруг Hermes",
                source_message_id="tg-runtime-knowledge-1",
                event_store_path=event_store_path,
            )
            events = JsonlEventStore(event_store_path).iter_events()

            self.assertEqual(result.dispatch_plan.route, "knowledge")
            self.assertEqual(result.dispatch_plan.action, "knowledge_candidate")
            self.assertFalse(result.should_execute_action)
            self.assertEqual(result.confirmation_text, "Captured as a draft candidate.")
            self.assertEqual(events[0]["metadata"]["agent"], "knowledge_curator")
            self.assertEqual(
                events[0]["metadata"]["knowledge_candidate"]["target"],
                "notion.knowledge",
            )
            self.assertIn(
                "Personal AI OS",
                events[0]["metadata"]["knowledge_candidate"]["links_to_existing_topics"],
            )

    def test_research_capture_records_research_agent_draft(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            event_store_path = Path(tmp_dir) / "events.jsonl"
            result = plan_telegram_capture(
                message="купить белые кроссовки Nike размер 43 с доставкой домой",
                source_message_id="tg-runtime-research-1",
                event_store_path=event_store_path,
            )
            events = JsonlEventStore(event_store_path).iter_events()

            self.assertEqual(result.dispatch_plan.route, "research")
            self.assertEqual(result.dispatch_plan.action, "research_brief")
            self.assertFalse(result.should_execute_action)
            self.assertEqual(result.confirmation_text, "Captured as a draft candidate.")
            self.assertEqual(events[0]["metadata"]["agent"], "research_agent")
            research_brief = events[0]["metadata"]["research_brief"]
            self.assertEqual(research_brief["target"], "notion.research")
            self.assertEqual(research_brief["research_type"], "purchase")
            self.assertIn("budget", research_brief["missing_inputs"])

    def test_execute_high_confidence_task_records_executed_event(self) -> None:
        expected = _load_expected("executed")
        calls = []

        def fake_task_creator(title, bucket, comment):
            calls.append({"title": title, "bucket": bucket, "comment": comment})
            return json.dumps(
                {
                    "success": True,
                    "id": expected["notion_page_id"],
                    "url": "https://notion.so/page-id-456",
                    "title": title,
                    "bucket": bucket,
                    "comment": comment,
                }
            )

        with tempfile.TemporaryDirectory() as tmp_dir:
            event_store_path = Path(tmp_dir) / "events.jsonl"
            result = execute_telegram_capture(
                message="todo: renew passport",
                source_message_id="tg-runtime-3",
                event_store_path=event_store_path,
                task_creator=fake_task_creator,
            )
            events = JsonlEventStore(event_store_path).iter_events()

            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0]["title"], "renew passport")
            self.assertIsNotNone(result.execution_event)
            self.assertEqual(result.execution_event.status, expected["execution_status"])
            self.assertEqual(result.execution_event.notion_page_id, expected["notion_page_id"])
            self.assertEqual(result.should_execute_action, expected["should_execute_action"])
            self.assertEqual(result.confirmation_text, expected["confirmation_text"])
            self.assertEqual(len(events), expected["stored_events"])

    def test_execute_duplicate_does_not_call_task_creator(self) -> None:
        calls = []

        def fake_task_creator(title, bucket, comment):
            calls.append(title)
            return json.dumps({"success": True, "id": "page-id-456"})

        with tempfile.TemporaryDirectory() as tmp_dir:
            event_store_path = Path(tmp_dir) / "events.jsonl"
            execute_telegram_capture(
                message="todo: renew passport",
                source_message_id="tg-runtime-4",
                event_store_path=event_store_path,
                task_creator=fake_task_creator,
            )
            duplicate = execute_telegram_capture(
                message="todo: renew passport",
                source_message_id="tg-runtime-4",
                event_store_path=event_store_path,
                task_creator=fake_task_creator,
            )

            self.assertEqual(len(calls), 1)
            self.assertEqual(duplicate.event.status, "skipped_duplicate")
            self.assertFalse(duplicate.should_execute_action)

    def test_execute_resource_draft_does_not_call_task_creator(self) -> None:
        def fail_task_creator(title, bucket, comment):
            raise AssertionError("task creator should not be called")

        with tempfile.TemporaryDirectory() as tmp_dir:
            result = execute_telegram_capture(
                message="https://example.com/article",
                source_message_id="tg-runtime-5",
                event_store_path=Path(tmp_dir) / "events.jsonl",
                task_creator=fail_task_creator,
            )

            self.assertEqual(result.dispatch_plan.route, "resource")
            self.assertIsNone(result.execution_event)
            self.assertFalse(result.should_execute_action)

    def test_execute_task_records_failed_event_on_creator_error(self) -> None:
        expected = _load_expected("failed")

        def fail_task_creator(title, bucket, comment):
            raise RuntimeError("Notion unavailable")

        with tempfile.TemporaryDirectory() as tmp_dir:
            event_store_path = Path(tmp_dir) / "events.jsonl"
            result = execute_telegram_capture(
                message="todo: renew passport",
                source_message_id="tg-runtime-6",
                event_store_path=event_store_path,
                task_creator=fail_task_creator,
            )
            events = JsonlEventStore(event_store_path).iter_events()

            self.assertIsNotNone(result.execution_event)
            self.assertEqual(result.execution_event.status, expected["execution_status"])
            self.assertEqual(result.confirmation_text, expected["confirmation_text"])
            self.assertEqual(result.should_execute_action, expected["should_execute_action"])
            self.assertEqual(len(events), expected["stored_events"])

    def test_default_event_store_path_uses_env_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            env_path = str(Path(tmp_dir) / "custom-events.jsonl")

            with patch.dict(os.environ, {"PERSONAL_AI_OS_EVENT_LOG_PATH": env_path}):
                self.assertEqual(resolve_event_store_path(), Path(env_path))

    def test_default_event_store_path_uses_hermes_home(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(
                os.environ,
                {"HERMES_HOME": tmp_dir},
                clear=True,
            ):
                self.assertEqual(
                    resolve_event_store_path(),
                    Path(tmp_dir) / "personal-ai-os" / "events" / "events.jsonl",
                )


def _load_expected(name: str) -> dict[str, object]:
    with FIXTURE_PATH.open(encoding="utf-8") as json_file:
        cases = json.load(json_file)

    for case in cases:
        if case["name"] == name:
            return case["expected"]

    raise AssertionError(f"missing fixture case: {name}")
