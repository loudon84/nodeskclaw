#!/usr/bin/env python3
"""Freeze Remote ACP v2.1 aggregates and update Backend discovery constants.

Run only after G1-G3 PASS on the same release train. Rewrites:
- contract manifests status=FROZEN / frontendContractGate=passed
- implementation SHAs
- nodeskclaw-backend/app/contracts/remote_acp/constants.py digests
Then reseals bundles.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CONSTANTS = REPO / "nodeskclaw-backend" / "app" / "contracts" / "remote_acp" / "constants.py"
ROOTS = (
    "nodeskclaw-agent/contracts/acp-runtime-gateway/v1.1.0",
    "nodeskclaw-backend/contracts/remote-acp-gateway/v1.1.0",
    "contracts/remote-expert-frontend/v2.1.0",
)


def _seal(rel: str) -> dict:
    proc = subprocess.run(
        [sys.executable, str(REPO / "tools/contracts/seal_remote_expert_contracts.py"), rel],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(proc.stderr or proc.stdout)
    return json.loads(proc.stdout.strip().splitlines()[-1])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--implementation-sha", required=True)
    args = parser.parse_args(argv)
    sha = args.implementation_sha.strip().lower()
    if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
        raise SystemExit("implementation-sha must be 40-hex")

    for rel in ROOTS:
        path = REPO / rel / "manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if "implementationHeadSha" in manifest:
            manifest["implementationHeadSha"] = sha
        if "releaseCommitSha" in manifest:
            manifest["releaseCommitSha"] = sha
        if "implementationCommit" in manifest:
            manifest["implementationCommit"] = sha
        manifest["status"] = "FROZEN"
        if "frontendContractGate" in manifest:
            manifest["frontendContractGate"] = "passed"
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    sealed = {item["root"]: item for item in (_seal(rel) for rel in ROOTS)}
    runtime = sealed["nodeskclaw-agent/contracts/acp-runtime-gateway/v1.1.0"]
    gateway = sealed["nodeskclaw-backend/contracts/remote-acp-gateway/v1.1.0"]
    aggregate = sealed["contracts/remote-expert-frontend/v2.1.0"]

    pins_path = REPO / "contracts/remote-expert-frontend/v2.1.0/component-pins.json"
    pins = json.loads(pins_path.read_text(encoding="utf-8"))
    pins["remoteAcpGateway"]["consumerDigest"] = gateway["consumerDigest"]
    pins_path.write_text(json.dumps(pins, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    aggregate = _seal("contracts/remote-expert-frontend/v2.1.0")

    text = CONSTANTS.read_text(encoding="utf-8")
    replacements = {
        r'FRONTEND_CONTRACT_VERSION = "[^"]+"': 'FRONTEND_CONTRACT_VERSION = "2.1.0"',
        r'FRONTEND_CONTRACT_DIGEST = "[^"]+"': f'FRONTEND_CONTRACT_DIGEST = "{aggregate["consumerDigest"]}"',
        r'REMOTE_ACP_CONTRACT_VERSION = "[^"]+"': 'REMOTE_ACP_CONTRACT_VERSION = "1.1.0"',
        r'REMOTE_ACP_CONTRACT_DIGEST = "[^"]+"': f'REMOTE_ACP_CONTRACT_DIGEST = "{gateway["consumerDigest"]}"',
    }
    for pattern, value in replacements.items():
        text, n = re.subn(pattern, value, text, count=1)
        if n != 1:
            raise SystemExit(f"failed to rewrite constants for {pattern}")
    CONSTANTS.write_text(text, encoding="utf-8")

    verify = subprocess.run(
        [sys.executable, str(REPO / "tools/contracts/verify_remote_expert_frontend_contract_v21.py")],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    sys.stdout.write(verify.stdout)
    if verify.returncode != 0:
        sys.stderr.write(verify.stderr)
        return verify.returncode
    print(
        json.dumps(
            {
                "ok": True,
                "runtime": runtime["consumerDigest"],
                "gateway": gateway["consumerDigest"],
                "aggregate": aggregate["consumerDigest"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
