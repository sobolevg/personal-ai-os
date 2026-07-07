"""Load and validate repo-owned agent contracts."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

VALID_AGENT_STATUSES = ("draft", "active")
VALID_WRITE_POLICIES = ("create_only", "draft_only", "read_only")


class AgentContractError(ValueError):
    """Raised when an agent contract is incomplete or internally inconsistent."""


@dataclass(frozen=True)
class AgentContract:
    path: Path
    data: dict[str, Any]

    @property
    def name(self) -> str:
        return str(self.data["name"])

    @property
    def allowed_actions(self) -> tuple[str, ...]:
        return tuple(self.data["routing"]["allowed_actions"])

    @property
    def allowed_routes(self) -> tuple[str, ...]:
        return tuple(self.data["routing"]["allowed_routes"])


def load_agent_contract(path: str | Path) -> AgentContract:
    contract_path = Path(path)
    with contract_path.open(encoding="utf-8") as contract_file:
        data = json.load(contract_file)

    contract = AgentContract(path=contract_path, data=data)
    validate_agent_contract(contract)
    return contract


def validate_agent_contract(contract: AgentContract) -> None:
    data = contract.data

    _require_string(data, "name")
    _require_string(data, "status")
    _require_string(data, "mission")
    _require_string(data, "prompt")

    if data["status"] not in VALID_AGENT_STATUSES:
        raise AgentContractError(
            f"agent status must be one of: {', '.join(VALID_AGENT_STATUSES)}"
        )

    _require_list(data, "inputs")
    _require_list(data, "outputs")
    _require_list(data, "safety_rules")
    _require_dict(data, "routing")
    _require_dict(data, "verification")

    routing = data["routing"]
    _require_list(routing, "allowed_routes")
    _require_list(routing, "allowed_actions")
    _require_string(routing, "default_route")

    if routing["default_route"] not in routing["allowed_routes"]:
        raise AgentContractError("routing.default_route must be in allowed_routes")

    for route, policy in routing.get("write_policies", {}).items():
        if route not in routing["allowed_routes"]:
            raise AgentContractError(f"write policy route is not allowed: {route}")
        if policy not in VALID_WRITE_POLICIES:
            raise AgentContractError(
                f"write policy must be one of: {', '.join(VALID_WRITE_POLICIES)}"
            )

    verification = data["verification"]
    _require_list(verification, "unit_tests")
    _require_list(verification, "fixtures")


def _require_string(data: dict[str, Any], key: str) -> None:
    if not isinstance(data.get(key), str) or not data[key].strip():
        raise AgentContractError(f"{key} is required")


def _require_list(data: dict[str, Any], key: str) -> None:
    if not isinstance(data.get(key), list) or not data[key]:
        raise AgentContractError(f"{key} must be a non-empty list")


def _require_dict(data: dict[str, Any], key: str) -> None:
    if not isinstance(data.get(key), dict) or not data[key]:
        raise AgentContractError(f"{key} must be a non-empty object")

