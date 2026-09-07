#!/usr/bin/env python3
"""SMC Plan v3.4 validator: structural governance + optional acceptance contract."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DELIVERY = HERE.parents[1] / "smc-plan-delivery" / "scripts"
sys.path.insert(0, str(DELIVERY))

from acceptance import validate_contract as validate_acceptance  # type: ignore
from validate_plan_v33 import validate_plan


def main() -> int:
    ap=argparse.ArgumentParser();ap.add_argument("plan",type=Path);ap.add_argument("--json",action="store_true");args=ap.parse_args();plan=args.plan.resolve()
    if not plan.is_file():
        payload={"valid":False,"plan":str(plan),"errors":[{"code":"PLAN_NOT_FOUND","detail":str(plan)}]}
        print(json.dumps(payload,ensure_ascii=False,indent=2) if args.json else f"PLAN_NOT_FOUND: {plan}",file=sys.stdout if args.json else sys.stderr);return 2
    errors=validate_plan(plan,"smc.plan.v3.4")
    errors.extend(validate_acceptance(plan))
    if args.json:print(json.dumps({"valid":not errors,"plan":str(plan),"errors":errors},ensure_ascii=False,indent=2))
    elif errors:print("\n".join(f"{e['code']}: {e['detail']}".rstrip(": ") for e in errors),file=sys.stderr)
    else:print("Plan v3.4 validation passed")
    return 1 if errors else 0

if __name__=="__main__":raise SystemExit(main())
