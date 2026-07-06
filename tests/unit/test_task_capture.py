from __future__ import annotations

import json
import unittest
from pathlib import Path

from integrations.notion.task_capture import (
    TaskCaptureValidationError,
    build_task_create_payload,
)

FIXTURE_DIR = (
    Path(__file__).resolve().parents[1] / "fixtures" / "notion_task_payloads"
)


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


class TaskCapturePayloadFixturesTest(unittest.TestCase):
    def test_positive_fixtures_match_expected_payloads(self) -> None:
        input_paths = sorted(FIXTURE_DIR.glob("*.input.json"))
        positive_cases = [
            path
            for path in input_paths
            if path.with_name(path.name.replace(".input.json", ".expected.json")).exists()
        ]

        self.assertGreater(len(positive_cases), 0)

        for input_path in positive_cases:
            expected_path = input_path.with_name(
                input_path.name.replace(".input.json", ".expected.json")
            )
            with self.subTest(case=input_path.stem):
                input_payload = load_json(input_path)
                expected_payload = load_json(expected_path)

                actual_payload = build_task_create_payload(**input_payload)

                self.assertEqual(actual_payload, expected_payload)

    def test_validation_fixtures_match_expected_errors(self) -> None:
        input_paths = sorted(FIXTURE_DIR.glob("*.input.json"))
        validation_cases = [
            path
            for path in input_paths
            if path.with_name(
                path.name.replace(".input.json", ".expected_error.json")
            ).exists()
        ]

        self.assertGreater(len(validation_cases), 0)

        for input_path in validation_cases:
            expected_path = input_path.with_name(
                input_path.name.replace(".input.json", ".expected_error.json")
            )
            with self.subTest(case=input_path.stem):
                input_payload = load_json(input_path)
                expected_error = load_json(expected_path)

                with self.assertRaises(TaskCaptureValidationError) as error:
                    build_task_create_payload(**input_payload)

                self.assertEqual(str(error.exception), expected_error["error"])
