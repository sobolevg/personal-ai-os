from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from integrations.agents.agent_contract import AgentContractError, load_agent_contract
from integrations.routing.capture_dispatch import build_capture_dispatch_plan

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = REPO_ROOT / "agents" / "personal_assistant.agent.json"


class PersonalAssistantAgentContractTest(unittest.TestCase):
    def test_contract_is_valid_and_references_existing_files(self) -> None:
        contract = load_agent_contract(CONTRACT_PATH)

        self.assertEqual(contract.name, "personal_assistant")

        referenced_paths = [contract.data["prompt"]]
        referenced_paths.extend(contract.data["verification"]["fixtures"])
        referenced_paths.extend(contract.data["verification"]["unit_tests"])

        for referenced_path in referenced_paths:
            with self.subTest(path=referenced_path):
                self.assertTrue((REPO_ROOT / referenced_path).exists())

    def test_dispatch_examples_only_use_agent_allowed_actions(self) -> None:
        contract = load_agent_contract(CONTRACT_PATH)
        fixture_path = REPO_ROOT / "tests" / "fixtures" / "capture_router" / "dispatch_examples.json"

        with fixture_path.open(encoding="utf-8") as fixture_file:
            cases = json.load(fixture_file)

        for case in cases:
            with self.subTest(case=case["name"]):
                result = build_capture_dispatch_plan(
                    message=case["message"],
                    source_platform=case["source_platform"],
                    source_message_id=case["source_message_id"],
                )

                self.assertIn(result.route, contract.allowed_routes)
                self.assertIn(result.action, contract.allowed_actions)
                self.assertEqual(
                    result.write_policy,
                    contract.data["routing"]["write_policies"][result.route],
                )

    def test_contract_validator_rejects_unknown_default_route(self) -> None:
        contract_data = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        contract_data["routing"]["default_route"] = "unknown"

        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json") as tmp:
            json.dump(contract_data, tmp)
            tmp.flush()

            with self.assertRaises(AgentContractError):
                load_agent_contract(tmp.name)
