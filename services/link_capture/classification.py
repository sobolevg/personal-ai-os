"""LLM classification boundary; concrete OpenAI-compatible client comes next."""

from __future__ import annotations

from typing import Protocol

from services.link_capture.models import ContentClassification, NormalizedContent


class ContentClassifier(Protocol):
    async def classify(self, content: NormalizedContent) -> ContentClassification: ...
