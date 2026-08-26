#!/usr/bin/env python3
"""Fail if committed contracts differ from freshly generated files."""

from __future__ import annotations

import filecmp
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATHS = [
    ROOT / "contracts" / "runtime-api" / "openapi.yaml",
    ROOT / "contracts" / "runtime-events" / "job-event.schema.json",
    ROOT / "contracts" / "runtime-events" / "chat-event.schema.json",
    ROOT / "contracts" / "runtime-events" / "chat-run-event.schema.json",
    ROOT / "contracts" / "runtime-events" / "error.schema.json",
]


def _run(script: str, env_pythonpath: str | None = None) -> None:
    cmd = [
        "uv",
        "run",
        "--project",
        str(ROOT / "services" / "runtime"),
        "python",
        str(ROOT / "tools" / "contract-generate" / script),
    ]
    subprocess.check_call(cmd, cwd=ROOT)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="smc-contracts-") as tmp:
        tmp_root = Path(tmp)
        # Snapshot current committed outputs
        backups: list[tuple[Path, Path]] = []
        for path in CONTRACT_PATHS:
            if not path.exists():
                print(f"Missing committed contract: {path.relative_to(ROOT)}", file=sys.stderr)
                print("Runtime contract drift detected.", file=sys.stderr)
                print("Run: npm run contracts:generate", file=sys.stderr)
                print("Commit generated contract changes.", file=sys.stderr)
                return 1
            bak = tmp_root / path.name
            shutil.copy2(path, bak)
            backups.append((path, bak))

        _run("export_openapi.py")
        _run("export_event_schemas.py")

        drifted = False
        for path, bak in backups:
            if not filecmp.cmp(path, bak, shallow=False):
                print(f"DRIFT: {path.relative_to(ROOT)}", file=sys.stderr)
                drifted = True
                # restore original for check-only mode? Leave regenerated — CI compares git.
                # Restore so `check` is non-mutating:
                shutil.copy2(bak, path)

        if drifted:
            print("Runtime contract drift detected.", file=sys.stderr)
            print("Run: npm run contracts:generate", file=sys.stderr)
            print("Commit generated contract changes.", file=sys.stderr)
            return 1

    print("[check_contract_drift] contracts are up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
