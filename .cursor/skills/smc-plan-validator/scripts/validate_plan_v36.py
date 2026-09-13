#!/usr/bin/env python3
"""SMC Plan v3.6 validator: v3.5 plus durable Test Asset binding."""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DELIVERY = HERE.parents[1] / "smc-plan-delivery" / "scripts"
sys.path.insert(0, str(DELIVERY))

from acceptance import validate_contract as validate_acceptance  # type: ignore
from test_assets import validate_plan as validate_test_assets  # type: ignore
from validate_plan_v33 import validate_plan  # type: ignore


def repo_root(plan: Path) -> Path:
    path = plan.resolve().parent
    for candidate in (path, *path.parents):
        if (candidate / ".agents").is_dir() or (candidate / ".git").exists():
            return candidate
    raise ValueError("DOMAIN_REPO_ROOT_NOT_FOUND")


def domain_module(plan: Path):
    target = repo_root(plan) / ".agents" / "ges" / "domain-runtime" / "domain_runtime.py"
    if not target.is_file():
        raise ValueError(f"DOMAIN_RUNTIME_MISSING: {target}")
    spec = importlib.util.spec_from_file_location("ges_domain_runtime_validate_v36", target)
    if spec is None or spec.loader is None:
        raise ValueError("DOMAIN_RUNTIME_IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    plan = args.plan.resolve()
    if not plan.is_file():
        payload = {"valid": False, "plan": str(plan), "errors": [{"code": "PLAN_NOT_FOUND", "detail": str(plan)}]}
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else f"PLAN_NOT_FOUND: {plan}")
        return 2
    errors = validate_plan(plan, "smc.plan.v3.6")
    errors.extend(validate_acceptance(plan))
    errors.extend(validate_test_assets(plan))
    try:
        errors.extend(domain_module(plan).validate_plan(plan))
    except ValueError as exc:
        errors.append({"code": str(exc).split(":", 1)[0], "detail": str(exc)})
    if args.json:
        print(json.dumps({"valid": not errors, "plan": str(plan), "errors": errors}, ensure_ascii=False, indent=2))
    elif errors:
        print("\n".join(f"{error['code']}: {error['detail']}".rstrip(": ") for error in errors), file=sys.stderr)
    else:
        print("Plan v3.6 validation passed")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
