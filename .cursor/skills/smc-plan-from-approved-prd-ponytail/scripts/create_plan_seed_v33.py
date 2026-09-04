#!/usr/bin/env python3
"""Deprecated entrypoint retained for callers; new Plans are emitted as v3.4."""
import sys
from create_plan_seed import main

if __name__ == "__main__":
    print("DEPRECATED: create_plan_seed_v33.py now emits smc.plan.v3.4; use create_plan_seed.py", file=sys.stderr)
    raise SystemExit(main())
