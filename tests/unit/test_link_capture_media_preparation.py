from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from typing import Sequence

from services.link_capture.media.base import MediaPreparationError
from services.link_capture.media.ffmpeg import (
    FfmpegM4aPreprocessor,
    ProcessResult,
)
from services.link_capture.models import NormalizedContent, SourcePlatform


class StubProcessRunner:
    def __init__(
        self,
        *,
        returncode: int = 0,
        output: bytes | None = b"m4a-data",
    ) -> None:
        self.returncode = returncode
        self.output = output
        self.calls: list[tuple[tuple[str, ...], float]] = []

    async def run(
        self,
        arguments: Sequence[str],
        *,
        timeout_seconds: float,
    ) -> ProcessResult:
        values = tuple(arguments)
        self.calls.append((values, timeout_seconds))
        if self.output is not None:
            Path(values[-1]).write_bytes(self.output)
        return ProcessResult(returncode=self.returncode, stderr="test error")


class FfmpegM4aPreprocessorTest(unittest.IsolatedAsyncioTestCase):
    async def test_remuxes_media_url_without_touching_original_source(self) -> None:
        source_url = "https://www.instagram.com/reel/ABC/?igsh=exact"
        media_url = "https://instagram.example.fbcdn.net/video.mp4?expires=soon"
        original = NormalizedContent.captured(
            source_url,
            SourcePlatform.INSTAGRAM,
            saved_at="2026-08-16T09:00:00Z",
        ).with_updates({"media_url": media_url})
        runner = StubProcessRunner()
        preprocessor = FfmpegM4aPreprocessor(runner=runner)

        with TemporaryDirectory() as directory:
            prepared = await preprocessor.prepare_m4a(
                original.media_url or "",
                work_dir=Path(directory),
            )

            self.assertTrue(prepared.path.is_file())
            self.assertEqual(prepared.path.suffix, ".m4a")
            self.assertEqual(prepared.mime_type, "audio/mp4")
            self.assertEqual(prepared.size_bytes, len(b"m4a-data"))
            command, timeout = runner.calls[0]
            self.assertEqual(timeout, 120.0)
            self.assertEqual(command[command.index("-i") + 1], media_url)
            self.assertEqual(command[command.index("-c:a") + 1], "copy")
            self.assertNotIn(source_url, command)
            self.assertEqual(original.source_url, source_url)

    async def test_rejects_private_or_insecure_media_urls_before_process(self) -> None:
        runner = StubProcessRunner()
        preprocessor = FfmpegM4aPreprocessor(runner=runner)

        with TemporaryDirectory() as directory:
            for url in (
                "http://cdn.example.com/video.mp4",
                "https://localhost/video.mp4",
                "https://127.0.0.1/video.mp4",
                "https://10.0.0.1/video.mp4",
            ):
                with self.subTest(url=url):
                    with self.assertRaises(ValueError):
                        await preprocessor.prepare_m4a(
                            url,
                            work_dir=Path(directory),
                        )

        self.assertEqual(runner.calls, [])

    async def test_removes_partial_output_when_ffmpeg_fails(self) -> None:
        runner = StubProcessRunner(returncode=1, output=b"partial")
        preprocessor = FfmpegM4aPreprocessor(runner=runner)

        with TemporaryDirectory() as directory:
            work_dir = Path(directory)
            with self.assertRaisesRegex(MediaPreparationError, "exit code 1"):
                await preprocessor.prepare_m4a(
                    "https://cdn.example.com/video.mp4",
                    work_dir=work_dir,
                )
            self.assertEqual(list(work_dir.iterdir()), [])

    async def test_rejects_and_removes_oversized_output(self) -> None:
        runner = StubProcessRunner(output=b"too-large")
        preprocessor = FfmpegM4aPreprocessor(
            runner=runner,
            max_output_bytes=4,
        )

        with TemporaryDirectory() as directory:
            work_dir = Path(directory)
            with self.assertRaisesRegex(MediaPreparationError, "size limit"):
                await preprocessor.prepare_m4a(
                    "https://cdn.example.com/video.mp4",
                    work_dir=work_dir,
                )
            self.assertEqual(list(work_dir.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
