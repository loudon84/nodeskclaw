#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from common import find_repo_root, parse_top_level_frontmatter, plan_id_from_text, split_frontmatter, repo_relative_path


def body_hash(text: str) -> str:
    _, body = split_frontmatter(text)
    normalized = re.sub(r"\s+", " ", "\n".join(body)).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def candidates(root: Path) -> list[dict]:
    out = []
    plans = root / ".cursor" / "plans"
    if not plans.is_dir(): return out
    for path in sorted(plans.glob("*.plan.md")):
        try: text = path.read_text(encoding="utf-8")
        except Exception: continue
        fm = parse_top_level_frontmatter(text)
        out.append({"path": path, "plan_id": plan_id_from_text(path, text), "explicit_plan_id": fm.get("plan_id", ""), "body_hash": body_hash(text), "source_revision": fm.get("source_revision", "")})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(); g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--plan", type=Path); g.add_argument("--plan-id")
    ap.add_argument("--json", action="store_true"); args = ap.parse_args()
    root = find_repo_root(args.plan if args.plan else Path.cwd())
    rows = candidates(root)
    if args.plan:
        target = args.plan.resolve()
        if not target.is_file(): print(f"PLAN_NOT_FOUND: {target}", file=sys.stderr); return 2
        text = target.read_text(encoding="utf-8"); pid = plan_id_from_text(target, text); bh = body_hash(text)
        same_id = [r for r in rows if r["plan_id"] == pid]
        semantic = [r for r in rows if r["body_hash"] == bh]
        duplicate_paths = sorted({repo_relative_path(r["path"], root) for r in same_id + semantic if r["path"].resolve() != target})
        if duplicate_paths:
            code = "PLAN_ID_DUPLICATE" if len(same_id) > 1 else "PLAN_SEMANTIC_DUPLICATE"
            print(f"{code}: {pid}: {', '.join(duplicate_paths)}", file=sys.stderr); return 1
        result = {"plan": repo_relative_path(target, root), "plan_id": pid, "body_hash": bh}
    else:
        matches = [r for r in rows if r["plan_id"] == args.plan_id]
        if not matches: print(f"PLAN_NOT_FOUND: {args.plan_id}", file=sys.stderr); return 2
        if len(matches) > 1: print(f"PLAN_ID_DUPLICATE: {args.plan_id}: {', '.join(repo_relative_path(r['path'], root) for r in matches)}", file=sys.stderr); return 1
        r = matches[0]; result = {"plan": repo_relative_path(r["path"], root).replace("\\", "/"), "plan_id": r["plan_id"], "body_hash": r["body_hash"]}
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else result["plan"]); return 0


if __name__ == "__main__": raise SystemExit(main())
