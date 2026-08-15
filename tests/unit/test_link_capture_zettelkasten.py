from __future__ import annotations

import json
import unittest

from services.link_capture.classification import (
    ZETTELKASTEN_SYSTEM_PROMPT,
    build_zettelkasten_user_prompt,
)
from services.link_capture.models import (
    Action,
    Actionability,
    ContentClassification,
    ContentEnrichment,
    NormalizedContent,
    SourcePlatform,
    TranscriptResult,
)
from services.link_capture.notion import build_zettelkasten_page_payload


SOURCE_URL = (
    "https://www.instagram.com/reel/DcBzxM4IFLl/"
    "?igsh=OGk4MzVnbW9vams3&igsi=OGk4MzVnbW9vams3"
)
CANONICAL_URL = "https://www.instagram.com/reel/DcBzxM4IFLl/"


def reverse_step_up_classification() -> ContentClassification:
    return ContentClassification(
        title="Reverse Step-Up: контроль колена и асимметрии",
        summary=(
            "Reverse Step-Up — одностороннее упражнение, которое тренирует "
            "контролируемое движение колена и отдельно нагружает каждую ногу."
        ),
        topics=("здоровье коленей", "силовые упражнения"),
        content_type="exercise",
        action=Action.TRY,
        actionability=Actionability.HIGH,
        why_relevant=(
            "Может улучшить контроль колена и выявить разницу между сторонами, "
            "не позволяя сильной ноге компенсировать слабую."
        ),
        suggested_area="Здоровье",
        suggested_project=None,
        reusable_knowledge=True,
    )


class ZettelkastenNotionPayloadTest(unittest.TestCase):
    def test_page_contains_only_distilled_idea_and_visible_original_link(self) -> None:
        raw_transcript = "RAW TRANSCRIPT MUST NEVER ENTER NOTION " * 20
        content = NormalizedContent.captured(
            SOURCE_URL,
            SourcePlatform.INSTAGRAM,
            saved_at="2026-08-16T09:00:00Z",
        ).enrich(
            ContentEnrichment(
                canonical_url=CANONICAL_URL,
                author="Дима Юрлов | фитнес-тренер",
                author_url="https://www.instagram.com/yurlov.move/",
                text=raw_transcript,
                media_url="https://cdninstagram.example/video.mp4",
            )
        )

        payload = build_zettelkasten_page_payload(
            "zettelkasten-database-id",
            content,
            reverse_step_up_classification(),
        )
        serialized = json.dumps(payload, ensure_ascii=False)

        self.assertNotIn("RAW TRANSCRIPT", serialized)
        self.assertNotIn("cdninstagram.example", serialized)
        self.assertEqual(
            payload["properties"]["Original URL"]["url"], SOURCE_URL
        )
        self.assertEqual(
            payload["properties"]["Canonical URL"]["url"], CANONICAL_URL
        )
        self.assertEqual(
            payload["children"][0]["paragraph"]["rich_text"][0]["text"][
                "link"
            ]["url"],
            SOURCE_URL,
        )
        self.assertIn("Reverse Step-Up", serialized)
        self.assertIn("Чем полезно", serialized)

    def test_page_survives_when_extraction_has_no_metadata(self) -> None:
        content = NormalizedContent.captured(
            SOURCE_URL,
            SourcePlatform.INSTAGRAM,
            saved_at="2026-08-16T09:00:00Z",
        )

        payload = build_zettelkasten_page_payload(
            "zettelkasten-database-id",
            content,
            reverse_step_up_classification(),
        )

        self.assertEqual(
            payload["properties"]["Original URL"]["url"], SOURCE_URL
        )
        self.assertNotIn("Canonical URL", payload["properties"])
        self.assertNotIn("Author", payload["properties"])

    def test_database_id_is_required(self) -> None:
        content = NormalizedContent.captured(
            SOURCE_URL,
            SourcePlatform.INSTAGRAM,
            saved_at="2026-08-16T09:00:00Z",
        )

        with self.assertRaises(ValueError):
            build_zettelkasten_page_payload(
                " ", content, reverse_step_up_classification()
            )


class ZettelkastenPromptTest(unittest.TestCase):
    def test_prompt_requests_atomic_json_without_source_url_field(self) -> None:
        content = NormalizedContent.captured(
            SOURCE_URL,
            SourcePlatform.INSTAGRAM,
            saved_at="2026-08-16T09:00:00Z",
        )
        transcript = TranscriptResult(
            text="Упражнение называется Reverse Step-Up.",
            language="ru",
            duration_seconds=65.0,
            segments=(),
            provider="test",
        )

        user_prompt = build_zettelkasten_user_prompt(content, transcript)

        self.assertIn("Reverse Step-Up", user_prompt)
        self.assertIn("одну главную идею", ZETTELKASTEN_SYSTEM_PROMPT)
        self.assertIn("Не добавляй source_url", ZETTELKASTEN_SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
