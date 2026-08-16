"""Conservative extraction of metadata exposed by public Instagram pages."""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
import json
import re
from urllib.parse import urljoin, urlsplit

from services.link_capture.extraction.base import (
    ExtractionError,
    ExtractionRequest,
    UnsupportedPlatformError,
)
from services.link_capture.extraction.http import (
    TextHttpTransport,
    UrllibTextTransport,
)
from services.link_capture.models import ContentEnrichment, SourcePlatform


_DESCRIPTION_AUTHOR_PATTERN = re.compile(
    r"^\s*[\d.,KM]+\s+likes?,\s+[\d.,KM]+\s+comments?\s+-\s+"
    r"(?P<username>[A-Za-z0-9._]{1,30})\s+on\s+",
    re.IGNORECASE,
)
_DESCRIPTION_CAPTION_PATTERN = re.compile(
    r"^\s*[\d.,KM]+\s+likes?,\s+[\d.,KM]+\s+comments?\s+-\s+"
    r"[A-Za-z0-9._]{1,30}\s+on\s+[^:]+:\s*(?P<caption>.*)\s*$",
    re.IGNORECASE | re.DOTALL,
)
_TITLE_CAPTION_PATTERN = re.compile(
    r"^\s*.+?\s+on\s+Instagram:\s*(?P<caption>.*)\s*$",
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True, slots=True)
class InstagramOpenGraphExtractor:
    """Read only metadata present in an unauthenticated public HTML response."""

    transport: TextHttpTransport = field(default_factory=UrllibTextTransport)
    name: str = field(default="instagram_open_graph", init=False)

    def supports(self, platform: SourcePlatform) -> bool:
        return platform is SourcePlatform.INSTAGRAM

    async def extract(self, request: ExtractionRequest) -> ContentEnrichment:
        if not self.supports(request.platform):
            raise UnsupportedPlatformError(
                f"{self.name} does not support {request.platform.value}"
            )
        if not _is_instagram_url(request.source_url):
            raise ExtractionError("Instagram provider requires an Instagram source URL")

        response = await self.transport.get_text(request.source_url)
        if not _is_instagram_url(response.final_url):
            raise ExtractionError("Instagram redirected to a non-Instagram host")
        if _is_blocked_page(response.final_url):
            raise ExtractionError("Instagram returned a login or challenge page")
        parser = _MetadataParser()
        parser.feed(response.body)

        title = parser.first("og:title", "twitter:title", "title")
        description = parser.first(
            "og:description",
            "twitter:description",
            "description",
        )
        caption = _instagram_caption(description, title)
        thumbnail_url = _absolute_url(
            parser.first("og:image", "twitter:image"),
            response.final_url,
        )
        canonical_url = _safe_canonical_url(
            parser.canonical_url,
            response.final_url,
        )
        published_at = parser.first("article:published_time") or None
        media_url = _extract_public_media_url(response.body)

        if not any((title, description, thumbnail_url)):
            raise ExtractionError("Instagram returned no public post metadata")

        return ContentEnrichment(
            canonical_url=canonical_url,
            author=_author_from_title(title),
            author_url=(
                _author_url(canonical_url or request.source_url)
                or _author_url_from_description(description)
            ),
            title=title,
            text=caption,
            media_type=_media_type(parser.first("og:type"), request.source_url),
            thumbnail_url=thumbnail_url,
            media_url=media_url,
            published_at=published_at,
        )


class _MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.metadata: dict[str, str] = {}
        self.canonical_url = ""
        self._in_title = False
        self._title_parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        attributes = {name.lower(): value or "" for name, value in attrs}
        lowered_tag = tag.lower()
        if lowered_tag == "meta":
            key = (attributes.get("property") or attributes.get("name") or "").lower()
            content = attributes.get("content", "").strip()
            if key and content:
                self.metadata.setdefault(key, content)
        elif lowered_tag == "link":
            rel = {item.lower() for item in attributes.get("rel", "").split()}
            if "canonical" in rel and attributes.get("href"):
                self.canonical_url = attributes["href"].strip()
        elif lowered_tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False
            title = "".join(self._title_parts).strip()
            if title:
                self.metadata.setdefault("title", title)

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_parts.append(data)

    def first(self, *keys: str) -> str:
        return next((self.metadata[key] for key in keys if self.metadata.get(key)), "")


