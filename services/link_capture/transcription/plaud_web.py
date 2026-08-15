"""PLAUD Web transcription provider backed by an isolated browser runner."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Protocol, Sequence

from services.link_capture.media.base import PreparedMedia
from services.link_capture.models import TranscriptResult, TranscriptSegment
from services.link_capture.transcription.base import (
    TranscriptionError,
    TranscriptionTimeoutError,
)


@dataclass(frozen=True, slots=True)
class BrowserProcessResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


class BrowserProcessRunner(Protocol):
    async def run(
        self,
        arguments: Sequence[str],
        *,
        timeout_seconds: float,
    ) -> BrowserProcessResult: ...


@dataclass(frozen=True, slots=True)
class AsyncioBrowserProcessRunner:
    """Run browser automation without a shell or inherited stdin."""

    max_output_bytes: int = 2_000_000

    async def run(
        self,
        arguments: Sequence[str],
        *,
        timeout_seconds: float,
    ) -> BrowserProcessResult:
        process = await asyncio.create_subprocess_exec(
            *arguments,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout_seconds
            )
        except TimeoutError as error:
            process.kill()
            await process.communicate()
            raise TranscriptionTimeoutError(
                "PLAUD Web browser runner timed out"
            ) from error
        if len(stdout) > self.max_output_bytes:
            raise TranscriptionError("PLAUD Web output exceeded size limit")
        return BrowserProcessResult(
            returncode=process.returncode or 0,
            stdout=stdout.decode("utf-8", errors="replace"),
            stderr=stderr.decode("utf-8", errors="replace")[-2_000:],
        )


def _default_runner_script() -> Path:
    return Path(__file__).with_name("plaud_web_runner.py").resolve()


@dataclass(frozen=True, slots=True)
class PlaudWebTranscriber:
    """Upload local audio through PLAUD Web using a persistent VPS profile."""

    browser_python: Path
    profile_dir: Path
    runner: BrowserProcessRunner = field(default_factory=AsyncioBrowserProcessRunner)
    runner_script: Path = field(default_factory=_default_runner_script)
    timeout_seconds: float = 900.0
    headless: bool = True
    name: str = field(default="plaud_web", init=False)

    def __post_init__(self) -> None:
        if not self.browser_python.is_absolute():
            raise ValueError("browser_python must be an absolute path")
        if not self.profile_dir.is_absolute():
            raise ValueError("profile_dir must be an absolute path")
        if not self.runner_script.is_absolute():
            raise ValueError("runner_script must be an absolute path")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

    async def transcribe_file(
        self,
        media: PreparedMedia,
        *,
        language: str = "auto",
    ) -> TranscriptResult:
        if not media.path.is_file():
            raise ValueError("prepared media file does not exist")
        if media.path.stat().st_size != media.size_bytes:
            raise ValueError("prepared media size changed before upload")

        arguments = [
            str(self.browser_python),
            str(self.runner_script),
            "--profile-dir",
            str(self.profile_dir),
            "--media-file",
            str(media.path),
            "--language",
            language,
            "--timeout-seconds",
            str(self.timeout_seconds),
        ]
        if not self.headless:
            arguments.append("--headed")
        result = await self.runner.run(
            arguments,
            timeout_seconds=self.timeout_seconds + 30,
        )
        payload = _decode_runner_payload(result.stdout)
        status = payload.get("status")
        if status == "authentication_required":
            raise TranscriptionError(
                "PLAUD Web authentication is required for the persistent profile"
            )
        if result.returncode != 0 or status != "success":
            raise TranscriptionError("PLAUD Web browser runner failed")
        return _parse_web_result(payload, language)


def _decode_runner_payload(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise TranscriptionError("PLAUD Web runner returned invalid JSON") from error
    if not isinstance(payload, dict):
        raise TranscriptionError("PLAUD Web runner returned an invalid object")
    return payload


def _parse_web_result(
    payload: dict[str, Any], requested_language: str
) -> TranscriptResult:
    text = payload.get("text")
    if not isinstance(text, str) or not text.strip():
        raise TranscriptionError("PLAUD Web returned an empty transcript")
    raw_segments = payload.get("segments")
    if not isinstance(raw_segments, list):
        raise TranscriptionError("PLAUD Web omitted transcript segments")
    segments: list[TranscriptSegment] = []
    for item in raw_segments:
        if not isinstance(item, dict) or not isinstance(item.get("text"), str):
            continue
        start = item.get("start")
        end = item.get("end")
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
            continue
        speaker = item.get("speaker")
        segments.append(
            TranscriptSegment(
                start=float(start),
                end=float(end),
                text=item["text"],
                speaker=speaker if isinstance(speaker, str) else None,
            )
        )
    language = payload.get("language")
    if not isinstance(language, str) or not language:
        language = "" if requested_language == "auto" else requested_language
    duration = payload.get("duration_seconds")
    return TranscriptResult(
        text=text,
        language=language,
        duration_seconds=(
            float(duration) if isinstance(duration, (int, float)) else None
        ),
        segments=tuple(segments),
        provider="plaud_web",
    )
