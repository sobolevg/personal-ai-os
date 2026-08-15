from __future__ import annotations

from collections import deque
import unittest
from unittest.mock import patch
from typing import Any, Mapping
from urllib.error import HTTPError

from services.link_capture.models import NormalizedContent, SourcePlatform
from services.link_capture.transcription.base import (
    TranscriptionError,
    TranscriptionTimeoutError,
)
from services.link_capture.transcription.plaud import (
    PlaudTranscriber,
    UrllibJsonTransport,
)


class StubJsonTransport:
    def __init__(self, responses: list[Mapping[str, Any]]) -> None:
        self.responses = deque(responses)
        self.requests: list[dict[str, Any]] = []

    async def request_json(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        payload: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        self.requests.append(
            {"method": method, "url": url, "headers": dict(headers), "payload": payload}
        )
        return self.responses.popleft()


class PlaudTranscriberTest(unittest.IsolatedAsyncioTestCase):
    async def test_submits_polls_and_maps_success_without_touching_source(self) -> None:
        transport = StubJsonTransport(
            [
                {"transcription_id": "task_exec_123", "status": "PENDING", "data": {}},
                {"transcription_id": "task_exec_123", "status": "PROGRESS", "data": {}},
                {
                    "transcription_id": "task_exec_123",
                    "status": "SUCCESS",
                    "data": {
                        "text": "Полный текст ролика",
                        "language": "ru",
                        "duration": 65.8,
                        "results": [
                            {
                                "start": 0,
                                "end": 4.2,
                                "text": "Первый фрагмент",
                                "speaker_id": "Speaker 1",
                            }
                        ],
                    },
                },
            ]
        )
        transcriber = PlaudTranscriber(
            client_id="client-test",
            api_key="api-test",
            transport=transport,
            poll_interval_seconds=0,
        )
        original = NormalizedContent.captured(
            "https://www.instagram.com/reel/ABC/?igsh=exact",
            SourcePlatform.INSTAGRAM,
            saved_at="2026-08-16T09:00:00Z",
        )

        transcript = await transcriber.transcribe(
            "https://instagram.example.fbcdn.net/video.mp4",
            language="ru",
        )

        self.assertEqual(transcript.text, "Полный текст ролика")
        self.assertEqual(transcript.language, "ru")
        self.assertEqual(transcript.duration_seconds, 65.8)
        self.assertEqual(transcript.segments[0].speaker, "Speaker 1")
        self.assertEqual(transcript.provider, "plaud")
        self.assertEqual(
            original.source_url,
            "https://www.instagram.com/reel/ABC/?igsh=exact",
        )
        self.assertEqual(len(transport.requests), 3)
        submit = transport.requests[0]
        self.assertEqual(submit["method"], "POST")
        self.assertEqual(
            submit["headers"]["User-Agent"],
            "Hermes-Link-Capture/0.1",
        )
        self.assertEqual(submit["headers"]["X-Client-Id"], "client-test")
        self.assertEqual(submit["headers"]["X-Client-Api-Key"], "api-test")
        self.assertEqual(submit["payload"]["file_url"], "https://instagram.example.fbcdn.net/video.mp4")
        self.assertEqual(
            submit["payload"]["params"]["transcribe"],
            {"language": "ru", "model": "plaud-fast-whisper"},
        )

    async def test_terminal_failure_is_reported_without_response_body(self) -> None:
        transport = StubJsonTransport(
            [{"transcription_id": "task_exec_123", "status": "FAILURE", "data": {}}]
        )
        transcriber = PlaudTranscriber(
            client_id="client-test",
            api_key="api-test",
            transport=transport,
            poll_interval_seconds=0,
        )

        with self.assertRaisesRegex(TranscriptionError, "ended with FAILURE"):
            await transcriber.transcribe("https://cdn.example.com/audio.mp3")

    async def test_timeout_is_bounded(self) -> None:
        transport = StubJsonTransport(
            [
                {"transcription_id": "task_exec_123", "status": "PENDING", "data": {}},
                {"transcription_id": "task_exec_123", "status": "PROGRESS", "data": {}},
            ]
        )
        transcriber = PlaudTranscriber(
            client_id="client-test",
            api_key="api-test",
            transport=transport,
            poll_interval_seconds=0,
            max_poll_attempts=1,
        )

        with self.assertRaises(TranscriptionTimeoutError):
            await transcriber.transcribe("https://cdn.example.com/audio.mp3")

    async def test_rejects_non_public_or_insecure_media_url(self) -> None:
        transcriber = PlaudTranscriber(
            client_id="client-test",
            api_key="api-test",
            transport=StubJsonTransport([]),
        )

        for media_url in ("http://cdn.example.com/audio.mp3", "https://localhost/a.mp3"):
            with self.subTest(media_url=media_url):
                with self.assertRaises(ValueError):
                    await transcriber.transcribe(media_url)


class UrllibJsonTransportTest(unittest.IsolatedAsyncioTestCase):
    async def test_retries_read_only_polling_request(self) -> None:
        transport = UrllibJsonTransport(retries=1, backoff_seconds=0)
        transient = HTTPError("https://api.example/task", 500, "error", {}, None)

        with patch.object(
            UrllibJsonTransport,
            "_request_json_sync",
            side_effect=[transient, {"status": "PENDING"}],
        ) as request:
            result = await transport.request_json(
                "GET",
                "https://api.example/task",
                headers={},
            )

        self.assertEqual(result, {"status": "PENDING"})
        self.assertEqual(request.call_count, 2)

    async def test_does_not_retry_non_idempotent_submit(self) -> None:
        transport = UrllibJsonTransport(retries=2, backoff_seconds=0)
        failure = HTTPError("https://api.example/tasks", 500, "error", {}, None)

        with patch.object(
            UrllibJsonTransport,
            "_request_json_sync",
            side_effect=failure,
        ) as request:
            with self.assertRaisesRegex(TranscriptionError, "HTTP 500"):
                await transport.request_json(
                    "POST",
                    "https://api.example/tasks",
                    headers={},
                    payload={"file_url": "https://cdn.example/audio.mp3"},
                )

        self.assertEqual(request.call_count, 1)


if __name__ == "__main__":
    unittest.main()
