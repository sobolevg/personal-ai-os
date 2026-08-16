from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from services.link_capture.capture_state import (
    JsonLinkCaptureStore,
    StoredLinkCapture,
    capture_id_for,
)
from services.link_capture.models import NormalizedContent, SourcePlatform


SOURCE_URL = (
    "https://www.instagram.com/reel/DcBzxM4IFLl/"
    "?igsh=OGk4MzVnbW9vams3&igsi=OGk4MzVnbW9vams3"
)


class LinkCaptureStateTest(unittest.TestCase):
    def test_round_trip_preserves_exact_source_and_private_permissions(self) -> None:
        capture_id = capture_id_for("telegram", "message-1", SOURCE_URL)
        record = StoredLinkCapture(
            capture_id=capture_id,
            source_message_id="message-1",
            content=NormalizedContent.captured(
                SOURCE_URL,
                SourcePlatform.INSTAGRAM,
                saved_at="2026-08-16T08:00:00Z",
            ),
        ).with_transcript("Reverse Step Up", "plaud_web")

        with TemporaryDirectory() as directory:
            root = Path(directory) / "captures"
            store = JsonLinkCaptureStore(root)
            store.save(record)
            restored = store.load(capture_id)
            mode = (root / f"{capture_id}.json").stat().st_mode & 0o777

        self.assertIsNotNone(restored)
        self.assertEqual(restored.content.source_url, SOURCE_URL)
        self.assertEqual(restored.transcript_text, "Reverse Step Up")
        self.assertEqual(mode, 0o600)

    def test_mark_saved_removes_transcript_but_not_source(self) -> None:
        capture_id = capture_id_for("telegram", "message-2", SOURCE_URL)
        record = StoredLinkCapture(
            capture_id=capture_id,
            source_message_id="message-2",
            content=NormalizedContent.captured(
                SOURCE_URL,
                SourcePlatform.INSTAGRAM,
                saved_at="2026-08-16T08:00:00Z",
            ),
        ).with_transcript("raw transcript", "plaud_web")

        saved = record.mark_saved("page-id", "https://notion.so/page-id")

        self.assertEqual(saved.content.source_url, SOURCE_URL)
        self.assertIsNone(saved.transcript_text)
        self.assertEqual(saved.status, "saved")

    def test_capture_id_rejects_empty_message_identity(self) -> None:
        with self.assertRaisesRegex(ValueError, "source_message_id"):
            capture_id_for("telegram", "", SOURCE_URL)


if __name__ == "__main__":
    unittest.main()
