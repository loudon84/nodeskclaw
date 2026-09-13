#!/usr/bin/env python3
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

DELIVERY_SCRIPTS = Path(__file__).resolve().parents[2] / "smc-plan-delivery" / "scripts"
if str(DELIVERY_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(DELIVERY_SCRIPTS))

from common import atomic_write, find_repo_root, frontmatter_end_index, plan_id, read_jsonl, semantic_plan_sha256, utc_now  # noqa: E402
from assess_plan_review import classify  # noqa: E402


def semantic_text(plan: Path) -> str:
    """Normalize only derived/runtime Cursor todo fields for semantic diffing."""
    lines = plan.read_text(encoding="utf-8").splitlines()
    end = frontmatter_end_index(lines)
    if end > 0:
        in_todos = False
        drop: set[int] = set()
        for i in range(1, end):
            line = lines[i]
            if re.match(r"^todos\s*:\s*$", line):
                in_todos = True
                continue
            if in_todos:
                if line and not line[0].isspace() and re.match(r"^[A-Za-z0-9_.-]+\s*:", line):
                    in_todos = False
                elif re.match(r"^\s+status\s*:\s*.*$", line):
                    indent = re.match(r"^(\s*)", line).group(1)
                    lines[i] = f"{indent}status: <runtime>"
                elif re.match(r"^\s+content\s*:\s*.*$", line):
                    drop.add(i)
        if drop:
            lines = [line for i, line in enumerate(lines) if i not in drop]
    return "\n".join(lines).rstrip() + "\n"


def snapshot_path(plan: Path) -> Path:
    root = find_repo_root(plan)
    return root / ".smc" / "reviews" / f"{plan_id(plan)}-semantic-snapshot.md"


def packet_path(plan: Path) -> Path:
    root = find_repo_root(plan)
    return root / ".smc" / "runs" / plan_id(plan) / "review" / "plan-semantic-review-packet.json"


def accept(plan: Path) -> Path:
    root = find_repo_root(plan)
    pid = plan_id(plan)
    ledger = root / ".smc" / "reviews" / f"{pid}.jsonl"
    rows = [row for row in read_jsonl(ledger) if row.get("kind") == "plan"]
    if not rows:
        raise ValueError("PLAN_REVIEW_SNAPSHOT_REQUIRES_REVIEW_RECORD")
    latest = rows[-1]
    current_hash = semantic_plan_sha256(plan)
    if str(latest.get("verdict") or "").upper() != "PASS" or latest.get("plan_sha256") != current_hash:
        raise ValueError("PLAN_REVIEW_SNAPSHOT_REQUIRES_FRESH_PASS")
    path = snapshot_path(plan)
    atomic_write(path, semantic_text(plan))
    return path


def build(plan: Path, requested_depth: str = "AUTO") -> dict:
    route = classify(plan)
    rank = {"NONE": 0, "DELTA": 1, "FULL": 2}
    route_depth = str(route["depth"])
    depth = route_depth if requested_depth == "AUTO" else requested_depth
    if depth not in rank:
        raise ValueError(f"PLAN_REVIEW_DEPTH_INVALID: {depth}")
    reasons = list(route.get("reasons", []))
    if rank[depth] < rank[route_depth]:
        reasons.append(f"requested depth {depth} cannot downgrade router depth {route_depth}; using {route_depth}")
        depth = route_depth

    current = semantic_text(plan)
    snap = snapshot_path(plan)
    previous = snap.read_text(encoding="utf-8") if snap.is_file() else None
    diff = ""

    if depth == "DELTA":
        if previous is None:
            depth = "FULL"
            reasons.append("DELTA requested but no prior semantic snapshot exists; fail-closed upgrade to FULL")
        else:
            diff = "".join(
                difflib.unified_diff(
                    previous.splitlines(keepends=True),
                    current.splitlines(keepends=True),
                    fromfile="prior-reviewed-plan",
                    tofile="current-plan",
                    n=5,
                )
            )
            if not diff:
                depth = "NONE"
                reasons.append("semantic snapshot equals current Plan")

    packet = {
        "schema": "smc.plan.semantic-review-packet.v1",
        "created_at": utc_now(),
        "plan_id": plan_id(plan),
        "plan_path": str(plan),
        "plan_sha256": semantic_plan_sha256(plan),
        "public_route": "NOT_REQUIRED" if depth == "NONE" else "REQUIRED",
        "review_depth": depth,
        "reasons": reasons,
        "prior_snapshot": str(snap) if previous is not None else None,
        "semantic_diff": diff if depth == "DELTA" else None,
        "changed_diff_lines": len(diff.splitlines()) if diff else 0,
        "reviewer_instruction": (
            "No model semantic review required; record content-bound router clearance."
            if depth == "NONE"
            else "Read semantic_diff and only affected closure; escalate to FULL if owner/boundary/acceptance semantics are implicated."
            if depth == "DELTA"
            else "Read the canonical Plan and approved inputs; this packet is metadata, not a second Plan."
        ),
    }
    out = packet_path(plan)
    atomic_write(out, json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return packet


def main() -> int:
    ap = argparse.ArgumentParser(description="Build/accept content-light SMC Plan semantic review packets.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("build")
    p.add_argument("plan", type=Path)
    p.add_argument("--depth", choices=("AUTO", "NONE", "DELTA", "FULL"), default="AUTO")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("accept")
    p.add_argument("plan", type=Path)
    p.add_argument("--json", action="store_true")
    args = ap.parse_args()
    plan = args.plan.resolve()
    if not plan.is_file():
        print(f"PLAN_NOT_FOUND: {plan}", file=sys.stderr)
        return 2
    try:
        if args.cmd == "accept":
            path = accept(plan)
            data = {"status": "SNAPSHOT_ACCEPTED", "path": str(path), "plan_sha256": semantic_plan_sha256(plan)}
        else:
            data = build(plan, args.depth)
            path = packet_path(plan)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"PLAN_REVIEW_PACKET_BLOCKED: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
