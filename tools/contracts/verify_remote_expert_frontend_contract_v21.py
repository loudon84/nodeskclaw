#!/usr/bin/env python3
"""Verify REMOTE-EXPERT-FRONTEND-CONTRACT v2.1.0 and historical immutability of v2.0.0 / gateway v1.0.0."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

CATALOG_ROOT_REL = "nodeskclaw-backend/contracts/remote-expert-catalog/v1.1.0"
ACP_GW_ROOT_REL = "nodeskclaw-backend/contracts/remote-acp-gateway/v1.1.0"
RUNTIME_GW_ROOT_REL = "nodeskclaw-agent/contracts/acp-runtime-gateway/v1.1.0"
AGGREGATE_ROOT_REL = "contracts/remote-expert-frontend/v2.1.0"
HISTORICAL = (
    "contracts/remote-expert-frontend/v1.0.0",
    "contracts/remote-expert-frontend/v2.0.0",
    "nodeskclaw-backend/contracts/remote-acp-gateway/v1.0.0",
    "nodeskclaw-agent/contracts/acp-runtime-gateway/v1.0.0",
    "nodeskclaw-backend/contracts/remote-expert-catalog/v1.0.0",
)
FORBIDDEN_PIN_KEYS = ("acpAdapter", "remoteAgent", "acpRuntimeGateway", "Hermes")
SECRET_PATTERNS = (
    re.compile(r"(?i)authorization\s*:\s*bearer\s+\S+"),
    re.compile(r"(?i)(access_token|refresh_token|api_key|jwt_secret)\s*[:=]\s*['\"][^'\"]{8,}"),
    re.compile(r"BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY"),
)
V2_FRONTEND_DIGEST = "22ad68dd1132a073f6df5d2bf9f219b683c73ebb7ea1fa48933c9b92a744ecd5"
V1_FRONTEND_DIGEST = "598ae09bb681049b42dbca509ff32394aaed81b1b826fab243de78cd3ff090cd"
REQUIRED_ERROR_CODES = (
    "ACP_STREAM_RECONCILIATION_MISMATCH",
    "ACP_RUNTIME_SESSION_BINDING_MISSING",
    "ACP_RUNTIME_SESSION_CONTINUITY_LOST",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_sha256sums(path: Path) -> dict[str, str]:
    raw = path.read_bytes()
    if b"\r" in raw:
        raise SystemExit(f"SHA256SUMS must be LF-only: {path}")
    listed: dict[str, str] = {}
    for line in raw.decode("utf-8").splitlines():
        if not line.strip():
            continue
        digest, sep, relative = line.partition("  ")
        if sep != "  " or len(digest) != 64:
            raise SystemExit(f"invalid SHA256SUMS line in {path}: {line!r}")
        listed[relative] = digest
    return listed


def bundle_files(root: Path) -> set[str]:
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }


def file_digest(path: Path) -> str:
    if path.name == "SHA256SUMS":
        return sha256_bytes(path.read_bytes())
    return sha256_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n"))


def verify_component_checksums(root: Path) -> str:
    sums_path = root / "SHA256SUMS"
    if not sums_path.is_file():
        raise SystemExit(f"SHA256SUMS missing: {root}")
    listed = parse_sha256sums(sums_path)
    actual = bundle_files(root)
    if set(listed) != actual:
        raise SystemExit(
            f"SHA256SUMS closure mismatch under {root}: "
            f"missing={sorted(actual - set(listed))} extra={sorted(set(listed) - actual)}"
        )
    for relative, digest in listed.items():
        got = file_digest(root / relative)
        if got != digest:
            raise SystemExit(f"digest mismatch {relative} under {root}")
    return sha256_bytes(sums_path.read_bytes())


def scan_secrets(root: Path) -> None:
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in {".json", ".md"}:
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                raise SystemExit(f"secret pattern in {path}")


def verify(repo: Path) -> dict[str, object]:
    catalog = repo / CATALOG_ROOT_REL
    gateway = repo / ACP_GW_ROOT_REL
    runtime = repo / RUNTIME_GW_ROOT_REL
    aggregate = repo / AGGREGATE_ROOT_REL
    for root in (catalog, gateway, runtime, aggregate):
        if not root.is_dir():
            raise SystemExit(f"missing: {root}")
    catalog_digest = verify_component_checksums(catalog)
    gateway_digest = verify_component_checksums(gateway)
    runtime_digest = verify_component_checksums(runtime)
    aggregate_digest = verify_component_checksums(aggregate)
    pins = json.loads((aggregate / "component-pins.json").read_text(encoding="utf-8"))
    for forbidden in FORBIDDEN_PIN_KEYS:
        if forbidden in pins:
            raise SystemExit(f"forbidden pin {forbidden}")
    if set(pins) != {"remoteExpertCatalog", "remoteAcpGateway"}:
        raise SystemExit(f"unexpected pins {sorted(pins)}")
    if pins["remoteExpertCatalog"]["consumerDigest"] != catalog_digest:
        raise SystemExit("catalog pin digest mismatch")
    if pins["remoteAcpGateway"]["consumerDigest"] != gateway_digest:
        raise SystemExit("remote acp pin digest mismatch")
    if pins["remoteAcpGateway"]["version"] != "1.1.0":
        raise SystemExit("remote acp pin version must be 1.1.0")
    manifest = json.loads((aggregate / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("productionGate") != "unpassed":
        raise SystemExit("productionGate must remain unpassed until EXT-G5")
    if manifest.get("frontendContractGate") not in {"pending", "passed"}:
        raise SystemExit("invalid frontendContractGate")
    if manifest.get("contractVersion") != "2.1.0":
        raise SystemExit("aggregate contractVersion must be 2.1.0")
    consumer = json.loads((aggregate / "consumer/smc-copilot-v6.3.json").read_text(encoding="utf-8"))
    for item in ("nodeskclaw-acp.exe", "acpAdapter", "remoteAgent"):
        if item not in consumer.get("forbiddenDependencies", []):
            raise SystemExit(f"consumer missing forbidden {item}")
    handoff = aggregate / "consumer/smc-copilot-v2.1-handoff.json"
    if not handoff.is_file():
        raise SystemExit("missing consumer handoff")
    runtime_errors = json.loads((runtime / "http/error-codes.json").read_text(encoding="utf-8"))
    public_errors = json.loads((gateway / "http/error-codes.json").read_text(encoding="utf-8"))
    for code in REQUIRED_ERROR_CODES:
        if code not in runtime_errors:
            raise SystemExit(f"runtime error catalog missing {code}")
        if code not in public_errors:
            raise SystemExit(f"public error catalog missing {code}")
    v1_manifest = json.loads((repo / "contracts/remote-expert-frontend/v1.0.0/manifest.json").read_text(encoding="utf-8"))
    if v1_manifest.get("bundleDigest") != V1_FRONTEND_DIGEST:
        raise SystemExit("CONTRACT_HISTORICAL_MUTATION frontend v1.0.0")
    v2_sums = repo / "contracts/remote-expert-frontend/v2.0.0/SHA256SUMS"
    if sha256_bytes(v2_sums.read_bytes()) != V2_FRONTEND_DIGEST:
        raise SystemExit("CONTRACT_HISTORICAL_MUTATION frontend v2.0.0 digest")
    for rel in HISTORICAL:
        if not (repo / rel).is_dir():
            raise SystemExit(f"historical missing: {rel}")
        verify_component_checksums(repo / rel)
    for root in (catalog, gateway, runtime, aggregate):
        scan_secrets(root)
    if manifest.get("status") == "FROZEN" or manifest.get("frontendContractGate") == "passed":
        constants = (repo / "nodeskclaw-backend/app/contracts/remote_acp/constants.py").read_text(encoding="utf-8")
        if catalog_digest not in constants or gateway_digest not in constants or aggregate_digest not in constants:
            raise SystemExit("REMOTE_ACP_CONTRACT_MISMATCH discovery constants")
        if 'FRONTEND_CONTRACT_VERSION = "2.1.0"' not in constants:
            raise SystemExit("FRONTEND_CONTRACT_VERSION must be 2.1.0 when frozen")
    return {
        "ok": True,
        "catalogConsumerDigest": catalog_digest,
        "remoteAcpConsumerDigest": gateway_digest,
        "runtimeGatewayConsumerDigest": runtime_digest,
        "aggregateConsumerDigest": aggregate_digest,
        "frontendContractGate": manifest.get("frontendContractGate"),
        "productionGate": manifest.get("productionGate"),
        "status": manifest.get("status"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args(argv)
    try:
        result = verify(args.repo_root.resolve())
    except SystemExit as exc:
        message = str(exc)
        if message.isdigit():
            raise
        sys.stdout.write(json.dumps({"ok": False, "error": message}, ensure_ascii=False) + "\n")
        return 1
    sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
