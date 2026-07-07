from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from hermes.tools import personal_ai_os_telegram_capture


class HermesPersonalAIOSCaptureTest(unittest.TestCase):
    def test_plans_capture_without_executing_task_creator(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            event_path = Path(temp_dir) / "events.jsonl"

            result = json.loads(
                personal_ai_os_telegram_capture.personal_ai_os_telegram_capture(
                    message="todo: Купить лампочки",
                    source_message_id="telegram-1",
                    event_store_path=str(event_path),
                )
            )

        self.assertEqual(result["event"]["status"], "planned")
        self.assertTrue(result["should_execute_action"])
        self.assertIsNone(result["execution_event"])
        self.assertEqual(result["confirmation_text"], "Task is ready to create.")

    def test_blocks_execution_without_server_flag(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            event_path = Path(temp_dir) / "events.jsonl"

            result = json.loads(
                personal_ai_os_telegram_capture.personal_ai_os_telegram_capture(
                    message="todo: Купить лампочки",
                    source_message_id="telegram-2",
                    execute=True,
                    event_store_path=str(event_path),
                )
            )

        self.assertEqual(
            result,
            {
                "error": (
                    "execution is disabled; set "
                    "PERSONAL_AI_OS_CAPTURE_EXECUTE_ENABLED=1 on the server to allow writes"
                )
            },
        )

    def test_executes_task_capture_with_explicit_allow_execute(self) -> None:
        calls = []

        def fake_task_creator(**kwargs) -> str:
            calls.append(kwargs)
            return json.dumps(
                {
                    "success": True,
                    "id": "notion-page-1",
                    "url": "https://notion.so/notion-page-1",
                }
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            event_path = Path(temp_dir) / "events.jsonl"

            result = json.loads(
                personal_ai_os_telegram_capture.personal_ai_os_telegram_capture(
                    message="todo: Купить лампочки",
                    source_message_id="telegram-2",
                    execute=True,
                    event_store_path=str(event_path),
                    task_creator=fake_task_creator,
                    allow_execute=True,
                )
            )

        self.assertEqual(
            calls,
            [{"title": "Купить лампочки", "bucket": "Потом", "comment": None}],
        )
        self.assertEqual(result["event"]["status"], "planned")
        self.assertEqual(result["execution_event"]["status"], "executed")
        self.assertEqual(result["execution_event"]["notion_page_id"], "notion-page-1")
        self.assertFalse(result["should_execute_action"])
        self.assertEqual(result["confirmation_text"], "Task created.")

    def test_returns_validation_errors(self) -> None:
        missing_message = json.loads(
            personal_ai_os_telegram_capture.personal_ai_os_telegram_capture(
                message="",
                source_message_id="telegram-3",
            )
        )
        missing_source_id = json.loads(
            personal_ai_os_telegram_capture.personal_ai_os_telegram_capture(
                message="todo: Купить лампочки",
                source_message_id="",
            )
        )

        self.assertEqual(missing_message, {"error": "message is required"})
        self.assertEqual(missing_source_id, {"error": "source_message_id is required"})

    def test_register_tool_uses_expected_contract(self) -> None:
        class FakeRegistry:
            def __init__(self) -> None:
                self.calls = []

            def register(self, **kwargs) -> None:
                self.calls.append(kwargs)

        registry = FakeRegistry()

        registered = personal_ai_os_telegram_capture.register_tool(registry)

        self.assertTrue(registered)
        self.assertEqual(len(registry.calls), 1)
        self.assertEqual(registry.calls[0]["name"], "personal_ai_os_telegram_capture")
        self.assertEqual(registry.calls[0]["toolset"], "personal_ai_os_capture")
        self.assertEqual(
            registry.calls[0]["schema"],
            personal_ai_os_telegram_capture.PERSONAL_AI_OS_TELEGRAM_CAPTURE_SCHEMA,
        )
        self.assertEqual(registry.calls[0]["emoji"], "📥")


if __name__ == "__main__":
    unittest.main()
