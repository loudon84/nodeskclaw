#!/usr/bin/env python3
"""Dispatch a Plan to its contract-specific validator without fallback."""
from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DELIVERY = HERE.parents[1] / "smc-plan-delivery" / "scripts"
sys.path.insert(0, str(DELIVERY))

from common import parse_top_level_frontmatter  # type: ignore
from contract_resolver import validator_name  # type: ignore


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    args, passthrough = parser.parse_known_args()
    plan = args.plan.resolve()
    if not plan.is_file():
        print(f"PLAN_NOT_FOUND: {plan}", file=sys.stderr)
        return 2
    contract = parse_top_level_frontmatter(plan.read_text(encoding="utf-8")).get("plan_contract", "")
    name = validator_name(contract)
    if not name:
        print(f"PLAN_CONTRACT_UNSUPPORTED: {contract or 'missing'}", file=sys.stderr)
        return 2
    target = HERE / name
    if not target.is_file():
        print(f"PLAN_VALIDATOR_NOT_FOUND: {target}", file=sys.stderr)
        return 2
    sys.argv = [str(target), str(plan), *passthrough]
    runpy.run_path(str(target), run_name="__main__")
    return 0


if __name__ == "__main__":
    main()
