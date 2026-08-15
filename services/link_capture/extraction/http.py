"""Small async HTTP transport for public metadata pages."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from typing import Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from services.link_capture.extraction.base import ExtractionError


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TextHttpResponse:
    final_url: str
    body: str
    headers: Mapping[str, str]


class TextHttpTransport(Protocol):
    async def get_text(self, url: str) -> TextHttpResponse: ...


@dataclass(frozen=True, slots=True)
class UrllibTextTransport:
    """Dependency-free public-page transport with bounded retry and response."""

    timeout_seconds: float = 10.0
    retries: int = 2
    backoff_seconds: float = 0.25
    max_response_bytes: int = 2_000_000
    user_agent: str = "Hermes-Link-Capture/0.1 (+personal metadata archiver)"

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.retries < 0:
            raise ValueError("retries must be non-negative")
        if self.backoff_seconds < 0:
            raise ValueError("backoff_seconds must be non-negative")
        if self.max_response_bytes <= 0:
            raise ValueError("max_response_bytes must be positive")

    async def get_text(self, url: str) -> TextHttpResponse:
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                return await asyncio.to_thread(self._get_text_sync, url)
            except Exception as error:
                last_error = error
                if attempt >= self.retries or not _is_retryable(error):
                    break
                delay = self.backoff_seconds * (2**attempt)
                logger.warning(
                    "metadata request failed; retrying",
                    extra={"attempt": attempt + 1, "delay_seconds": delay},
                )
                if delay:
                    await asyncio.sleep(delay)
        raise ExtractionError(f"metadata request failed: {last_error}") from last_error

    def _get_text_sync(self, url: str) -> TextHttpResponse:
        request = Request(
            url,
            headers={
                "Accept": "text/html,application/xhtml+xml",
                "User-Agent": self.user_agent,
            },
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            body = response.read(self.max_response_bytes + 1)
            if len(body) > self.max_response_bytes:
                raise ExtractionError("metadata response exceeded size limit")
            charset = response.headers.get_content_charset() or "utf-8"
            final_url = response.geturl()
            headers = dict(response.headers.items())
        try:
            text = body.decode(charset)
        except (LookupError, UnicodeDecodeError) as error:
            raise ExtractionError("metadata page has unsupported encoding") from error
        return TextHttpResponse(final_url=final_url, body=text, headers=headers)


def _is_retryable(error: Exception) -> bool:
    if isinstance(error, HTTPError):
        return error.code in {408, 429} or error.code >= 500
    return isinstance(error, (TimeoutError, URLError))
