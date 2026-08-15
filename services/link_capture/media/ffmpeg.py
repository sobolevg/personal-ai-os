"""Extract an existing audio stream into an M4A container with FFmpeg."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import ipaddress
import os
from pathlib import Path
from typing import Protocol, Sequence
from urllib.parse import urlsplit
from uuid import uuid4

from services.link_capture.media.base import MediaPreparationError, PreparedMedia


@dataclass(frozen=True, slots=True)
class ProcessResult:
    returncode: int
    stderr: str = ""


class ProcessRunner(Protocol):
    async def run(
        self,
        arguments: Sequence[str],
        *,
        timeout_seconds: float,
    ) -> ProcessResult: ...


@dataclass(frozen=True, slots=True)
class AsyncioProcessRunner:
    """Run a subprocess without a shell and with a hard timeout."""

    async def run(
        self,
        arguments: Sequence[str],
        *,
        timeout_seconds: float,
    ) -> ProcessResult:
        process = await asyncio.create_subprocess_exec(
            *arguments,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout_seconds,
            )
        except TimeoutError as error:
            process.kill()
            await process.communicate()
            raise MediaPreparationError("FFmpeg media preparation timed out") from error
        return ProcessResult(
            returncode=process.returncode or 0,
            stderr=stderr.decode("utf-8", errors="replace")[-2_000:],
        )


@dataclass(frozen=True, slots=True)
class FfmpegM4aPreprocessor:
    """Remux the first audio stream to M4A without quality loss."""

    runner: ProcessRunner = field(default_factory=AsyncioProcessRunner)
    ffmpeg_binary: str = "ffmpeg"
    timeout_seconds: float = 120.0
    max_output_bytes: int = 50_000_000
    name: str = field(default="ffmpeg_m4a", init=False)

    def __post_init__(self) -> None:
        if not self.ffmpeg_binary:
            raise ValueError("ffmpeg_binary is required")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_output_bytes <= 0:
            raise ValueError("max_output_bytes must be positive")

    async def prepare_m4a(
        self,
        media_url: str,
        *,
        work_dir: Path,
    ) -> PreparedMedia:
        _validate_remote_media_url(media_url)
        absolute_work_dir = work_dir.expanduser().resolve()
        absolute_work_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        output_path = absolute_work_dir / f"{uuid4().hex}.m4a"
        arguments = (
            self.ffmpeg_binary,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            media_url,
            "-map",
            "0:a:0",
            "-vn",
            "-c:a",
            "copy",
            "-f",
            "ipod",
            str(output_path),
        )
        try:
            result = await self.runner.run(
                arguments,
                timeout_seconds=self.timeout_seconds,
            )
            if result.returncode != 0:
                raise MediaPreparationError(
                    f"FFmpeg failed with exit code {result.returncode}"
                )
            if not output_path.is_file():
                raise MediaPreparationError("FFmpeg produced no M4A file")
            size_bytes = output_path.stat().st_size
            if size_bytes <= 0:
                raise MediaPreparationError("FFmpeg produced an empty M4A file")
            if size_bytes > self.max_output_bytes:
                raise MediaPreparationError("prepared M4A exceeded size limit")
            os.chmod(output_path, 0o600)
            return PreparedMedia(
                path=output_path,
                mime_type="audio/mp4",
                size_bytes=size_bytes,
            )
        except Exception:
            output_path.unlink(missing_ok=True)
            raise


def _validate_remote_media_url(url: str) -> None:
    parsed = urlsplit(url)
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or not hostname:
        raise ValueError("media_url must be an absolute HTTPS URL")
    if hostname in {"localhost", "localhost.localdomain"}:
        raise ValueError("media_url must be publicly accessible")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return
    if not address.is_global:
        raise ValueError("media_url must not use a private or local IP address")
