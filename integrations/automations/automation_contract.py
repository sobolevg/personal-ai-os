"""Load and validate repo-owned automation contracts."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

VALID_AUTOMATION_STATUSES = ("draft", "active")
VALID_WRITE_POLICIES = ("create_only", "draft_only", "read_only")


class AutomationContractError(ValueError):
    """Raised when an automation contract is incomplete or inconsistent."""


@dataclass(frozen=True)
class AutomationContract:
    path: Path
    data: dict[str, Any]

    @property
    def name(self) -> str:
        return str(self.data["name"])

    @property
    def agents(self) -> tuple[str, ...]:
        return tuple(self.data["agents"])


def load_automation_contract(path: str | Path) -> AutomationContract:
    contract_path = Path(path)
    with contract_path.open(encoding="utf-8") as contract_file:
        data = json.load(contract_file)

    contract = AutomationContract(path=contract_path, data=data)
    validate_automation_contract(contract)
    return contract


def validate_automation_contract(contract: AutomationContract) -> None:
    data = contract.data

    _require_string(data, "name")
    _require_string(data, "status")
    _require_string(data, "purpose")
    _require_string(data, "prompt")

    if data["status"] not in VALID_AUTOMATION_STATUSES:
        raise AutomationContractError(
            f"automation status must be one of: {', '.join(VALID_AUTOMATION_STATUSES)}"
        )

    _require_list(data, "inputs")
    _require_list(data, "outputs")
    _require_list(data, "agents")
    _require_list(data, "tools")
    _require_list(data, "triggers")
    _require_list(data, "workflow")
    _require_list(data, "safety_rules")
    _require_list(data, "future_improvements")
    _require_dict(data, "execution")
    _require_dict(data, "verification")

    execution = data["execution"]
    _require_string(execution, "mode")
    _require_string(execution, "write_policy")
    if execution["write_policy"] not in VALID_WRITE_POLICIES:
        raise AutomationContractError(
            f"write policy must be one of: {', '.join(VALID_WRITE_POLICIES)}"
        )

    verification = data["verification"]
    _require_list(verification, "fixtures")
    _require_list(verification, "unit_tests")


def _require_string(data: dict[str, Any], key: str) -> None:
    if not isinstance(data.get(key), str) or not data[key].strip():
        raise AutomationContractError(f"{key} is required")


def _require_list(data: dict[str, Any], key: str) -> None:
    if not isinstance(data.get(key), list) or not data[key]:
        raise AutomationContractError(f"{key} must be a non-empty list")


def _require_dict(data: dict[str, Any], key: str) -> None:
    if not isinstance(data.get(key), dict) or not data[key]:
        raise AutomationContractError(f"{key} must be a non-empty object")

