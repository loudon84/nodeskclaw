#!/usr/bin/env python3
"""Build PG-SUMMARY / staging-prerun-SUMMARY skeleton from SMC G7 evidence JSON."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from remote_acp_v21_pins import (
    FRONTEND_CONTRACT_VERSION,
    L2_ENV_ID,
    L2_K8S_CONTEXT,
    L2_K8S_NAMESPACE,
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_from_g7(evidence: dict[str, Any], *, source_path: Path, mode: str) -> dict[str, Any]:
    topo = evidence.get("topology") or {}
    consumer = evidence.get("consumer") or {}
    cases = evidence.get("cases") or {}
    doc: dict[str, Any] = {
        "envId": topo.get("envId")
        or (L2_ENV_ID if mode == "full" else "nodeskclaw-staging"),
        "k8sContext": topo.get("k8sContext") or L2_K8S_CONTEXT,
        "namespace": topo.get("k8sNamespace")
        or (L2_K8S_NAMESPACE if mode == "full" else "nodeskclaw-staging"),
        "pin": FRONTEND_CONTRACT_VERSION,
        "g7CommitSha": consumer.get("sha") or evidence.get("commitSha"),
        "g7SourceSha256": sha256_file(source_path),
        "cases": cases,
        "productionGate": evidence.get("productionGate", "unpassed"),
        "claimAuthorized": bool(evidence.get("claimAuthorized", False)),
        "passedAt": evidence.get("passedAt"),
        "expiresAt": evidence.get("expiresAt"),
        "desktopVersion": evidence.get("desktopVersion"),
        "desktopCommit": evidence.get("desktopCommit") or consumer.get("sha"),
        "sourcePath": str(source_path).replace("\\", "/"),
        "gate": evidence.get("gate"),
        "overall": evidence.get("overall"),
        "traceIds": evidence.get("traceIds") or [],
    }
    if mode == "full" and doc["productionGate"] == "passed":
        trace = (doc["traceIds"] or [None])[0]
        doc["obsJoin"] = {
            "traceId": trace,
            "operationId": None,
            "backendLogPointer": None,
            "agentLogPointer": None,
            "smcEvidencePointer": str(source_path).replace("\\", "/"),
            "note": "Fill backend/agent log pointers before validate_pg_summary.py",
        }
    if evidence.get("claimAuthorized"):
        doc["engineeringSignoff"] = evidence.get("engineeringSignoff")
        doc["productSignoff"] = evidence.get("productSignoff")
        doc["claimAuthorizedAt"] = evidence.get("claimAuthorizedAt")
    return doc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("g7_json", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument(
        "--mode",
        choices=("full", "prerun", "auto"),
        default="auto",
    )
    args = parser.parse_args(argv)
    if not args.g7_json.is_file():
        print(json.dumps({"ok": False, "error": "missing g7 json"}))
        return 2
    evidence = json.loads(args.g7_json.read_text(encoding="utf-8"))
    mode = args.mode
    if mode == "auto":
        mode = "prerun" if evidence.get("gate") == "G7-PRERUN" else "full"
    doc = build_from_g7(evidence, source_path=args.g7_json, mode=mode)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": True, "output": str(args.output), "mode": mode}))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
