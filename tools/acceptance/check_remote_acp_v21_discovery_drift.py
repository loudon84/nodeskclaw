#!/usr/bin/env python3
"""Compare Backend discovery digests against pinned v2.1.0 (A-PG-2109)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

from remote_acp_v21_pins import (
    CATALOG_CONTRACT_DIGEST,
    FRONTEND_CONTRACT_DIGEST,
    FRONTEND_CONTRACT_VERSION,
    REMOTE_ACP_CONTRACT_DIGEST,
)


def fetch_contracts(backend: str, token: str, timeout: float = 15.0) -> dict[str, Any]:
    base = backend.rstrip("/")
    url = f"{base}/api/v1/remote-experts/contracts"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
    return json.loads(body)


def compare_discovery(payload: dict[str, Any]) -> dict[str, Any]:
    expected = {
        "frontendContractVersion": FRONTEND_CONTRACT_VERSION,
        "frontendContractDigest": FRONTEND_CONTRACT_DIGEST,
        "catalogContractDigest": CATALOG_CONTRACT_DIGEST,
        "remoteAcpContractDigest": REMOTE_ACP_CONTRACT_DIGEST,
    }
    actual = {
        "frontendContractVersion": payload.get("frontendContractVersion"),
        "frontendContractDigest": payload.get("frontendContractDigest"),
        "catalogContractDigest": payload.get("catalogContractDigest"),
        "remoteAcpContractDigest": payload.get("remoteAcpContractDigest"),
    }
    mismatches = {
        key: {"expected": expected[key], "actual": actual[key]}
        for key in expected
        if actual[key] != expected[key]
    }
    return {
        "ok": not mismatches,
        "status": "OK" if not mismatches else "DRIFT",
        "expected": expected,
        "actual": actual,
        "mismatches": mismatches,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--backend",
        default=os.environ.get("SMC_REMOTE_EXPERT_G7_BACKEND_URL")
        or os.environ.get("NODESKCLAW_BACKEND_URL")
        or "",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("SMC_REMOTE_EXPERT_G7_TOKEN")
        or os.environ.get("NODESKCLAW_JWT")
        or "",
    )
    parser.add_argument("--json", action="store_true", help="print machine JSON")
    args = parser.parse_args(argv)

    if not args.backend or not args.token:
        result = {
            "ok": False,
            "status": "BLOCKED",
            "errorCode": "DRIFT_ENV_INCOMPLETE",
            "reason": "backend URL and JWT required (env or flags)",
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 2

    try:
        payload = fetch_contracts(args.backend, args.token)
    except urllib.error.HTTPError as exc:
        result = {
            "ok": False,
            "status": "FAIL",
            "errorCode": "DRIFT_HTTP_ERROR",
            "reason": f"HTTP {exc.code}",
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1
    except Exception as exc:  # noqa: BLE001 — CLI boundary
        result = {
            "ok": False,
            "status": "FAIL",
            "errorCode": "DRIFT_FETCH_FAILED",
            "reason": str(exc),
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1

    result = compare_discovery(payload)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    # Allow running as script from tools/acceptance
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    raise SystemExit(main())
