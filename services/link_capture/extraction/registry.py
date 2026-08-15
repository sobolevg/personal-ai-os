"""Provider selection with graceful metadata-failure fallback."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Iterable

from services.link_capture.extraction.base import (
    ContentExtractor,
    ExtractionRequest,
)
from services.link_capture.models import NormalizedContent


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ExtractionOutcome:
    content: NormalizedContent
    provider: str | None
    extracted: bool
    error: str | None = None


class ExtractorRegistry:
    def __init__(self, extractors: Iterable[ContentExtractor] = ()) -> None:
        self._extractors = tuple(extractors)

    def select(self, content: NormalizedContent) -> ContentExtractor | None:
        return next(
            (
                extractor
                for extractor in self._extractors
                if extractor.supports(content.platform)
            ),
            None,
        )

    async def enrich(self, content: NormalizedContent) -> ExtractionOutcome:
        extractor = self.select(content)
        if extractor is None:
            return ExtractionOutcome(
                content=content,
                provider=None,
                extracted=False,
                error="no extractor registered for platform",
            )

        try:
            enrichment = await extractor.extract(
                ExtractionRequest(
                    source_url=content.source_url,
                    platform=content.platform,
                )
            )
            enriched = content.enrich(enrichment)
        except Exception as error:
            logger.warning(
                "content extraction failed; preserving minimal capture",
                extra={"provider": extractor.name, "platform": content.platform.value},
            )
            return ExtractionOutcome(
                content=content,
                provider=extractor.name,
                extracted=False,
                error=str(error),
            )

        return ExtractionOutcome(
            content=enriched,
            provider=extractor.name,
            extracted=True,
        )
