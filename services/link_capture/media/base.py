"""Provider-neutral media preparation contracts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class MediaPreparationError(RuntimeError):
    """Raised when source media cannot be prepared safely."""


@dataclass(frozen=True, slots=True)
class PreparedMedia:
    """A temporary local artifact ready for a downstream provider."""

    path: Path
    mime_type: str
    size_bytes: int

    def __post_init__(self) -> None:
        if not self.path.is_absolute():
            raise ValueError("prepared media path must be absolute")
        if not self.mime_type:
            raise ValueError("prepared media mime_type is required")
        if self.size_bytes <= 0:
            raise ValueError("prepared media size must be positive")


class AudioPreprocessor(Protocol):
    name: str

    async def prepare_m4a(
        self,
        media_url: str,
        *,
        work_dir: Path,
    ) -> PreparedMedia: ...
