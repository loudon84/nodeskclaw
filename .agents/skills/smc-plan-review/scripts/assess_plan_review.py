#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

DELIVERY_SCRIPTS = Path(__file__).resolve().parents[2] / "smc-plan-delivery" / "scripts"
if str(DELIVERY_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(DELIVERY_SCRIPTS))

from common import find_repo_root, parse_top_level_frontmatter, plan_id, read_jsonl, semantic_plan_sha256  # noqa: E402

FULL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("live/fault/external acceptance", re.compile(r"\b(LIVE|FAULT_INJECTION|EXTERNAL)\b", re.I)),
    ("production owner change", re.compile(r"\bproduction\s+owner\b.*\b(change|replace|new|move|migrate)", re.I)),
    ("trust boundary", re.compile(r"\btrust[- ]boundary\b|\btrust boundary\b", re.I)),
    ("auth/security semantics", re.compile(r"\b(authentication|authorization|authn|authz|security boundary)\b", re.I)),
    ("schema/data migration", re.compile(r"\b(schema migration|database migration|data migration|migration step)\b", re.I)),
    ("protocol/contract boundary", re.compile(r"\b(new protocol|protocol change|public contract|contract boundary|wire format)\b", re.I)),
    ("concurrency/lifecycle semantics", re.compile(r"\b(concurrency|idempotenc|lease|lock ownership|lifecycle owner|cancel writer)\b", re.I)),
)


def review_records(plan: Path) -> list[dict]:
    root = find_repo_root(plan)
    path = root / ".smc" / "reviews" / f"{plan_id(plan)}.jsonl"
    return [row for row in read_jsonl(path) if row.get("kind") == "plan"]


# @lat: [[runtime-cost#GES Runtime Cost Optimization#Adaptive Plan Review]]
def classify(plan: Path) -> dict:
    text = plan.read_text(encoding="utf-8")
    fm = parse_top_level_frontmatter(text)
    current_hash = semantic_plan_sha256(plan)
    reasons: list[str] = []

    if fm.get("acceptance_contract", "").strip() == "smc.acceptance.v1":
        reasons.append("acceptance_contract=smc.acceptance.v1")

    for label, pattern in FULL_PATTERNS:
        if pattern.search(text):
            reasons.append(label)

    if reasons:
        return {
            "schema": "smc.plan.review-route.v2",
            "route": "REQUIRED",
            "depth": "FULL",
            "reasons": sorted(set(reasons)),
            "plan_sha256": current_hash,
        }

    prior = review_records(plan)
    if prior:
        latest = prior[-1]
        verdict = str(latest.get("verdict") or "").upper()
        if verdict and verdict != "PASS":
            return {
                "schema": "smc.plan.review-route.v2",
                "route": "REQUIRED",
                "depth": "FULL",
                "reasons": [f"latest prior Plan review verdict is {verdict}, not PASS"],
                "plan_sha256": current_hash,
                "prior_plan_sha256": latest.get("plan_sha256"),
            }
        if latest.get("plan_sha256") != current_hash:
            return {
                "schema": "smc.plan.review-route.v2",
                "route": "REQUIRED",
                "depth": "DELTA",
                "reasons": ["prior PASS/clearance exists and semantic Plan hash changed"],
                "plan_sha256": current_hash,
                "prior_plan_sha256": latest.get("plan_sha256"),
            }

    return {
        "schema": "smc.plan.review-route.v2",
        "route": "NOT_REQUIRED",
        "depth": "NONE",
        "reasons": ["no deterministic semantic-risk trigger"],
        "plan_sha256": current_hash,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Route SMC Plan semantic review without changing the public REQUIRED/NOT_REQUIRED contract.")
    ap.add_argument("plan", type=Path)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    plan = args.plan.resolve()
    if not plan.is_file():
        print(f"PLAN_NOT_FOUND: {plan}", file=sys.stderr)
        return 2
    try:
        result = classify(plan)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"PLAN_REVIEW_ROUTER_BLOCKED: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        # Backward-compatible stdout for existing orchestrators/documented calls.
        print(result["route"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
