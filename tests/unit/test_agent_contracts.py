from __future__ import annotations

import json
import unittest
from pathlib import Path

from integrations.agents.agent_contract import load_agent_contract

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENT_DIR = REPO_ROOT / "agents"

EXPECTED_AGENTS = {
    "inbox_processor",
    "task_planner",
    "knowledge_curator",
    "resource_importer",
    "weekly_review",
    "research_agent",
    "project_manager",
    "personal_assistant",
}


class AgentContractsCatalogTest(unittest.TestCase):
    def test_all_first_generation_agents_have_valid_contracts(self) -> None:
        contract_paths = sorted(AGENT_DIR.glob("*.agent.json"))
        agent_names = {path.name.replace(".agent.json", "") for path in contract_paths}

        self.assertEqual(agent_names, EXPECTED_AGENTS)

        for contract_path in contract_paths:
            with self.subTest(agent=contract_path.name):
                contract = load_agent_contract(contract_path)
                self.assertIn(contract.name, EXPECTED_AGENTS)

                self.assertTrue((REPO_ROOT / contract.data["prompt"]).exists())

                for fixture_path in contract.data["verification"]["fixtures"]:
                    full_path = REPO_ROOT / fixture_path
                    self.assertTrue(full_path.exists())
                    with full_path.open(encoding="utf-8") as fixture_file:
                        self.assertIsInstance(json.load(fixture_file), list)

                for test_path in contract.data["verification"]["unit_tests"]:
                    self.assertTrue((REPO_ROOT / test_path).exists())

    def test_agent_yaml_files_point_to_contracts(self) -> None:
        for agent_name in EXPECTED_AGENTS:
            yaml_path = AGENT_DIR / f"{agent_name}.yaml"
            contract_path = AGENT_DIR / f"{agent_name}.agent.json"

            with self.subTest(agent=agent_name):
                self.assertTrue(yaml_path.exists())
                yaml_text = yaml_path.read_text(encoding="utf-8")

                self.assertIn("status: draft", yaml_text)
                self.assertIn(f"contract: agents/{agent_name}.agent.json", yaml_text)
                self.assertTrue(contract_path.exists())

    def test_contracts_include_required_design_sections(self) -> None:
        for contract_path in sorted(AGENT_DIR.glob("*.agent.json")):
            with self.subTest(agent=contract_path.name):
                contract = load_agent_contract(contract_path)

                self.assertTrue(contract.data["purpose"])
                self.assertTrue(contract.data["inputs"])
                self.assertTrue(contract.data["outputs"])
                self.assertTrue(contract.data["tools"])
                self.assertTrue(contract.data["triggers"])
                self.assertTrue(contract.data["workflow"])
                self.assertTrue(contract.data["prompt"])
                self.assertTrue(contract.data["future_improvements"])
