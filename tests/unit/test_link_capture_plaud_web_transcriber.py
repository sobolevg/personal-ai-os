from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from typing import Sequence

from services.link_capture.config import PlaudWebSettings
from services.link_capture.media.base import PreparedMedia
from services.link_capture.transcription.base import TranscriptionError
from services.link_capture.transcription.plaud_web import (
    BrowserProcessResult,
    PlaudWebTranscriber,
)


class StubBrowserRunner:
    def __init__(self, result: BrowserProcessResult) -> None:
        self.result = result
        self.calls: list[tuple[tuple[str, ...], float]] = []

    async def run(
        self,
        arguments: Sequence[str],
        *,
        timeout_seconds: float,
    ) -> BrowserProcessResult:
        self.calls.append((tuple(arguments), timeout_seconds))
        return self.result


class PlaudWebTranscriberTest(unittest.IsolatedAsyncioTestCase):
    async def test_maps_browser_result_without_receiving_source_url(self) -> None:
        response = {
            "status": "success",
            "language": "ru",
            "duration_seconds": 65,
            "text": "Reverse Step-Up тренирует контроль колена.",
            "segments": [
                {
                    "start": 0,
                    "end": 31,
                    "speaker": "Speaker 1",
                    "text": "Reverse Step-Up тренирует контроль колена.",
                }
            ],
            "file_url": "https://web.plaud.ai/file/browser-owned-id",
        }
        runner = StubBrowserRunner(
            BrowserProcessResult(returncode=0, stdout=json.dumps(response))
        )

        with TemporaryDirectory() as directory:
            root = Path(directory)
            media_path = root / "audio.m4a"
            media_path.write_bytes(b"audio")
            transcriber = PlaudWebTranscriber(
                browser_python=Path("/opt/browser/bin/python"),
                profile_dir=Path("/root/.hermes/browser-profiles/plaud-web"),
                runner_script=Path("/opt/app/plaud_web_runner.py"),
                runner=runner,
            )

            result = await transcriber.transcribe_file(
                PreparedMedia(
                    path=media_path,
                    mime_type="audio/mp4",
                    size_bytes=5,
                ),
                language="ru",
            )

        self.assertEqual(result.provider, "plaud_web")
        self.assertEqual(result.segments[0].speaker, "Speaker 1")
        arguments, timeout = runner.calls[0]
        self.assertEqual(timeout, 930.0)
        self.assertIn(str(media_path), arguments)
        self.assertNotIn("instagram.com", " ".join(arguments))

    async def test_reports_authentication_required_without_page_details(self) -> None:
        runner = StubBrowserRunner(
            BrowserProcessResult(
                returncode=2,
                stdout=json.dumps({"status": "authentication_required"}),
            )
        )
        with TemporaryDirectory() as directory:
            media_path = Path(directory) / "audio.m4a"
            media_path.write_bytes(b"audio")
            transcriber = PlaudWebTranscriber(
                browser_python=Path("/opt/browser/bin/python"),
                profile_dir=Path("/root/.hermes/browser-profiles/plaud-web"),
                runner_script=Path("/opt/app/plaud_web_runner.py"),
                runner=runner,
            )

            with self.assertRaisesRegex(TranscriptionError, "authentication"):
                await transcriber.transcribe_file(
                    PreparedMedia(media_path, "audio/mp4", 5)
                )

    async def test_rejects_file_changed_after_preparation(self) -> None:
        runner = StubBrowserRunner(BrowserProcessResult(returncode=0))
        with TemporaryDirectory() as directory:
            media_path = Path(directory) / "audio.m4a"
            media_path.write_bytes(b"changed")
            transcriber = PlaudWebTranscriber(
                browser_python=Path("/opt/browser/bin/python"),
                profile_dir=Path("/root/.hermes/browser-profiles/plaud-web"),
                runner_script=Path("/opt/app/plaud_web_runner.py"),
                runner=runner,
            )

            with self.assertRaisesRegex(ValueError, "size changed"):
                await transcriber.transcribe_file(
                    PreparedMedia(media_path, "audio/mp4", 5)
                )

        self.assertEqual(runner.calls, [])


class PlaudWebSettingsTest(unittest.TestCase):
    def test_reads_vps_browser_paths_without_credentials(self) -> None:
        values = {
            "PLAUD_WEB_BROWSER_PYTHON": "/opt/browser/.venv/bin/python",
            "PLAUD_WEB_PROFILE_DIR": "/root/.hermes/profiles/plaud",
            "PLAUD_WEB_TIMEOUT_SECONDS": "600",
            "PLAUD_WEB_HEADLESS": "true",
        }
        with patch.dict(os.environ, values, clear=False):
            settings = PlaudWebSettings.from_env(None)

        self.assertEqual(
            settings.browser_python, Path("/opt/browser/.venv/bin/python")
        )
        self.assertEqual(settings.profile_dir, Path("/root/.hermes/profiles/plaud"))
        self.assertEqual(settings.timeout_seconds, 600)
        self.assertTrue(settings.headless)


if __name__ == "__main__":
    unittest.main()
