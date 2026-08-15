"""Safe, replaceable media preparation boundaries."""

from services.link_capture.media.base import (
    AudioPreprocessor,
    MediaPreparationError,
    PreparedMedia,
)
from services.link_capture.media.ffmpeg import FfmpegM4aPreprocessor

__all__ = [
    "AudioPreprocessor",
    "FfmpegM4aPreprocessor",
    "MediaPreparationError",
    "PreparedMedia",
]
