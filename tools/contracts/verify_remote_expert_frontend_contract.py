#!/usr/bin/env python3
"""Verify REMOTE-EXPERT-FRONTEND-CONTRACT v1.0.0 release closure.

Standard library only. Supports --repo-root for tag worktree / tamper copies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

IMPLEMENTATION_COMMIT = "896450ad479033afc2428852a2d02f70f77ab19e"
REMOTE_AGENT_DIGEST_CRLF = "c8bc0ed8a1cf5b21fcbfb743a59a2d24480ff4dc90a651e8a0b5c057ca27b18c"
REMOTE_AGENT_DIGEST_LF = "9bb6b0cd316a8ceab2824a259edfa90d033f5dcb7e56785aa0ab2698990403e3"
PRE_CLOSURE_ACP = "b4de0c63a370810403e18438618430ba8cac9bd790747d567937585812f13f8a"
PRE_CLOSURE_CATALOG = "cd38f8fbed0b41632fb0e7bbb7d6218ce6330d2cb2797555e9e6e62e14c38dba"

ACP_ROOT_REL = "nodeskclaw-acp/contracts/acp-v1-adapter/v1.1.0"
CATALOG_ROOT_REL = "nodeskclaw-backend/contracts/remote-expert-catalog/v1.0.0"
REMOTE_ROOT_REL = "nodeskclaw-backend/contracts/remote-agent/v1.5.0"
AGGREGATE_ROOT_REL = "contracts/remote-expert-frontend/v1.0.0"
CONSTANTS_REL = "nodeskclaw-acp/app/constants.py"
FIXTURES_REL = "nodeskclaw-acp/contracts/consumer-fixtures/smc-copilot-v6.3"

REQUIRED_FIXTURES = (
    "catalog.json",
    "initialize.json",
    "session-new.json",
    "session-resume.json",
    "session-close.json",
    "text-turn.json",
    "attachment-turn.json",
    "tool-call.json",
    "permission-request.json",
    "artifact-resource-link.json",
    "cancel.json",
    "remote-error.json",
)

FORBIDDEN_REQUIRED = (
    "WORK-EXPERT-CONTRACT",
    "ExpertProjectionStore",
    "expert.start",
    "skillName",
    "SkillRunStore",
    "/expert/mcp",
)

SECRET_PATTERNS = (
    re.compile(r"(?i)authorization\s*:\s*bearer\s+\S+"),
    re.compile(r"(?i)(access_token|refresh_token|api_key|jwt_secret)\s*[:=]\s*['\"][^'\"]{8,}"),
    re.compile(r"BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY"),
)

PRIVATE_PATH_RE = re.compile(
    r"(?i)([A-Z]:\\\\Users\\\\(?!Public\\)|/Users/(?!Shared)|/home/)[^\s\"']+"
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def digest_materializations(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    lf = raw.replace(b"\r\n", b"\n")
    crlf = lf.replace(b"\n", b"\r\n")
    return sha256_bytes(lf), sha256_bytes(crlf)


def parse_constant(constants_text: str, name: str) -> str:
    match = re.search(rf'{re.escape(name)} = "([0-9a-f]{{64}})"', constants_text)
    if not match:
        raise SystemExit(f"missing constant {name}")
    return match.group(1)


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


def verify_component_checksums(root: Path) -> str:
    sums_path = root / "SHA256SUMS"
    if not sums_path.is_file():
        raise SystemExit(f"SHA256SUMS missing: {root}")
    listed = parse_sha256sums(sums_path)
    actual = bundle_files(root)
    if "manifest.json" not in listed:
        raise SystemExit(f"SHA256SUMS must include manifest.json: {root}")
    if set(listed) != actual:
        raise SystemExit(
            f"SHA256SUMS closure mismatch under {root}: "
            f"missing={sorted(actual - set(listed))} extra={sorted(set(listed) - actual)}"
        )
    for relative, digest in listed.items():
        got = sha256_file(root / relative)
        if got != digest:
            raise SystemExit(f"SHA256 mismatch for {relative} under {root}")
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    artifacts = manifest.get("artifacts") or {}
    for relative, digest in artifacts.items():
        if relative == "manifest.json":
            continue
        if sha256_file(root / relative) != digest:
            raise SystemExit(f"manifest.artifacts mismatch for {relative}")
        if listed.get(relative) != digest:
            raise SystemExit(f"SHA256SUMS/manifest disagree on {relative}")
    return sha256_file(sums_path)


def scan_secrets(paths: list[Path]) -> None:
    for path in paths:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                raise SystemExit(f"secret-like pattern in {path}")
        if PRIVATE_PATH_RE.search(text):
            raise SystemExit(f"absolute private path in {path}")


def verify(repo_root: Path, *, require_frontend_passed: bool) -> dict:
    repo_root = repo_root.resolve()
    acp_root = repo_root / ACP_ROOT_REL
    catalog_root = repo_root / CATALOG_ROOT_REL
    remote_root = repo_root / REMOTE_ROOT_REL
    aggregate_root = repo_root / AGGREGATE_ROOT_REL
    constants_path = repo_root / CONSTANTS_REL
    fixtures_root = repo_root / FIXTURES_REL

    for root in (acp_root, catalog_root, remote_root, aggregate_root):
        if not root.is_dir():
            raise SystemExit(f"missing contract root: {root}")

    acp_digest = verify_component_checksums(acp_root)
    catalog_digest = verify_component_checksums(catalog_root)
    aggregate_digest = verify_component_checksums(aggregate_root)

    if acp_digest == PRE_CLOSURE_ACP or catalog_digest == PRE_CLOSURE_CATALOG:
        raise SystemExit("pre-closure candidate digest still pinned")

    acp_manifest = json.loads((acp_root / "manifest.json").read_text(encoding="utf-8"))
    catalog_manifest = json.loads((catalog_root / "manifest.json").read_text(encoding="utf-8"))
    aggregate_manifest = json.loads((aggregate_root / "manifest.json").read_text(encoding="utf-8"))
    pins = json.loads((aggregate_root / "component-pins.json").read_text(encoding="utf-8"))
    consumer = json.loads(
        (aggregate_root / "consumer/smc-copilot-v6.3.json").read_text(encoding="utf-8")
    )

    if acp_manifest.get("implementationHeadSha") != IMPLEMENTATION_COMMIT:
        raise SystemExit("ACP implementationHeadSha mismatch")
    if acp_manifest.get("releaseCommitSha") != IMPLEMENTATION_COMMIT:
        raise SystemExit("ACP releaseCommitSha mismatch")
    if catalog_manifest.get("implementationHeadSha") != IMPLEMENTATION_COMMIT:
        raise SystemExit("Catalog implementationHeadSha mismatch")
    if catalog_manifest.get("releaseCommitSha") != IMPLEMENTATION_COMMIT:
        raise SystemExit("Catalog releaseCommitSha mismatch")
    if aggregate_manifest.get("implementationCommit") != IMPLEMENTATION_COMMIT:
        raise SystemExit("aggregate implementationCommit mismatch")

    constants_text = constants_path.read_text(encoding="utf-8")
    adapter_const = parse_constant(constants_text, "ADAPTER_CONTRACT_DIGEST")
    catalog_const = parse_constant(constants_text, "CATALOG_CONTRACT_DIGEST")
    remote_const = parse_constant(constants_text, "REMOTE_AGENT_CONTRACT_DIGEST")
    if adapter_const != acp_digest:
        raise SystemExit("ADAPTER_CONTRACT_DIGEST != sha256(ACP SHA256SUMS)")
    if catalog_const != catalog_digest:
        raise SystemExit("CATALOG_CONTRACT_DIGEST != sha256(Catalog SHA256SUMS)")
    if remote_const != REMOTE_AGENT_DIGEST_CRLF:
        raise SystemExit("REMOTE_AGENT_CONTRACT_DIGEST drifted from frozen CRLF pin")

    lf_digest, crlf_digest = digest_materializations(remote_root / "SHA256SUMS")
    if REMOTE_AGENT_DIGEST_CRLF not in {lf_digest, crlf_digest}:
        raise SystemExit("Remote Agent v1.5 digest materialization missing CRLF pin")
    if REMOTE_AGENT_DIGEST_LF not in {lf_digest, crlf_digest}:
        raise SystemExit("Remote Agent v1.5 digest materialization missing LF pin")

    if acp_manifest.get("remoteAgentContractDigest") != REMOTE_AGENT_DIGEST_CRLF:
        raise SystemExit("ACP manifest remoteAgentContractDigest mismatch")
    if acp_manifest.get("catalogContractDigest") != catalog_digest:
        raise SystemExit("ACP manifest catalogContractDigest != Catalog final digest")

    components = aggregate_manifest.get("components") or {}
    if components.get("acpAdapter", {}).get("consumerDigest") != acp_digest:
        raise SystemExit("aggregate acpAdapter pin mismatch")
    if components.get("remoteExpertCatalog", {}).get("consumerDigest") != catalog_digest:
        raise SystemExit("aggregate catalog pin mismatch")
    remote_comp = components.get("remoteAgent") or {}
    if remote_comp.get("consumerDigest") != REMOTE_AGENT_DIGEST_CRLF:
        raise SystemExit("aggregate remoteAgent pin mismatch")
    if remote_comp.get("consumerDigestLfMaterialization") != REMOTE_AGENT_DIGEST_LF:
        raise SystemExit("aggregate remoteAgent LF materialization pin mismatch")

    if pins.get("acpAdapter", {}).get("consumerDigest") != acp_digest:
        raise SystemExit("component-pins acpAdapter mismatch")
    if pins.get("remoteExpertCatalog", {}).get("consumerDigest") != catalog_digest:
        raise SystemExit("component-pins catalog mismatch")

    for name in REQUIRED_FIXTURES:
        if not (fixtures_root / name).is_file():
            raise SystemExit(f"missing golden fixture: {name}")

    if consumer.get("integrationMode") != "original-chat-compose-acp":
        raise SystemExit("consumer integrationMode mismatch")
    forbidden = set(consumer.get("forbiddenDependencies") or [])
    for item in FORBIDDEN_REQUIRED:
        if item in ("WORK-EXPERT-CONTRACT", "ExpertProjectionStore", "expert.start", "skillName", "SkillRunStore"):
            if item not in forbidden:
                raise SystemExit(f"forbidden dependency not listed: {item}")
    required = set(consumer.get("requiredCapabilities") or [])
    for item in FORBIDDEN_REQUIRED:
        if item in required:
            raise SystemExit(f"forbidden capability listed as required: {item}")

    production_gate = aggregate_manifest.get("productionGate")
    if production_gate != "unpassed":
        raise SystemExit("productionGate must remain unpassed without LIVE evidence")
    frontend_gate = aggregate_manifest.get("frontendContractGate")
    if frontend_gate not in {"pending", "passed"}:
        raise SystemExit(f"invalid frontendContractGate: {frontend_gate}")
    if require_frontend_passed and frontend_gate != "passed":
        raise SystemExit("frontendContractGate must be passed")

    if acp_manifest.get("production_gate") != "unpassed":
        raise SystemExit("ACP production_gate must be unpassed")
    if catalog_manifest.get("production_gate") != "unpassed":
        raise SystemExit("Catalog production_gate must be unpassed")

    scan_paths = [
        aggregate_root / "manifest.json",
        aggregate_root / "RELEASE.md",
        aggregate_root / "component-pins.json",
        aggregate_root / "consumer/smc-copilot-v6.3.json",
        aggregate_root / "SHA256SUMS",
        acp_root / "manifest.json",
        catalog_root / "manifest.json",
    ]
    scan_secrets(scan_paths)

    return {
        "ok": True,
        "implementationCommit": IMPLEMENTATION_COMMIT,
        "acpConsumerDigest": acp_digest,
        "catalogConsumerDigest": catalog_digest,
        "remoteAgentConsumerDigest": REMOTE_AGENT_DIGEST_CRLF,
        "remoteAgentConsumerDigestLf": REMOTE_AGENT_DIGEST_LF,
        "aggregateConsumerDigest": aggregate_digest,
        "frontendContractGate": frontend_gate,
        "productionGate": production_gate,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="repository root (supports tag worktree / tamper copies)",
    )
    parser.add_argument(
        "--require-frontend-passed",
        action="store_true",
        help="fail unless aggregate frontendContractGate is passed",
    )
    args = parser.parse_args(argv)
    try:
        result = verify(args.repo_root, require_frontend_passed=args.require_frontend_passed)
    except SystemExit as exc:
        message = str(exc) if exc.args else "verification failed"
        print(json.dumps({"ok": False, "error": message}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
