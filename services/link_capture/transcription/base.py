"""Provider-neutral transcription boundary."""

from __future__ import annotations

from typing import Protocol

from services.link_capture.models import TranscriptResult


class TranscriptionError(RuntimeError):
    """Raised when a provider cannot produce a transcript."""


class TranscriptionTimeoutError(TranscriptionError):
    """Raised when an asynchronous provider does not finish in time."""


class MediaTranscriber(Protocol):
    name: str

    async def transcribe(
        self,
        media_url: str,
        *,
        language: str = "auto",
    ) -> TranscriptResult: ...
