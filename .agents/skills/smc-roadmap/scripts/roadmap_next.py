#!/usr/bin/env python3
from __future__ import annotations
import argparse
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import validate_roadmap_v11 as vr

def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("roadmap", type=Path); args = ap.parse_args()
    path = args.roadmap.resolve()
    if not path.is_file(): print(f"ROADMAP_NOT_FOUND: {path}", file=sys.stderr); return 2
    errors = vr.validate(path)
    if errors: print("\n".join(errors), file=sys.stderr); return 1
    _, rows = vr.table(vr.section(path.read_text(encoding="utf-8"), "Roadmap Items"))
    for row in rows:
        if row["Status"].strip().upper() == "READY":
            print(f"{row['Item ID'].strip()}\t{row['Outcome'].strip()}")
            return 0
    print("ROADMAP_NO_READY_ITEM")
    return 3

if __name__ == "__main__": raise SystemExit(main())
