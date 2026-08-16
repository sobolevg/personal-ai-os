from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from services.link_capture.transcription import plaud_web_runner
from services.link_capture.transcription.plaud_web_runner import (
    _new_file_id,
    _seconds,
)


class PlaudWebRunnerTest(unittest.TestCase):
    def test_finds_only_newly_imported_file_with_expected_name(self) -> None:
        rows = [
            {"id": "new-id", "name": "hermes-instagram-audio 1m 5s"},
            {"id": "old-id", "name": "hermes-instagram-audio 1m 5s"},
        ]

        result = _new_file_id(
            {"old-id"},
            rows,
            "hermes-instagram-audio",
        )

        self.assertEqual(result, "new-id")

    def test_does_not_open_unrelated_new_file(self) -> None:
        result = _new_file_id(
            {"old-id"},
            [{"id": "new-id", "name": "another-recording"}],
            "hermes-instagram-audio",
        )

        self.assertIsNone(result)

    def test_parses_hours_minutes_and_seconds(self) -> None:
        self.assertEqual(_seconds("01:02:03"), 3723)

    def test_retries_generation_until_transcript_appears(self) -> None:
        page = MagicMock()
        page.locator.return_value.count.side_effect = [0, 0, 1]

        with (
            patch.object(plaud_web_runner, "_show_transcript"),
            patch.object(plaud_web_runner, "_log_stage"),
            patch.object(
                plaud_web_runner,
                "_start_generation_if_needed",
                return_value=False,
            ) as start,
            patch.object(
                plaud_web_runner.time,
                "monotonic",
                side_effect=[0, 1, 2, 3, 4, 5],
            ),
        ):
            plaud_web_runner._wait_for_transcript(page, deadline=100)

        self.assertEqual(start.call_count, 2)


if __name__ == "__main__":
    unittest.main()
