#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import validate_roadmap_v11 as validator


def cells(line: str) -> list[str]:
    return [x.strip() for x in line.strip().strip("|").split("|")]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("roadmap", type=Path)
    ap.add_argument("item_id")
    ap.add_argument("--status", required=True)
    ap.add_argument("--prd")
    ap.add_argument("--plan")
    ap.add_argument("--implementation-commit")
    ap.add_argument("--verification")
    args = ap.parse_args()

    path = args.roadmap.resolve()
    if not path.is_file():
        print(f"ROADMAP_NOT_FOUND: {path}", file=sys.stderr)
        return 2
    original = path.read_text(encoding="utf-8")
    lines = original.splitlines()
    header = None
    table_index = None
    for i, line in enumerate(lines):
        if line.strip().startswith("|") and "Item ID" in line and "Verification Evidence" in line:
            header = cells(line)
            table_index = i
            break
    if header is None or table_index is None:
        print("ROADMAP_TABLE_MISSING", file=sys.stderr)
        return 1
    try:
        idx = {key: header.index(key) for key in header}
    except ValueError as exc:
        print(f"ROADMAP_COLUMN_MISSING: {exc}", file=sys.stderr)
        return 1

    found = False
    for i in range(table_index + 2, len(lines)):
        if not lines[i].strip().startswith("|"):
            break
        values = cells(lines[i])
        if len(values) != len(header):
            continue
        if values[idx["Item ID"]].strip() == args.item_id:
            found = True
            values[idx["Status"]] = args.status.upper()
            for arg, column in (
                (args.prd, "PRD"),
                (args.plan, "Plan"),
                (args.implementation_commit, "Implementation Commit"),
                (args.verification, "Verification Evidence"),
            ):
                if arg is not None:
                    values[idx[column]] = arg
            lines[i] = "| " + " | ".join(values) + " |"
            break
    if not found:
        print(f"ROADMAP_ITEM_NOT_FOUND: {args.item_id}", file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    for i, line in enumerate(lines[:40]):
        if line.startswith("updated_at:"):
            lines[i] = f"updated_at: {now}"
            break
    candidate = "\n".join(lines) + "\n"
    path.write_text(candidate, encoding="utf-8")

    errors = validator.validate(path, check_git=True, check_architecture=True)
    if errors:
        path.write_text(original, encoding="utf-8")
        print("ROADMAP_UPDATE_REJECTED", file=sys.stderr)
        print("\n".join(errors), file=sys.stderr)
        return 1

    print(f"Roadmap updated: {args.item_id} -> {args.status.upper()}")
    print(f"Suggested commit: chore(roadmap): update {args.item_id} to {args.status.upper()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
