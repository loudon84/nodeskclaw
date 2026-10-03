#!/usr/bin/env python3
"""Deterministic reseal for Remote Expert / ACP / Frontend aggregate contracts.

Preserves existing manifest keys (except artifacts + bundleDigest).
Writes SHA256SUMS as UTF-8 LF, lexicographic relative paths.
consumerDigest = sha256(raw SHA256SUMS bytes).
bundleDigest follows bundle_digest_from_checksums (skips manifest.json / SHA256SUMS).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EXCLUDED_FROM_SUMS = frozenset({"SHA256SUMS"})
SKIP_BUNDLE_DIGEST_NAMES = frozenset({"manifest.json", "SHA256SUMS", "BUNDLE_DIGEST"})


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_bytes_canonical_lf(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def sha256_file(path: Path) -> str:
    if path.name == "SHA256SUMS":
        return sha256_bytes(path.read_bytes())
    return sha256_bytes(file_bytes_canonical_lf(path))


def write_text_lf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8"))


def write_json_lf(path: Path, payload: object) -> None:
    write_text_lf(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def bundle_files(root: Path) -> list[str]:
    return sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name not in EXCLUDED_FROM_SUMS
    )


def checksum_lines(root: Path) -> list[str]:
    return [f"{sha256_file(root / rel)}  {rel}" for rel in bundle_files(root)]


def bundle_digest_from_checksum_text(checksum_text: str) -> str:
    lines: list[tuple[str, str]] = []
    for raw_line in checksum_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        digest, _, relative = line.partition("  ")
        if not relative or relative in SKIP_BUNDLE_DIGEST_NAMES:
            continue
        lines.append((relative, f"{digest}  {relative}"))
    body = "\n".join(item for _, item in sorted(lines)) + "\n"
    return sha256_bytes(body.encode("utf-8"))


def seal(root: Path) -> dict[str, str]:
    root = root.resolve()
    if not root.is_dir():
        raise SystemExit(f"contract root missing: {root}")
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise SystemExit(f"manifest.json missing: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifact_rels = [
        rel
        for rel in bundle_files(root)
        if rel not in {"manifest.json", "SHA256SUMS"}
    ]
    artifacts = {rel: sha256_file(root / rel) for rel in artifact_rels}
    manifest["artifacts"] = artifacts
    write_json_lf(manifest_path, manifest)

    lines = checksum_lines(root)
    sums_text = "\n".join(lines) + "\n"
    write_text_lf(root / "SHA256SUMS", sums_text)
    bundle_digest = bundle_digest_from_checksum_text(sums_text)
    if "bundleDigest" in manifest:
        manifest["bundleDigest"] = bundle_digest
        write_json_lf(manifest_path, manifest)
        lines = checksum_lines(root)
        sums_text = "\n".join(lines) + "\n"
        write_text_lf(root / "SHA256SUMS", sums_text)
        bundle_digest = bundle_digest_from_checksum_text(sums_text)

    consumer_digest = sha256_file(root / "SHA256SUMS")
    return {
        "root": str(root.relative_to(REPO_ROOT)).replace("\\", "/"),
        "consumerDigest": consumer_digest,
        "bundleDigest": bundle_digest,
    }


DEFAULT_ROOTS = (
    "nodeskclaw-backend/contracts/remote-expert-catalog/v1.0.0",
    "nodeskclaw-acp/contracts/acp-v1-adapter/v1.1.0",
    "contracts/remote-expert-frontend/v1.0.0",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "roots",
        nargs="*",
        help="contract roots relative to repo root (default: catalog, acp, frontend)",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="repository root (default: auto-detect)",
    )
    args = parser.parse_args(argv)
    repo = args.repo_root.resolve()
    roots = args.roots or list(DEFAULT_ROOTS)
    results = []
    for rel in roots:
        path = (repo / rel).resolve() if not Path(rel).is_absolute() else Path(rel)
        if not path.exists():
            print(json.dumps({"ok": False, "error": f"missing: {rel}"}), file=sys.stderr)
            return 1
        result = seal(path)
        results.append(result)
        print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
