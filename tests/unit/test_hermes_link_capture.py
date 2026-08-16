from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from hermes.tools.personal_ai_os_link_capture import (
    PERSONAL_AI_OS_LINK_SAVE_SCHEMA,
    personal_ai_os_link_prepare,
    personal_ai_os_link_save,
    register_tools,
)
from services.link_capture.capture_state import (
    JsonLinkCaptureStore,
    StoredLinkCapture,
    capture_id_for,
)
from services.link_capture.models import NormalizedContent, SourcePlatform
from services.link_capture.workflow import PreparedLinkCapture


SOURCE_URL = "https://www.instagram.com/reel/ABC/?igsh=exact"


class HermesLinkCaptureTest(unittest.TestCase):
    def test_prepare_deduplicates_markdown_url_and_returns_transcript(self) -> None:
        calls = []

        async def fake_prepare(**kwargs) -> PreparedLinkCapture:
            calls.append(kwargs)
            capture_id = capture_id_for("telegram", "message-1", SOURCE_URL)
            return PreparedLinkCapture(
                StoredLinkCapture(
                    capture_id=capture_id,
                    source_message_id="message-1",
                    content=NormalizedContent.captured(
                        SOURCE_URL,
                        SourcePlatform.INSTAGRAM,
                        saved_at="2026-08-16T08:00:00Z",
                    ),
                    transcript_text="Reverse Step Up",
                    transcript_provider="plaud_web",
                )
            )

        with TemporaryDirectory() as directory:
            result = json.loads(
                personal_ai_os_link_prepare(
                    message=f"[{SOURCE_URL}]({SOURCE_URL})",
                    source_message_id="message-1",
                    state_dir=Path(directory),
                    prepare_runner=fake_prepare,
                )
            )

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["source_url"], SOURCE_URL)
        self.assertEqual(result["source_url"], SOURCE_URL)
        self.assertEqual(result["transcript"], "Reverse Step Up")

    def test_save_uses_server_owned_original_url_and_is_idempotent(self) -> None:
        pages = []

        def fake_create(payload, token):
            pages.append((payload, token))
            return {"id": "page-1", "url": "https://notion.so/page-1"}

        with TemporaryDirectory() as directory:
            store = JsonLinkCaptureStore(Path(directory))
            capture_id = capture_id_for("telegram", "message-2", SOURCE_URL)
            store.save(
                StoredLinkCapture(
                    capture_id=capture_id,
                    source_message_id="message-2",
                    content=NormalizedContent.captured(
                        SOURCE_URL,
                        SourcePlatform.INSTAGRAM,
                        saved_at="2026-08-16T08:00:00Z",
                    ),
                )
            )
            kwargs = {
                "capture_id": capture_id,
                "title": "Reverse Step-Up для контроля колена",
                "summary": "Одностороннее упражнение для контроля движения колена.",
                "topics": ["колени", "упражнения"],
                "content_type": "exercise",
                "action": "try",
                "actionability": "high",
                "why_relevant": "Может помочь заметить асимметрию между ногами.",
                "reusable_knowledge": True,
                "state_dir": Path(directory),
                "token": "secret",
                "database_id": "database-id",
                "allow_create": True,
                "page_creator": fake_create,
            }

            first = json.loads(personal_ai_os_link_save(**kwargs))
            second = json.loads(personal_ai_os_link_save(**kwargs))

        payload = pages[0][0]
        self.assertEqual(len(pages), 1)
        self.assertEqual(payload["properties"]["Original URL"]["url"], SOURCE_URL)
        self.assertEqual(first["duplicate"], False)
        self.assertEqual(second["duplicate"], True)
        self.assertNotIn(
            "source_url",
            PERSONAL_AI_OS_LINK_SAVE_SCHEMA["parameters"]["properties"],
        )

    def test_save_is_disabled_without_server_flag(self) -> None:
        result = json.loads(
            personal_ai_os_link_save(
                capture_id="0" * 32,
                title="title",
                summary="summary",
                topics=[],
                content_type="note",
                action="none",
                actionability="low",
                why_relevant="why",
                reusable_knowledge=False,
                allow_create=False,
            )
        )

        self.assertIn("disabled", result["error"])

    def test_registers_prepare_and_save_tools(self) -> None:
        class FakeRegistry:
            def __init__(self) -> None:
                self.calls = []

            def register(self, **kwargs) -> None:
                self.calls.append(kwargs)

        registry = FakeRegistry()
        self.assertTrue(register_tools(registry))
        self.assertEqual(
            [call["name"] for call in registry.calls],
            ["personal_ai_os_link_prepare", "personal_ai_os_link_save"],
        )


if __name__ == "__main__":
    unittest.main()
