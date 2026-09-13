#!/usr/bin/env python3
"""Create smc.plan.v3.6 seed with Domain and Test Asset bindings."""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
V35 = HERE / "create_plan_seed_v35.py"


def inject_before(text: str, marker: str, block: str) -> str:
    if marker not in text:
        raise ValueError(f"PLAN_SEED_MARKER_MISSING: {marker}")
    return text.replace(marker, block + "\n\n" + marker, 1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("prd", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--plan-id", required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        print(f"PLAN_ALREADY_EXISTS: {output}", file=sys.stderr)
        return 2
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".plan.md", prefix=".ges-v36-", dir=output.parent, delete=False) as handle:
        temporary = Path(handle.name)
    temporary.unlink(missing_ok=True)
    try:
        result = subprocess.run(
            [sys.executable, str(V35), str(args.prd), str(temporary), "--plan-id", args.plan_id],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
        )
        if result.returncode:
            print((result.stdout + result.stderr).strip(), file=sys.stderr)
            return result.returncode
        text = temporary.read_text(encoding="utf-8").replace(
            "plan_contract: smc.plan.v3.5", "plan_contract: smc.plan.v3.6", 1
        )
        ledger = """## Test Asset Ledger

| Verification ID | Asset ID | Kind | Path / Entrypoint | Required Capabilities | Action | Impact | Reason |
|---|---|---|---|---|---|---|---|
| V01 | <ASSET_ID_OR_NONE> | TEST | `<GROUND>` | <CAPABILITIES> | NEW | <DECIDE> | <DECIDE> |
"""
        text = inject_before(text, "## Implementation Decisions", ledger)
        output.write_text(text, encoding="utf-8")
    finally:
        temporary.unlink(missing_ok=True)
    print(
        f"Plan v3.6 seed created: {output}\nPlan ID: {args.plan_id}\n"
        "Test Asset Ledger is required for LIVE/FAULT/EXTERNAL fixtures; seed remains non-executable until grounded."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
