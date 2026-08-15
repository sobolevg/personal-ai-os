"""PLAUD Developer API transcription provider."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import json
import logging
from typing import Any, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

from services.link_capture.models import TranscriptResult, TranscriptSegment
from services.link_capture.transcription.base import (
    TranscriptionError,
    TranscriptionTimeoutError,
)


logger = logging.getLogger(__name__)
_IN_PROGRESS = {"PENDING", "RECEIVED", "STARTED", "PROGRESS"}
_FAILED = {"FAILURE", "REVOKED"}


class JsonHttpTransport(Protocol):
    async def request_json(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        payload: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]: ...


@dataclass(frozen=True, slots=True)
class UrllibJsonTransport:
    """Small async JSON transport with bounded retry and response size."""

    timeout_seconds: float = 20.0
    retries: int = 2
    backoff_seconds: float = 0.5
    max_response_bytes: int = 2_000_000

    async def request_json(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        payload: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                return await asyncio.to_thread(
                    self._request_json_sync,
                    method,
                    url,
                    headers,
                    payload,
                )
            except Exception as error:
                last_error = error
                if attempt >= self.retries or not _is_retryable(error, method):
                    break
                delay = self.backoff_seconds * (2**attempt)
                logger.warning(
                    "PLAUD request failed; retrying",
                    extra={"attempt": attempt + 1, "delay_seconds": delay},
                )
                if delay:
                    await asyncio.sleep(delay)
        if isinstance(last_error, HTTPError):
            detail = f"HTTP {last_error.code}"
        else:
            detail = type(last_error).__name__ if last_error else "unknown error"
        raise TranscriptionError(f"PLAUD request failed ({detail})") from last_error

    def _request_json_sync(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any] | None,
    ) -> Mapping[str, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(url, data=body, headers=dict(headers), method=method)
        with urlopen(request, timeout=self.timeout_seconds) as response:
            raw = response.read(self.max_response_bytes + 1)
        if len(raw) > self.max_response_bytes:
            raise TranscriptionError("PLAUD response exceeded size limit")
        try:
            decoded = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise TranscriptionError("PLAUD returned invalid JSON") from error
        if not isinstance(decoded, dict):
            raise TranscriptionError("PLAUD returned an invalid response object")
        return decoded


@dataclass(frozen=True, slots=True)
class PlaudTranscriber:
    """Submit a public media URL and poll PLAUD until completion."""

    client_id: str = field(repr=False)
    api_key: str = field(repr=False)
    transport: JsonHttpTransport = field(default_factory=UrllibJsonTransport)
    base_url: str = "https://platform-us.plaud.ai"
    poll_interval_seconds: float = 2.0
    max_poll_attempts: int = 90
    model: str = "plaud-fast-whisper"
    name: str = field(default="plaud", init=False)

    def __post_init__(self) -> None:
        if not self.client_id or not self.api_key:
            raise ValueError("PLAUD client_id and api_key are required")
        if self.poll_interval_seconds < 0:
            raise ValueError("poll_interval_seconds must be non-negative")
        if self.max_poll_attempts <= 0:
            raise ValueError("max_poll_attempts must be positive")
        parsed = urlsplit(self.base_url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("PLAUD base_url must be an absolute HTTPS URL")

    async def transcribe(
        self,
        media_url: str,
        *,
        language: str = "auto",
    ) -> TranscriptResult:
        _validate_public_media_url(media_url)
        endpoint = (
            self.base_url.rstrip("/")
            + "/developer/api/open/partner/ai/transcriptions/"
        )
        submitted = await self.transport.request_json(
            "POST",
            endpoint,
            headers=self._headers(),
            payload={
                "file_url": media_url,
                "params": {
                    "transcribe": {"language": language, "model": self.model},
                    "vad": {"decode_silence": False},
                    "diarization": {
                        "enabled": False,
                        "return_embedding": False,
                    },
                },
            },
        )
        transcription_id = submitted.get("transcription_id")
        if not isinstance(transcription_id, str) or not transcription_id:
            raise TranscriptionError("PLAUD response omitted transcription_id")

        status_payload = submitted
        for attempt in range(self.max_poll_attempts):
            status = _status(status_payload)
            if status == "SUCCESS":
                return _parse_result(status_payload)
            if status in _FAILED:
                raise TranscriptionError(f"PLAUD transcription ended with {status}")
            if status not in _IN_PROGRESS:
                raise TranscriptionError(f"PLAUD returned unknown status {status}")
            if attempt and self.poll_interval_seconds:
                await asyncio.sleep(self.poll_interval_seconds)
            status_payload = await self.transport.request_json(
                "GET",
                endpoint + quote(transcription_id, safe=""),
                headers=self._headers(),
            )
        raise TranscriptionTimeoutError("PLAUD transcription polling timed out")

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "User-Agent": "Hermes-Link-Capture/0.1",
            "X-Client-Id": self.client_id,
            "X-Client-Api-Key": self.api_key,
        }


def _status(payload: Mapping[str, Any]) -> str:
    value = payload.get("status")
    if not isinstance(value, str) or not value:
        raise TranscriptionError("PLAUD response omitted status")
    return value.upper()


def _parse_result(payload: Mapping[str, Any]) -> TranscriptResult:
    data = payload.get("data")
    if not isinstance(data, dict):
        raise TranscriptionError("PLAUD success response omitted transcript data")
    text = data.get("text")
    if not isinstance(text, str):
        raise TranscriptionError("PLAUD success response omitted transcript text")
    language = data.get("language") if isinstance(data.get("language"), str) else ""
    duration_value = data.get("duration")
    duration = float(duration_value) if isinstance(duration_value, (int, float)) else None
    raw_segments = data.get("results", data.get("segments", []))
    segments: list[TranscriptSegment] = []
    if isinstance(raw_segments, list):
        for item in raw_segments:
            if not isinstance(item, dict) or not isinstance(item.get("text"), str):
                continue
            start = item.get("start")
            end = item.get("end")
            if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
                continue
            speaker_value = item.get("speaker_id", item.get("speaker"))
            speaker = speaker_value if isinstance(speaker_value, str) else None
            segments.append(
                TranscriptSegment(
                    start=float(start),
                    end=float(end),
                    text=item["text"],
                    speaker=speaker,
                )
            )
    return TranscriptResult(
        text=text,
        language=language,
        duration_seconds=duration,
        segments=tuple(segments),
        provider="plaud",
    )


def _validate_public_media_url(url: str) -> None:
    parsed = urlsplit(url)
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or not hostname:
        raise ValueError("media_url must be an absolute HTTPS URL")
    if hostname in {"localhost", "localhost.localdomain"}:
        raise ValueError("media_url must be publicly accessible")


def _is_retryable(error: Exception, method: str) -> bool:
    # A timed-out or failed POST may already have created a transcription task.
    # Without an idempotency key, retry only the read-only polling request.
    if method.upper() != "GET":
        return False
    if isinstance(error, HTTPError):
        return error.code in {408, 429} or error.code >= 500
    return isinstance(error, (TimeoutError, URLError))
