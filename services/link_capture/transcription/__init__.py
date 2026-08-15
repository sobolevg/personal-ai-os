"""Replaceable media transcription providers."""

from services.link_capture.transcription.base import (
    MediaTranscriber,
    TranscriptionError,
    TranscriptionTimeoutError,
)
from services.link_capture.transcription.plaud import PlaudTranscriber

__all__ = [
    "MediaTranscriber",
    "PlaudTranscriber",
    "TranscriptionError",
    "TranscriptionTimeoutError",
]
