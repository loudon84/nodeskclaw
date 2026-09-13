"""Single contract-to-validator resolver shared by Delivery runtime gates."""
from __future__ import annotations

from pathlib import Path

CURRENT_PLAN_CONTRACT = "smc.plan.v3.6"
VALIDATORS = {
    "smc.plan.v3.3": "validate_plan_v33.py",
    "smc.plan.v3.4": "validate_plan_v34.py",
    "smc.plan.v3.5": "validate_plan_v35.py",
    "smc.plan.v3.6": "validate_plan_v36.py",
}


# @lat: [[plan-delivery#Plan Contract Resolution]]
def validator_name(contract: str) -> str | None:
    """Return the only valid static validator for a supported Plan contract."""
    return VALIDATORS.get(contract)


def validator_path(root: Path, contract: str) -> Path | None:
    name = validator_name(contract)
    if not name:
        return None
    return root / ".agents" / "skills" / "smc-plan-validator" / "scripts" / name
