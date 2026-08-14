"""Base interface implemented by platform-specific extractors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from services.link_capture.models import ContentEnrichment, SourcePlatform


@dataclass(frozen=True, slots=True)
class ExtractionRequest:
    source_url: str
    platform: SourcePlatform


class ContentExtractor(Protocol):
    def supports(self, platform: SourcePlatform) -> bool: ...

    async def extract(self, request: ExtractionRequest) -> ContentEnrichment: ...
