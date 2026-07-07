from __future__ import annotations

import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MAP_PATH = REPO_ROOT / "docs" / "09-agent-automation-map.md"


class AgentAutomationMapTest(unittest.TestCase):
    def test_map_mentions_all_agent_and_automation_contracts(self) -> None:
        map_text = MAP_PATH.read_text(encoding="utf-8")

        for contract_path in sorted((REPO_ROOT / "agents").glob("*.agent.json")):
            with self.subTest(agent=contract_path.name):
                contract = _load_json(contract_path)
                self.assertIn(_display_name(contract["name"]), map_text)

        for contract_path in sorted(
            (REPO_ROOT / "automations").glob("*.automation.json")
        ):
            with self.subTest(automation=contract_path.name):
                contract = _load_json(contract_path)
                self.assertIn(_display_name(contract["name"]), map_text)


def _load_json(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8") as json_file:
        return json.load(json_file)


def _display_name(name: str) -> str:
    return name.replace("_", " ").title()

