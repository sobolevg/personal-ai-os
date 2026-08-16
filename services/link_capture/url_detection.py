"""URL extraction and source-platform detection without URL rewriting."""

from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import urlsplit

from services.link_capture.models import SourcePlatform


class InvalidSourceUrlError(ValueError):
    """Raised when platform detection receives an invalid source URL."""


@dataclass(frozen=True, slots=True)
class DetectedUrl:
    source_url: str
    platform: SourcePlatform


_URL_PATTERN = re.compile(r"https?://[^\s<>\"'\]]+", re.IGNORECASE)
_SIMPLE_TRAILING_PUNCTUATION = ".,!?;:"
_CLOSING_DELIMITERS = {")": "(", "]": "[", "}": "{"}

_PLATFORM_DOMAINS: tuple[tuple[SourcePlatform, tuple[str, ...]], ...] = (
    (SourcePlatform.INSTAGRAM, ("instagram.com",)),
    (SourcePlatform.THREADS, ("threads.net", "threads.com")),
    (SourcePlatform.X, ("x.com", "twitter.com", "t.co")),
    (
        SourcePlatform.TELEGRAM,
        ("t.me", "telegram.me", "telegram.dog"),
    ),
    (
        SourcePlatform.YOUTUBE,
        ("youtube.com", "youtu.be", "youtube-nocookie.com"),
    ),
)


def extract_urls(message: str | None) -> tuple[str, ...]:
    """Return HTTP(S) URLs exactly as shared, excluding prose punctuation."""
    if not message:
        return ()
    return tuple(
        _trim_prose_punctuation(match.group(0))
        for match in _URL_PATTERN.finditer(message)
    )


def detect_platform(source_url: str) -> SourcePlatform:
    """Detect a supported platform from hostname without following redirects."""
    try:
        parsed = urlsplit(source_url)
        hostname = (parsed.hostname or "").lower().rstrip(".")
    except ValueError as error:
        raise InvalidSourceUrlError("source_url is not a valid URL") from error

    if parsed.scheme.lower() not in {"http", "https"} or not hostname:
        raise InvalidSourceUrlError("source_url must be an absolute HTTP(S) URL")

    for platform, domains in _PLATFORM_DOMAINS:
        if any(_is_domain_or_subdomain(hostname, domain) for domain in domains):
            return platform
    return SourcePlatform.WEB


def detect_urls(message: str | None) -> tuple[DetectedUrl, ...]:
    """Extract URLs and classify each source without changing its value."""
    return tuple(
        DetectedUrl(source_url=url, platform=detect_platform(url))
        for url in extract_urls(message)
    )


def _is_domain_or_subdomain(hostname: str, domain: str) -> bool:
    return hostname == domain or hostname.endswith(f".{domain}")


def _trim_prose_punctuation(url: str) -> str:
    while url and url[-1] in _SIMPLE_TRAILING_PUNCTUATION:
        url = url[:-1]

    changed = True
    while url and changed:
        changed = False
        closer = url[-1]
        opener = _CLOSING_DELIMITERS.get(closer)
        if opener is not None and url.count(closer) > url.count(opener):
            url = url[:-1]
            changed = True
    return url
