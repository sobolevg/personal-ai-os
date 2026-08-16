"""Notion persistence boundary and Zettelkasten page construction."""

from __future__ import annotations

from typing import Any, Protocol

from services.link_capture.models import ContentClassification, NormalizedContent


NOTION_PROPERTY_MAP = {
    "title": "Name",
    "source_url": "Original URL",
    "canonical_url": "Canonical URL",
    "platform": "Source",
    "author": "Author",
    "author_url": "Author URL",
    "saved_at": "Saved At",
}


def build_zettelkasten_page_payload(
    database_id: str,
    content: NormalizedContent,
    classification: ContentClassification,
) -> dict[str, Any]:
    """Build a concise note with source caption but without raw transcription.

    The LLM owns only the distilled knowledge fields. Capture identity always
    comes from ``NormalizedContent``, so a model response cannot replace the
    exact URL that entered Hermes.
    """
    if not database_id.strip():
        raise ValueError("database_id is required")

    properties: dict[str, Any] = {
        NOTION_PROPERTY_MAP["title"]: _title(classification.title),
        NOTION_PROPERTY_MAP["source_url"]: {"url": content.source_url},
        NOTION_PROPERTY_MAP["platform"]: {
            "select": {"name": content.platform.value}
        },
        NOTION_PROPERTY_MAP["saved_at"]: {
            "date": {"start": content.saved_at}
        },
        "Type": {"select": {"name": "Permanent"}},
    }
    if content.canonical_url:
        properties[NOTION_PROPERTY_MAP["canonical_url"]] = {
            "url": content.canonical_url
        }
    if content.author:
        properties[NOTION_PROPERTY_MAP["author"]] = _rich_text(content.author)
    if content.author_url:
        properties[NOTION_PROPERTY_MAP["author_url"]] = {
            "url": content.author_url
        }

    children = [
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": "Оригинал",
                            "link": {"url": content.source_url},
                        },
                    }
                ]
            },
        },
        _heading("Суть"),
        _paragraph(classification.summary),
        _heading("Чем полезно"),
        _paragraph(classification.why_relevant),
    ]
    if content.text.strip():
        children.append(_source_text_toggle(content.text))
    children.append(
        {
            "object": "block",
            "type": "callout",
            "callout": {
                "icon": {"type": "emoji", "emoji": "⚠️"},
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": (
                                "Польза сформулирована по исходному материалу; "
                                "медицинские утверждения требуют отдельной проверки."
                            )
                        },
                    }
                ],
            },
        }
    )

    return {
        "parent": {"database_id": database_id},
        "properties": properties,
        "children": children,
    }


def _title(value: str) -> dict[str, Any]:
    return {"title": [{"type": "text", "text": {"content": value}}]}


def _rich_text(value: str) -> dict[str, Any]:
    return {"rich_text": [{"type": "text", "text": {"content": value}}]}


def _heading(value: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "heading_2",
        "heading_2": {
            "rich_text": [{"type": "text", "text": {"content": value}}]
        },
    }


def _paragraph(value: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{"type": "text", "text": {"content": value}}]
        },
    }


def _source_text_toggle(value: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "toggle",
        "toggle": {
            "rich_text": [
                {"type": "text", "text": {"content": "Описание автора"}}
            ],
            "children": [_paragraph(chunk) for chunk in _rich_text_chunks(value)],
        },
    }


def _rich_text_chunks(value: str, limit: int = 1900) -> list[str]:
    """Split source text below Notion's per-rich-text content limit."""
    text = value.strip()
    if not text:
        return []
    return [text[start : start + limit] for start in range(0, len(text), limit)]


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
