from __future__ import annotations

import json
import unittest
from pathlib import Path

from integrations.routing.capture_router import (
    VALID_ROUTES,
    route_capture_message,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "capture_router"
    / "examples.json"
)


class CaptureRouterFixturesTest(unittest.TestCase):
    def test_fixture_examples_route_to_expected_targets(self) -> None:
        with FIXTURE_PATH.open(encoding="utf-8") as fixture_file:
            cases = json.load(fixture_file)

        self.assertGreater(len(cases), 0)

        for case in cases:
            with self.subTest(case=case["name"]):
                result = route_capture_message(case["message"])
                expected = case["expected"]

                self.assertIn(result.route, VALID_ROUTES)
                self.assertEqual(result.route, expected["route"])
                self.assertEqual(result.confidence, expected["confidence"])
                self.assertEqual(result.target, expected["target"])
                self.assertIsInstance(result.signals, tuple)

    def test_message_text_is_normalized(self) -> None:
        result = route_capture_message("  todo:   renew    passport  ")

        self.assertEqual(result.normalized_text, "todo: renew passport")

