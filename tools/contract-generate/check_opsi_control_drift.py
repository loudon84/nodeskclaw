#!/usr/bin/env python3
"""Fail if committed OPSI Control OpenAPI differs from freshly generated output."""

from __future__ import annotations

import filecmp
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "contracts" / "opsi" / "openapi.yaml"


def _run_export() -> None:
    cmd = [
        "uv",
        "run",
        "--project",
        str(ROOT / "services" / "opsi-control"),
        "python",
        str(ROOT / "tools" / "contract-generate" / "export_opsi_control_openapi.py"),
    ]
    subprocess.check_call(cmd, cwd=ROOT)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="smc-opsi-contracts-") as tmp:
        tmp_root = Path(tmp)
        if not CONTRACT_PATH.exists():
            print(f"Missing committed contract: {CONTRACT_PATH.relative_to(ROOT)}", file=sys.stderr)
            return 1
        bak = tmp_root / CONTRACT_PATH.name
        shutil.copy2(CONTRACT_PATH, bak)
        _run_export()
        if not filecmp.cmp(CONTRACT_PATH, bak, shallow=False):
            print(f"DRIFT: {CONTRACT_PATH.relative_to(ROOT)}", file=sys.stderr)
            shutil.copy2(bak, CONTRACT_PATH)
            print("Run: uv run --project services/opsi-control python tools/contract-generate/export_opsi_control_openapi.py", file=sys.stderr)
            return 1
    print("[check_opsi_control_drift] contracts are up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
