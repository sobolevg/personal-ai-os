"""Validated data contracts for the link capture pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping
from urllib.parse import urlsplit


class SourcePlatform(str, Enum):
    INSTAGRAM = "instagram"
    THREADS = "threads"
    X = "x"
    TELEGRAM = "telegram"
    YOUTUBE = "youtube"
    WEB = "web"


class Action(str, Enum):
    READ = "read"
    WATCH = "watch"
    TRY = "try"
    BUY = "buy"
    DO = "do"
    NONE = "none"


class Actionability(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SourceUrlIntegrityError(ValueError):
    """Raised when enrichment attempts to replace captured source identity."""


def utc_now_iso() -> str:
    """Return an RFC 3339 UTC timestamp suitable for Notion and JSON."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class ContentEnrichment:
    """Metadata produced by an extractor.

    This model intentionally has no ``source_url`` or ``saved_at`` field. An
    extractor can enrich a capture but cannot redefine where it came from or
    when Hermes accepted it.
    """

    canonical_url: str | None = None
    author: str = ""
    author_url: str = ""
    title: str = ""
    text: str = ""
    media_type: str = ""
    thumbnail_url: str = ""
    media_url: str | None = None
    published_at: str | None = None

    def __post_init__(self) -> None:
        for name in ("canonical_url", "media_url"):
            value = getattr(self, name)
            if value is not None:
                _validate_http_url(value, name)
        if self.author_url:
            _validate_http_url(self.author_url, "author_url")
        if self.thumbnail_url:
            _validate_http_url(self.thumbnail_url, "thumbnail_url")
        if self.published_at is not None:
            _validate_timestamp(self.published_at, "published_at")


@dataclass(frozen=True, slots=True)
class NormalizedContent:
    """A captured item whose original source identity is immutable."""

    source_url: str
    platform: SourcePlatform
    author: str = ""
    author_url: str = ""
    title: str = ""
    text: str = ""
    media_type: str = ""
    thumbnail_url: str = ""
    published_at: str | None = None
    saved_at: str = field(default_factory=utc_now_iso)
    canonical_url: str | None = None
    media_url: str | None = None

    def __post_init__(self) -> None:
        _validate_http_url(self.source_url, "source_url")
        if not isinstance(self.platform, SourcePlatform):
            raise TypeError("platform must be a SourcePlatform")
        _validate_timestamp(self.saved_at, "saved_at")
        if self.published_at is not None:
            _validate_timestamp(self.published_at, "published_at")
        for name in ("canonical_url", "media_url"):
            value = getattr(self, name)
            if value is not None:
                _validate_http_url(value, name)
        if self.author_url:
            _validate_http_url(self.author_url, "author_url")
        if self.thumbnail_url:
            _validate_http_url(self.thumbnail_url, "thumbnail_url")

    @classmethod
    def captured(
        cls,
        source_url: str,
        platform: SourcePlatform,
        *,
        saved_at: str | None = None,
    ) -> NormalizedContent:
        """Create the durable record before redirects or extraction occur."""
        values: dict[str, Any] = {"source_url": source_url, "platform": platform}
        if saved_at is not None:
            values["saved_at"] = saved_at
        return cls(**values)

    def enrich(self, enrichment: ContentEnrichment) -> NormalizedContent:
        """Apply extractor output without changing capture identity."""
        if not isinstance(enrichment, ContentEnrichment):
            raise TypeError("enrichment must be a ContentEnrichment")
        updates = asdict(enrichment)
        return replace(self, **updates)

    def with_updates(self, updates: Mapping[str, Any]) -> NormalizedContent:
        """Apply trusted pipeline updates while guarding immutable identity."""
        protected = {"source_url", "saved_at"}.intersection(updates)
        if protected:
            protected_names = ", ".join(sorted(protected))
            raise SourceUrlIntegrityError(
                f"capture identity fields cannot be updated: {protected_names}"
            )
        allowed = {item.name for item in fields(self)}
        unknown = set(updates).difference(allowed)
        if unknown:
            unknown_names = ", ".join(sorted(unknown))
            raise ValueError(f"unknown normalized content fields: {unknown_names}")
        return replace(self, **dict(updates))

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["platform"] = self.platform.value
        return result


