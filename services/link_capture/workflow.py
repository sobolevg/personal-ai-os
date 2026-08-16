"""Prepare an Instagram capture for classification by the active Hermes model."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path
from typing import Any

from services.link_capture.capture_state import (
    JsonLinkCaptureStore,
    StoredLinkCapture,
    capture_id_for,
)
from services.link_capture.config import PlaudWebSettings
from services.link_capture.extraction.providers.instagram import (
    InstagramOpenGraphExtractor,
)
from services.link_capture.extraction.registry import ExtractorRegistry
from services.link_capture.media.base import AudioPreprocessor
from services.link_capture.media.ffmpeg import FfmpegM4aPreprocessor
from services.link_capture.models import NormalizedContent, SourcePlatform
from services.link_capture.transcription.plaud_web import PlaudWebTranscriber
from services.link_capture.url_detection import detect_platform


DEFAULT_CAPTURE_ROOT = Path("/root/.hermes/personal-ai-os/link-capture/captures")
DEFAULT_MEDIA_WORK_DIR = Path("/root/.hermes/personal-ai-os/link-capture/media")
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PreparedLinkCapture:
    capture: StoredLinkCapture
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_model_dict(self) -> dict[str, Any]:
        content = self.capture.content
        return {
            "capture_id": self.capture.capture_id,
            "status": self.capture.status,
            "existing_page_url": self.capture.notion_page_url,
            "source_url": content.source_url,
            "canonical_url": content.canonical_url,
            "platform": content.platform.value,
            "author": content.author,
            "author_url": content.author_url,
            "title": content.title,
            "text": content.text,
            "media_type": content.media_type,
            "saved_at": content.saved_at,
            "transcript": self.capture.transcript_text or "",
            "transcript_provider": self.capture.transcript_provider,
            "warnings": list(self.warnings),
        }


async def prepare_instagram_capture(
    *,
    source_url: str,
    source_message_id: str,
    source_platform: str = "telegram",
    store: JsonLinkCaptureStore | None = None,
    extractor_registry: ExtractorRegistry | None = None,
    preprocessor: AudioPreprocessor | None = None,
    transcriber: PlaudWebTranscriber | None = None,
    media_work_dir: Path = DEFAULT_MEDIA_WORK_DIR,
) -> PreparedLinkCapture:
    """Persist capture identity first, then enrich and transcribe when possible."""
    platform = detect_platform(source_url)
    if platform is not SourcePlatform.INSTAGRAM:
        raise ValueError("only Instagram is enabled for this checkpoint")

    capture_store = store or JsonLinkCaptureStore(DEFAULT_CAPTURE_ROOT)
    capture_id = capture_id_for(source_platform, source_message_id, source_url)
    existing = capture_store.load(capture_id)
    if existing is not None and (
        existing.status == "saved" or existing.transcript_text
    ):
        return PreparedLinkCapture(capture=existing)

    if existing is None:
        captured = NormalizedContent.captured(source_url, platform)
        record = StoredLinkCapture(
            capture_id=capture_id,
            source_message_id=source_message_id,
            content=captured,
        )
        capture_store.save(record)
    else:
        captured = existing.content

    registry = extractor_registry or ExtractorRegistry(
        [InstagramOpenGraphExtractor()]
    )
    extraction = await registry.enrich(captured)
    record = StoredLinkCapture(
        capture_id=capture_id,
        source_message_id=source_message_id,
        content=extraction.content,
    )
    capture_store.save(record)

    warnings: list[str] = []
    if not extraction.extracted:
        warnings.append("metadata_unavailable")
    if not record.content.media_url:
        warnings.append("media_unavailable")
        return PreparedLinkCapture(capture=record, warnings=tuple(warnings))

    media_preprocessor = preprocessor or FfmpegM4aPreprocessor()
    prepared_media = None
    try:
        prepared_media = await media_preprocessor.prepare_m4a(
            record.content.media_url,
            work_dir=media_work_dir,
        )
        transcript_provider = transcriber or _default_plaud_web_transcriber()
        transcript = await transcript_provider.transcribe_file(prepared_media)
        if transcript.text.strip():
            record = record.with_transcript(transcript.text, transcript.provider)
            capture_store.save(record)
        else:
            warnings.append("transcript_empty")
    except Exception as error:
        logger.warning(
            "link transcription unavailable; preserving source capture",
            extra={
                "capture_id": capture_id,
                "error_type": type(error).__name__,
            },
        )
        warnings.append("transcription_unavailable")
    finally:
        if prepared_media is not None:
            prepared_media.path.unlink(missing_ok=True)

    return PreparedLinkCapture(capture=record, warnings=tuple(warnings))


def _default_plaud_web_transcriber() -> PlaudWebTranscriber:
    settings = PlaudWebSettings.from_env(None)
    return PlaudWebTranscriber(
        browser_python=settings.browser_python,
        profile_dir=settings.profile_dir,
        timeout_seconds=settings.timeout_seconds,
        headless=settings.headless,
    )
