from __future__ import annotations

import unittest

from services.link_capture.models import (
    Action,
    Actionability,
    ContentClassification,
    ContentEnrichment,
    NormalizedContent,
    SourcePlatform,
    SourceUrlIntegrityError,
)


SOURCE_URL = "https://x.com/example/status/123?ref=telegram#original"
SAVED_AT = "2026-08-14T12:30:00Z"


class NormalizedContentTest(unittest.TestCase):
    def test_minimal_capture_survives_without_metadata(self) -> None:
        content = NormalizedContent.captured(
            source_url=SOURCE_URL,
            platform=SourcePlatform.X,
            saved_at=SAVED_AT,
        )

        self.assertEqual(content.source_url, SOURCE_URL)
        self.assertEqual(content.saved_at, SAVED_AT)
        self.assertEqual(content.author, "")
        self.assertIsNone(content.canonical_url)

    def test_enrichment_cannot_replace_original_source(self) -> None:
        content = NormalizedContent.captured(
            source_url=SOURCE_URL,
            platform=SourcePlatform.X,
            saved_at=SAVED_AT,
        )
        enrichment = ContentEnrichment(
            canonical_url="https://x.com/example/status/123",
            author="Example",
            author_url="https://x.com/example",
            title="An example post",
            text="Post body",
            media_type="post",
            thumbnail_url="https://cdn.example.com/thumbnail.jpg",
            media_url="https://cdn.example.com/video.mp4",
        )

        enriched = content.enrich(enrichment)

        self.assertEqual(enriched.source_url, SOURCE_URL)
        self.assertEqual(enriched.saved_at, SAVED_AT)
        self.assertEqual(enriched.canonical_url, "https://x.com/example/status/123")
        self.assertEqual(enriched.media_url, "https://cdn.example.com/video.mp4")

    def test_mapping_update_rejects_source_url_even_if_metadata_contains_it(self) -> None:
        content = NormalizedContent.captured(
            source_url=SOURCE_URL,
            platform=SourcePlatform.X,
            saved_at=SAVED_AT,
        )

        with self.assertRaises(SourceUrlIntegrityError):
            content.with_updates(
                {"source_url": "https://cdn.example.com/not-the-original.mp4"}
            )

    def test_mapping_update_rejects_saved_at_rewrite(self) -> None:
        content = NormalizedContent.captured(
            source_url=SOURCE_URL,
            platform=SourcePlatform.X,
            saved_at=SAVED_AT,
        )

        with self.assertRaises(SourceUrlIntegrityError):
            content.with_updates({"saved_at": "2027-01-01T00:00:00Z"})

    def test_serialized_model_uses_json_schema_values(self) -> None:
        content = NormalizedContent.captured(
            source_url=SOURCE_URL,
            platform=SourcePlatform.X,
            saved_at=SAVED_AT,
        )

        payload = content.to_dict()

        self.assertEqual(payload["source_url"], SOURCE_URL)
        self.assertEqual(payload["platform"], "x")
        self.assertEqual(payload["saved_at"], SAVED_AT)

    def test_source_url_must_be_absolute_http_url(self) -> None:
        with self.assertRaises(ValueError):
            NormalizedContent.captured(
                source_url="x.com/example/status/123",
                platform=SourcePlatform.X,
                saved_at=SAVED_AT,
            )


class ContentClassificationTest(unittest.TestCase):
    def test_strict_classification_round_trip(self) -> None:
        payload = {
            "title": "Build a personal search index",
            "summary": "A practical indexing guide.",
            "topics": ["search", "personal-ai"],
            "content_type": "article",
            "action": "try",
            "actionability": "high",
            "why_relevant": "Useful for Hermes retrieval.",
            "suggested_area": "Personal AI OS",
            "suggested_project": None,
            "reusable_knowledge": True,
        }

        result = ContentClassification.from_dict(payload)

        self.assertEqual(result.action, Action.TRY)
        self.assertEqual(result.actionability, Actionability.HIGH)
        self.assertEqual(result.to_dict(), payload)

    def test_classification_rejects_unknown_fields(self) -> None:
        payload = {
            "title": "Title",
            "summary": "Summary",
            "topics": [],
            "content_type": "article",
            "action": "read",
            "actionability": "low",
            "why_relevant": "",
            "suggested_area": None,
            "suggested_project": None,
            "reusable_knowledge": False,
            "source_url": "https://example.com/should-not-come-from-the-llm",
        }

        with self.assertRaises(ValueError):
            ContentClassification.from_dict(payload)

    def test_classification_rejects_invalid_action(self) -> None:
        payload = {
            "title": "Title",
            "summary": "Summary",
            "topics": [],
            "content_type": "article",
            "action": "bookmark",
            "actionability": "low",
            "why_relevant": "",
            "suggested_area": None,
            "suggested_project": None,
            "reusable_knowledge": False,
        }

        with self.assertRaises(ValueError):
            ContentClassification.from_dict(payload)

    def test_direct_construction_also_requires_enum_values(self) -> None:
        with self.assertRaises(TypeError):
            ContentClassification(
                title="Title",
                summary="Summary",
                topics=(),
                content_type="article",
                action="read",  # type: ignore[arg-type]
                actionability=Actionability.LOW,
                why_relevant="",
                suggested_area=None,
                suggested_project=None,
                reusable_knowledge=False,
            )


if __name__ == "__main__":
    unittest.main()