@dataclass(frozen=True, slots=True)
class ContentClassification:
    """Strict structured output expected from the LLM classifier."""

    title: str
    summary: str
    topics: tuple[str, ...]
    content_type: str
    action: Action
    actionability: Actionability
    why_relevant: str
    suggested_area: str | None
    suggested_project: str | None
    reusable_knowledge: bool

    def __post_init__(self) -> None:
        if not isinstance(self.topics, tuple) or not all(
            isinstance(topic, str) for topic in self.topics
        ):
            raise TypeError("topics must be a tuple of strings")
        if not isinstance(self.action, Action):
            raise TypeError("action must be an Action")
        if not isinstance(self.actionability, Actionability):
            raise TypeError("actionability must be an Actionability")
        if not isinstance(self.reusable_knowledge, bool):
            raise TypeError("reusable_knowledge must be a boolean")
        for name in ("title", "summary", "content_type", "why_relevant"):
            if not isinstance(getattr(self, name), str):
                raise TypeError(f"{name} must be a string")
        for name in ("suggested_area", "suggested_project"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, str):
                raise TypeError(f"{name} must be a string or null")

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ContentClassification:
        expected = {
            "title",
            "summary",
            "topics",
            "content_type",
            "action",
            "actionability",
            "why_relevant",
            "suggested_area",
            "suggested_project",
            "reusable_knowledge",
        }
        missing = expected.difference(payload)
        extra = set(payload).difference(expected)
        if missing or extra:
            details = []
            if missing:
                details.append(f"missing: {', '.join(sorted(missing))}")
            if extra:
                details.append(f"unexpected: {', '.join(sorted(extra))}")
            raise ValueError(
                "invalid classification schema (" + "; ".join(details) + ")"
            )

        topics = payload["topics"]
        if not isinstance(topics, list) or not all(
            isinstance(topic, str) for topic in topics
        ):
            raise TypeError("topics must be a list of strings")
        if not isinstance(payload["reusable_knowledge"], bool):
            raise TypeError("reusable_knowledge must be a boolean")
        for name in (
            "title",
            "summary",
            "content_type",
            "why_relevant",
        ):
            if not isinstance(payload[name], str):
                raise TypeError(f"{name} must be a string")
        for name in ("suggested_area", "suggested_project"):
            if payload[name] is not None and not isinstance(payload[name], str):
                raise TypeError(f"{name} must be a string or null")

        return cls(
            title=payload["title"],
            summary=payload["summary"],
            topics=tuple(topics),
            content_type=payload["content_type"],
            action=Action(payload["action"]),
            actionability=Actionability(payload["actionability"]),
            why_relevant=payload["why_relevant"],
            suggested_area=payload["suggested_area"],
            suggested_project=payload["suggested_project"],
            reusable_knowledge=payload["reusable_knowledge"],
        )

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["topics"] = list(self.topics)
        result["action"] = self.action.value
        result["actionability"] = self.actionability.value
        return result


@dataclass(frozen=True, slots=True)
class TranscriptSegment:
    """One time-aligned fragment returned by a transcription provider."""

    start: float
    end: float
    text: str
    speaker: str | None = None

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < self.start:
            raise ValueError("transcript segment timestamps are invalid")
        if not isinstance(self.text, str):
            raise TypeError("transcript segment text must be a string")


@dataclass(frozen=True, slots=True)
class TranscriptResult:
    """Provider-neutral transcript kept separate from captured metadata."""

    text: str
    language: str
    duration_seconds: float | None
    segments: tuple[TranscriptSegment, ...]
    provider: str

    def __post_init__(self) -> None:
        if not isinstance(self.text, str):
            raise TypeError("transcript text must be a string")
        if self.duration_seconds is not None and self.duration_seconds < 0:
            raise ValueError("transcript duration must be non-negative")
        if not isinstance(self.segments, tuple) or not all(
            isinstance(segment, TranscriptSegment) for segment in self.segments
        ):
            raise TypeError("segments must be a tuple of TranscriptSegment values")


def _validate_http_url(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")
    if value != value.strip():
        raise ValueError(f"{field_name} must not contain surrounding whitespace")
    parsed = urlsplit(value)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"{field_name} must be an absolute HTTP(S) URL")


def _validate_timestamp(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field_name} must be an ISO timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} must include a timezone")
