from __future__ import annotations

import json
import unittest
from pathlib import Path

from integrations.routing.capture_dispatch import build_capture_dispatch_plan

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "capture_router"
    / "dispatch_examples.json"
)


class CaptureDispatchFixturesTest(unittest.TestCase):
    def test_fixture_examples_build_expected_dispatch_plans(self) -> None:
        with FIXTURE_PATH.open(encoding="utf-8") as fixture_file:
            cases = json.load(fixture_file)

        self.assertGreater(len(cases), 0)

        for case in cases:
            with self.subTest(case=case["name"]):
                result = build_capture_dispatch_plan(
                    message=case["message"],
                    source_platform=case["source_platform"],
                    source_message_id=case["source_message_id"],
                )
                expected = case["expected"]

                self.assertEqual(result.route, expected["route"])
                self.assertEqual(result.action, expected["action"])
                self.assertEqual(result.write_policy, expected["write_policy"])
                self.assertEqual(result.needs_confirmation, expected["needs_confirmation"])
                self.assertEqual(result.target, expected["target"])
                self.assertEqual(result.source_platform, case["source_platform"])
                self.assertEqual(result.source_message_id, case["source_message_id"])

