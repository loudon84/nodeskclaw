#!/usr/bin/env python3
"""Validate Production Gate SUMMARY JSON (A-PG-2107 / A-PG-2108 / A-PG-2100)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from remote_acp_v21_pins import (
    CLAIM_WINDOW_DAYS,
    FRONTEND_CONTRACT_VERSION,
    FULL_LIVE_IDS,
    L2_ENV_ID,
    L2_K8S_CONTEXT,
    L2_K8S_NAMESPACE,
    PRERUN_LIVE_IDS,
)

SECRET_RE = re.compile(
    r"(?:authorization\s*:\s*bearer\s+\S+|Bearer\s+[A-Za-z0-9._\-+/=]{8,}"
    r"|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,})",
    re.I,
)

URL_RE = re.compile(r"https?://[^\s\"']+", re.I)


def _parse_iso(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def validate_summary(doc: dict[str, Any], *, mode: str) -> list[str]:
    errors: list[str] = []
    required_common = [
        "envId",
        "k8sContext",
        "namespace",
        "pin",
        "g7CommitSha",
        "g7SourceSha256",
        "cases",
        "productionGate",
        "claimAuthorized",
    ]
    for key in required_common:
        if key not in doc:
            errors.append(f"missing field: {key}")

    if doc.get("pin") != FRONTEND_CONTRACT_VERSION:
        errors.append(f"pin must be {FRONTEND_CONTRACT_VERSION}")

    cases = doc.get("cases") or {}
    if not isinstance(cases, dict):
        errors.append("cases must be object")
        cases = {}

    if mode == "prerun":
        expected_ids = PRERUN_LIVE_IDS
        if doc.get("productionGate") != "unpassed":
            errors.append("prerun productionGate must be unpassed")
        if doc.get("claimAuthorized") is not False:
            errors.append("prerun claimAuthorized must be false")
    else:
        expected_ids = FULL_LIVE_IDS
        if doc.get("envId") != L2_ENV_ID:
            errors.append(f"envId must be {L2_ENV_ID}")
        if doc.get("k8sContext") != L2_K8S_CONTEXT:
            errors.append(f"k8sContext must be {L2_K8S_CONTEXT}")
        if doc.get("namespace") != L2_K8S_NAMESPACE:
            errors.append(f"namespace must be {L2_K8S_NAMESPACE}")

    for case_id in expected_ids:
        status = cases.get(case_id)
        if status != "PASS":
            errors.append(f"case {case_id} must be PASS, got {status!r}")
    extra = set(cases) - set(expected_ids)
    if extra and mode == "prerun":
        errors.append(f"prerun cases must not include extras: {sorted(extra)}")

    blob = json.dumps(doc, ensure_ascii=False)
    if SECRET_RE.search(blob):
        errors.append("secret material detected in summary")
    # Backend URL must not appear; env var name is fine
    if URL_RE.search(blob):
        errors.append("raw URL must not appear in summary")

    if mode == "full":
        if doc.get("productionGate") == "passed":
            for key in ("passedAt", "expiresAt", "obsJoin"):
                if key not in doc or doc[key] in (None, "", {}):
                    errors.append(f"missing field for passed gate: {key}")
            if doc.get("passedAt") and doc.get("expiresAt"):
                try:
                    passed = _parse_iso(str(doc["passedAt"]))
                    expires = _parse_iso(str(doc["expiresAt"]))
                    expected = passed + timedelta(days=CLAIM_WINDOW_DAYS)
                    delta = abs((expires - expected).total_seconds())
                    if delta > 2:
                        errors.append("expiresAt must be passedAt + 14 days")
                except ValueError as exc:
                    errors.append(f"invalid passedAt/expiresAt: {exc}")
            obs = doc.get("obsJoin") or {}
            if not isinstance(obs, dict) or not obs.get("traceId"):
                errors.append("obsJoin.traceId required when productionGate=passed")
            if not obs.get("backendLogPointer") or not obs.get("agentLogPointer"):
                errors.append("obsJoin backend/agent log pointers required")

        if doc.get("claimAuthorized") is True:
            for key in (
                "desktopVersion",
                "desktopCommit",
                "engineeringSignoff",
                "productSignoff",
            ):
                if not doc.get(key):
                    errors.append(f"claimAuthorized requires {key}")
            if doc.get("productionGate") != "passed":
                errors.append("claimAuthorized requires productionGate=passed")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="PG-SUMMARY or staging-prerun-SUMMARY path")
    parser.add_argument(
        "--mode",
        choices=("full", "prerun", "auto"),
        default="auto",
    )
    args = parser.parse_args(argv)

    if not args.path.is_file():
        print(json.dumps({"ok": False, "error": f"missing file {args.path}"}))
        return 2

    doc = json.loads(args.path.read_text(encoding="utf-8"))
    mode = args.mode
    if mode == "auto":
        name = args.path.name.lower()
        mode = "prerun" if "prerun" in name or "staging" in name else "full"

    errors = validate_summary(doc, mode=mode)
    result = {"ok": not errors, "mode": mode, "errors": errors, "path": str(args.path)}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
