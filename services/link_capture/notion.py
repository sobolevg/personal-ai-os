"""Notion persistence boundary and stable property names."""

from __future__ import annotations

from typing import Protocol

from services.link_capture.models import ContentClassification, NormalizedContent


NOTION_PROPERTY_MAP = {
    "source_url": "Original URL",
    "canonical_url": "Canonical URL",
    "platform": "Source",
    "author": "Author",
    "author_url": "Author URL",
    "saved_at": "Saved At",
}


class NotionLinkStore(Protocol):
    async def save(
        self,
        content: NormalizedContent,
        classification: ContentClassification,
    ) -> str:
        """Save and return the Notion page URL.

        Implementations must map ``Original URL`` to ``content.source_url`` and
        also include a visible link to that URL in the page body.
        """
        ...
