from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from services.link_capture.capture_state import (
    JsonLinkCaptureStore,
    StoredLinkCapture,
    capture_id_for,
)
from services.link_capture.extraction.registry import ExtractionOutcome
from services.link_capture.media.base import PreparedMedia
from services.link_capture.models import (
    ContentEnrichment,
    NormalizedContent,
    SourcePlatform,
    TranscriptResult,
    TranscriptSegment,
)
from services.link_capture.workflow import prepare_instagram_capture


SOURCE_URL = "https://www.instagram.com/reel/ABC/?igsh=exact"
MEDIA_URL = "https://video.cdninstagram.com/reel.mp4?expires=soon"


class StubRegistry:
    async def enrich(self, content: NormalizedContent) -> ExtractionOutcome:
        return ExtractionOutcome(
            content=content.enrich(
                ContentEnrichment(
                    canonical_url="https://www.instagram.com/reel/ABC/",
                    title="Reverse Step Up",
                    media_url=MEDIA_URL,
                )
            ),
            provider="instagram",
            extracted=True,
        )


class StubPreprocessor:
    def __init__(self) -> None:
        self.path: Path | None = None

    async def prepare_m4a(self, media_url: str, *, work_dir: Path) -> PreparedMedia:
        self.asserted_url = media_url
        work_dir.mkdir(parents=True, exist_ok=True)
        self.path = (work_dir / "prepared.m4a").resolve()
        self.path.write_bytes(b"audio")
        return PreparedMedia(self.path, "audio/mp4", 5)


class StubTranscriber:
    async def transcribe_file(
        self,
        media: PreparedMedia,
        *,
        language: str = "auto",
    ) -> TranscriptResult:
        return TranscriptResult(
            text="Reverse Step Up тренирует контроль колена.",
            language="ru",
            duration_seconds=10,
            segments=(
                TranscriptSegment(
                    start=0,
                    end=10,
                    text="Reverse Step Up тренирует контроль колена.",
                ),
            ),
            provider="plaud_web",
        )


class LinkCaptureWorkflowTest(unittest.IsolatedAsyncioTestCase):
    async def test_prepares_transcript_and_preserves_original_source(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            store = JsonLinkCaptureStore(root / "captures")
            preprocessor = StubPreprocessor()

            result = await prepare_instagram_capture(
                source_url=SOURCE_URL,
                source_message_id="message-1",
                store=store,
                extractor_registry=StubRegistry(),
                preprocessor=preprocessor,
                transcriber=StubTranscriber(),
                media_work_dir=root / "media",
            )

            restored = store.load(result.capture.capture_id)
            prepared_exists = preprocessor.path.exists()

        self.assertEqual(result.capture.content.source_url, SOURCE_URL)
        self.assertEqual(result.capture.content.canonical_url, "https://www.instagram.com/reel/ABC/")
        self.assertEqual(result.capture.content.media_url, MEDIA_URL)
        self.assertIn("Reverse Step Up", result.capture.transcript_text)
        self.assertEqual(restored.content.source_url, SOURCE_URL)
        self.assertFalse(prepared_exists)

    async def test_returns_saved_capture_without_reprocessing(self) -> None:
        with TemporaryDirectory() as directory:
            store = JsonLinkCaptureStore(Path(directory) / "captures")
            first = await prepare_instagram_capture(
                source_url=SOURCE_URL,
                source_message_id="message-2",
                store=store,
                extractor_registry=StubRegistry(),
                preprocessor=StubPreprocessor(),
                transcriber=StubTranscriber(),
                media_work_dir=Path(directory) / "media",
            )
            saved = first.capture.mark_saved("page", "https://notion.so/page")
            store.save(saved)

            second = await prepare_instagram_capture(
                source_url=SOURCE_URL,
                source_message_id="message-2",
                store=store,
                extractor_registry=object(),
            )

        self.assertEqual(second.capture.status, "saved")
        self.assertEqual(second.capture.notion_page_url, "https://notion.so/page")

    async def test_retry_preserves_first_saved_at(self) -> None:
        with TemporaryDirectory() as directory:
            store = JsonLinkCaptureStore(Path(directory) / "captures")
            capture_id = capture_id_for("telegram", "message-3", SOURCE_URL)
            store.save(
                StoredLinkCapture(
                    capture_id=capture_id,
                    source_message_id="message-3",
                    content=NormalizedContent.captured(
                        SOURCE_URL,
                        SourcePlatform.INSTAGRAM,
                        saved_at="2026-08-16T08:00:00Z",
                    ),
                )
            )

            result = await prepare_instagram_capture(
                source_url=SOURCE_URL,
                source_message_id="message-3",
                store=store,
                extractor_registry=StubRegistry(),
                preprocessor=StubPreprocessor(),
                transcriber=StubTranscriber(),
                media_work_dir=Path(directory) / "media",
            )

        self.assertEqual(result.capture.content.saved_at, "2026-08-16T08:00:00Z")


if __name__ == "__main__":
    unittest.main()
