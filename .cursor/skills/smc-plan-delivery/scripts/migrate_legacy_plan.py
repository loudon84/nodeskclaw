#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from common import atomic_write, frontmatter_end_index, parse_top_level_frontmatter, plan_id_from_text, set_top_level_frontmatter


def slug(text: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return value[:48] or "todo"


def add_cursor_metadata(text: str, path: Path) -> str:
    lines = text.splitlines(); end = frontmatter_end_index(lines)
    if end < 0: raise ValueError("PLAN_FRONTMATTER_MISSING")
    fm = parse_top_level_frontmatter(text)
    headings = [(m.group(1).upper(), m.group(2).strip()) for m in re.finditer(r"^##\s+Todo\s+(T\d+)\s*[—-]\s*(.+?)\s*$", text, re.M)]
    existing = any(re.match(r"^todos\s*:\s*$", line) for line in lines[1:end])
    inserts = []
    if "name" not in fm: inserts.append(f"name: {path.stem.replace('.plan','')}")
    if "overview" not in fm: inserts.append("overview: SMC governed implementation plan")
    if not existing:
        inserts.append("todos:")
        for tid, title in headings:
            n = int(tid[1:])
            inserts += [f"  - id: t{n}-{slug(title)}", "    status: pending"]
    if "isProject" not in fm: inserts.append("isProject: false")
    lines[end:end] = inserts
    return "\n".join(lines).rstrip() + "\n"


def migrate_verification(text: str) -> str:
    lines = text.splitlines(); in_ver = False; header_idx = None; policy_idx = None
    for i, line in enumerate(lines):
        if line.strip() == "## Verification Ledger": in_ver = True; continue
        if in_ver and line.startswith("## "): break
        if in_ver and line.strip().startswith("|") and "Verification ID" in line and "Evidence Output" in line:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            header_idx = i; policy_idx = cells.index("Evidence Output"); cells[policy_idx] = "Evidence Policy"; lines[i] = "| " + " | ".join(cells) + " |"; continue
        if in_ver and header_idx is not None and i > header_idx + 1 and line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if policy_idx is not None and policy_idx < len(cells): cells[policy_idx] = "LOCAL_TRANSIENT"; lines[i] = "| " + " | ".join(cells) + " |"
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("plan", type=Path); ap.add_argument("--in-place", action="store_true"); ap.add_argument("--output", type=Path)
    args = ap.parse_args(); path = args.plan.resolve()
    if not path.is_file(): print(f"PLAN_NOT_FOUND: {path}", file=sys.stderr); return 2
    text = path.read_text(encoding="utf-8"); fm = parse_top_level_frontmatter(text)
    if fm.get("plan_contract") == "smc.plan.v3.3": print("PLAN_ALREADY_V33"); return 0
    pid = plan_id_from_text(path, text)
    text = set_top_level_frontmatter(text, {"plan_contract": "smc.plan.v3.3", "plan_id": pid, "commit_policy": "post_review"})
    text = add_cursor_metadata(text, path); text = migrate_verification(text)
    out = path if args.in_place else (args.output.resolve() if args.output else path.with_suffix(path.suffix + ".v33"))
    atomic_write(out, text); print(f"Migrated Plan v3.3: {out}"); return 0


if __name__ == "__main__": raise SystemExit(main())