def _absolute_url(value: str, base_url: str) -> str:
    return urljoin(base_url, value) if value else ""


def _safe_canonical_url(value: str, base_url: str) -> str | None:
    canonical_url = _absolute_url(value, base_url)
    if not canonical_url or _is_blocked_page(canonical_url):
        return None
    hostname = (urlsplit(canonical_url).hostname or "").lower().rstrip(".")
    if hostname == "instagram.com" or hostname.endswith(".instagram.com"):
        return canonical_url
    return None


def _is_instagram_url(url: str) -> bool:
    parsed = urlsplit(url)
    hostname = (parsed.hostname or "").lower().rstrip(".")
    return parsed.scheme.lower() in {"http", "https"} and (
        hostname == "instagram.com" or hostname.endswith(".instagram.com")
    )


def _is_blocked_page(url: str) -> bool:
    path = urlsplit(url).path.lower()
    return path.startswith(("/accounts/login", "/challenge", "/checkpoint"))


def _author_from_title(title: str) -> str:
    marker = " on Instagram"
    author, separator, _ = title.partition(marker)
    return author.strip() if separator else ""


def _author_url(post_url: str) -> str:
    parsed = urlsplit(post_url)
    segments = [segment for segment in parsed.path.split("/") if segment]
    if len(segments) >= 3 and segments[1].lower() in {"p", "reel", "reels"}:
        return f"https://www.instagram.com/{segments[0]}/"
    return ""


def _author_url_from_description(description: str) -> str:
    match = _DESCRIPTION_AUTHOR_PATTERN.match(description)
    if match is None:
        return ""
    return f"https://www.instagram.com/{match.group('username')}/"


def _instagram_caption(description: str, title: str) -> str:
    """Remove Instagram's engagement/date wrapper while preserving author text."""
    description_match = _DESCRIPTION_CAPTION_PATTERN.match(description)
    if description_match is not None:
        return _unwrap_caption(description_match.group("caption"))

    title_match = _TITLE_CAPTION_PATTERN.match(title)
    if title_match is not None:
        return _unwrap_caption(title_match.group("caption"))

    return description.strip()


def _unwrap_caption(value: str) -> str:
    caption = value.strip()
    if len(caption) >= 3 and caption[0] == '"' and caption.endswith('".'):
        return caption[1:-2].strip()
    if len(caption) >= 2 and caption[0] in {'"', "'"} and caption[-1] == caption[0]:
        return caption[1:-1].strip()
    return caption


def _extract_public_media_url(html: str) -> str | None:
    marker = '"video_versions":'
    position = html.find(marker)
    if position < 0:
        return None
    try:
        versions, _ = json.JSONDecoder().raw_decode(html[position + len(marker) :])
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(versions, list):
        return None
    for version in versions:
        if not isinstance(version, dict):
            continue
        candidate = version.get("url")
        if isinstance(candidate, str) and _is_public_instagram_media_url(candidate):
            return candidate
    return None


def _is_public_instagram_media_url(url: str) -> bool:
    parsed = urlsplit(url)
    hostname = (parsed.hostname or "").lower().rstrip(".")
    return parsed.scheme.lower() == "https" and (
        hostname.endswith(".fbcdn.net")
        or hostname == "cdninstagram.com"
        or hostname.endswith(".cdninstagram.com")
    )


def _media_type(open_graph_type: str, source_url: str) -> str:
    lowered_type = open_graph_type.lower()
    lowered_url = source_url.lower()
    if "video" in lowered_type or "/reel/" in lowered_url or "/reels/" in lowered_url:
        return "video"
    return "post"
