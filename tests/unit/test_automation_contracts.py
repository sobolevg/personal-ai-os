from __future__ import annotations

import json
import unittest
from pathlib import Path

from integrations.automations.automation_contract import load_automation_contract

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTOMATION_DIR = REPO_ROOT / "automations"
AGENT_DIR = REPO_ROOT / "agents"

EXPECTED_AUTOMATIONS = {
    "telegram_to_inbox",
    "book_import",
    "movie_import",
    "voice_notes",
    "weekly_review",
    "daily_planning",
    "project_creation",
    "knowledge_linking",
    "task_breakdown",
    "resource_classification",
}


class AutomationContractsCatalogTest(unittest.TestCase):
    def test_all_first_generation_automations_have_valid_contracts(self) -> None:
        contract_paths = sorted(AUTOMATION_DIR.glob("*.automation.json"))
        automation_names = {
            path.name.replace(".automation.json", "") for path in contract_paths
        }

        self.assertEqual(automation_names, EXPECTED_AUTOMATIONS)

        for contract_path in contract_paths:
            with self.subTest(automation=contract_path.name):
                contract = load_automation_contract(contract_path)
                self.assertIn(contract.name, EXPECTED_AUTOMATIONS)

                self.assertTrue((REPO_ROOT / contract.data["prompt"]).exists())

                for agent_name in contract.agents:
                    self.assertTrue((AGENT_DIR / f"{agent_name}.agent.json").exists())

                for fixture_path in contract.data["verification"]["fixtures"]:
                    full_path = REPO_ROOT / fixture_path
                    self.assertTrue(full_path.exists())
                    with full_path.open(encoding="utf-8") as fixture_file:
                        self.assertIsInstance(json.load(fixture_file), list)

                for test_path in contract.data["verification"]["unit_tests"]:
                    self.assertTrue((REPO_ROOT / test_path).exists())

    def test_automation_yaml_files_point_to_contracts(self) -> None:
        for automation_name in EXPECTED_AUTOMATIONS:
            yaml_path = AUTOMATION_DIR / f"{automation_name}.yaml"
            contract_path = AUTOMATION_DIR / f"{automation_name}.automation.json"

            with self.subTest(automation=automation_name):
                self.assertTrue(yaml_path.exists())
                yaml_text = yaml_path.read_text(encoding="utf-8")

                self.assertIn("status: draft", yaml_text)
                self.assertIn(
                    f"contract: automations/{automation_name}.automation.json",
                    yaml_text,
                )
                self.assertTrue(contract_path.exists())

    def test_contracts_include_required_design_sections(self) -> None:
        for contract_path in sorted(AUTOMATION_DIR.glob("*.automation.json")):
            with self.subTest(automation=contract_path.name):
                contract = load_automation_contract(contract_path)

                self.assertTrue(contract.data["purpose"])
                self.assertTrue(contract.data["inputs"])
                self.assertTrue(contract.data["outputs"])
                self.assertTrue(contract.data["agents"])
                self.assertTrue(contract.data["tools"])
                self.assertTrue(contract.data["triggers"])
                self.assertTrue(contract.data["workflow"])
                self.assertTrue(contract.data["prompt"])
                self.assertTrue(contract.data["safety_rules"])
                self.assertTrue(contract.data["future_improvements"])

