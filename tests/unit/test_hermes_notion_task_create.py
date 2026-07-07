from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from hermes.tools import notion_task_create


class FakeResponse:
    status = 200

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(
            {
                "id": "page-id-123",
                "url": "https://notion.so/page-id-123",
            }
        ).encode("utf-8")


class HermesNotionTaskCreateTest(unittest.TestCase):
    def test_returns_success_json_after_posting_payload(self) -> None:
        requests = []

        def fake_urlopen(request, timeout):
            requests.append((request, timeout))
            return FakeResponse()

        result = json.loads(
            notion_task_create.notion_task_create(
                title=" Позвонить в банк ",
                bucket="Сегодня",
                comment=" Уточнить лимиты ",
                token="test-token",
                urlopen=fake_urlopen,
                allow_create=True,
            )
        )

        self.assertEqual(
            result,
            {
                "success": True,
                "id": "page-id-123",
                "url": "https://notion.so/page-id-123",
                "title": "Позвонить в банк",
                "bucket": "Сегодня",
                "comment": "Уточнить лимиты",
            },
        )
        self.assertEqual(len(requests), 1)

        request, timeout = requests[0]
        self.assertEqual(timeout, 25)
        self.assertEqual(request.full_url, notion_task_create.NOTION_API_URL)
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.headers["Notion-version"], "2022-06-28")
        self.assertEqual(request.headers["Content-type"], "application/json")

        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["properties"]["Когда начать"]["select"]["name"], "Сегодня")
        self.assertEqual(
            payload["properties"]["Комментарий"]["rich_text"][0]["text"]["content"],
            "Уточнить лимиты",
        )

    def test_returns_validation_error_without_posting(self) -> None:
        def fail_urlopen(*args, **kwargs):
            raise AssertionError("urlopen should not be called")

        result = json.loads(
            notion_task_create.notion_task_create(
                title="",
                bucket="Сегодня",
                token="test-token",
                urlopen=fail_urlopen,
                allow_create=True,
            )
        )

        self.assertEqual(result, {"error": "title is required"})

    def test_returns_missing_token_error_without_posting(self) -> None:
        def fail_urlopen(*args, **kwargs):
            raise AssertionError("urlopen should not be called")

        with patch.object(notion_task_create, "load_notion_token", return_value=None):
            result = json.loads(
                notion_task_create.notion_task_create(
                    title="Купить лампочки",
                    bucket="На выходных",
                    urlopen=fail_urlopen,
                    allow_create=True,
                )
            )

        self.assertEqual(
            result,
            {"error": "NOTION_TOKEN or NOTION_API_KEY is not configured"},
        )

    def test_blocks_creation_without_server_flag(self) -> None:
        def fail_urlopen(*args, **kwargs):
            raise AssertionError("urlopen should not be called")

        result = json.loads(
            notion_task_create.notion_task_create(
                title="Купить лампочки",
                bucket="Сегодня",
                token="test-token",
                urlopen=fail_urlopen,
            )
        )

        self.assertEqual(
            result,
            {
                "error": (
                    "notion_task_create is disabled; use personal_ai_os_telegram_capture "
                    "with execute=false unless PERSONAL_AI_OS_NOTION_TASK_CREATE_ENABLED=1 "
                    "is set on the server"
                )
            },
        )

    def test_register_tool_uses_expected_contract(self) -> None:
        class FakeRegistry:
            def __init__(self) -> None:
                self.calls = []

            def register(self, **kwargs) -> None:
                self.calls.append(kwargs)

        registry = FakeRegistry()

        registered = notion_task_create.register_tool(registry)

        self.assertTrue(registered)
        self.assertEqual(len(registry.calls), 1)
        self.assertEqual(registry.calls[0]["name"], "notion_task_create")
        self.assertEqual(registry.calls[0]["toolset"], "notion_task")
        self.assertEqual(
            registry.calls[0]["schema"],
            notion_task_create.NOTION_TASK_CREATE_SCHEMA,
        )
        self.assertEqual(registry.calls[0]["emoji"], "📝")
