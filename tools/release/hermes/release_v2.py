"""Build smc.hermes.release.v2 self-contained Windows payload."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools.release.hermes.source_metadata import FORBIDDEN_VERSIONS, sha256_file
from tools.release.hermes.windows_runtime import assert_pe_amd64

RELEASE_V2_SCHEMA = "smc.hermes.release.v2"
RELEASE_KEY_ID = "smc-hermes-release-ed25519-v1"
SMOKE_KEY_ID = "TEST-ONLY-ed25519"
RELEASE_VERSION_RE = re.compile(r"^(?P<hermes>\d+\.\d+\.\d+)-(?P<smc>smc\.\d+)$")
FORBIDDEN_V2_NAMES = {".env", "config.yaml", "auth.json"}
FORBIDDEN_V2_PARTS = {".git", ".github", ".venv"}
REQUIRED_RUNTIME_FILES = (
    "bin/hermes.exe",
    "python/python.exe",
    "python/sqlite3.dll",
    "node/node.exe",
    "node/npm.cmd",
    "node/npx.cmd",
    "node/hermes-agent/package.json",
    "scripts/HostOperations.ps1",
    "scripts/HostOperations.psm1",
    "scripts/SmcHermesManaged.psm1",
    "config/managed.defaults.yaml",
)
CHROMIUM_FORBIDDEN_IN_RELEASE = {"chromium", ".local-chromium", "chrome-win", "chrome-linux"}


def parse_release_version(release_version: str, *, hermes_version: str = "") -> tuple[str, str, str]:
    text = str(release_version or "").strip()
    if not text or text.lower() in FORBIDDEN_VERSIONS:
        raise ValueError(f"forbidden release version: {release_version}")
    match = RELEASE_VERSION_RE.match(text)
    if not match:
        raise ValueError(f"invalid release version format: {release_version}")
    upstream = match.group("hermes")
    smc_revision = match.group("smc")
    if hermes_version and hermes_version != upstream:
        raise ValueError(f"hermes version mismatch: {hermes_version} != {upstream}")
    return text, upstream, smc_revision


def scan_release_v2_tree(root: Path) -> None:
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        parts = {part.lower() for part in rel.parts}
        if parts & FORBIDDEN_V2_PARTS:
            raise ValueError(f"forbidden path in release v2 tree: {rel}")
        if path.name.lower() in FORBIDDEN_V2_NAMES:
            raise ValueError(f"forbidden file in release v2 tree: {rel}")
        if path.is_dir() and path.name.lower() in CHROMIUM_FORBIDDEN_IN_RELEASE:
            raise ValueError(f"Chromium forbidden in release tree: {rel}")


def assert_required_runtime(root: Path) -> None:
    for rel in REQUIRED_RUNTIME_FILES:
        path = root.joinpath(*rel.split("/"))
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"missing runtime file: {rel}")
        if rel.endswith(".exe"):
            assert_pe_amd64(path)


def inventory_tree(root: Path) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix()
        key = rel.lower()
        if rel in seen or key in {item.lower() for item in seen}:
            raise ValueError(f"duplicate release path: {rel}")
        seen.add(rel)
        data = path.read_bytes()
        if not data:
            continue
        files.append({"path": rel, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    if not files:
        raise ValueError("release v2 tree is empty")
    inventory_paths = {item["path"] for item in files}
    for rel in REQUIRED_RUNTIME_FILES:
        if rel not in inventory_paths:
            raise ValueError(f"missing runtime file: {rel}")
    return files


def assemble_self_contained_tree(
    runtime_tree: Path,
    dest: Path,
    *,
    release_version: str,
    hermes_version: str,
    build_id: str,
) -> Path:
    release_version, upstream, smc_revision = parse_release_version(release_version, hermes_version=hermes_version)
    runtime_tree = runtime_tree.resolve()
    dest = dest.resolve()
    if runtime_tree != dest:
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(runtime_tree, dest)
    (dest / "manifest").mkdir(parents=True, exist_ok=True)
    (dest / "uninstall").mkdir(parents=True, exist_ok=True)
    metadata = {
        "schema": RELEASE_V2_SCHEMA,
        "releaseVersion": release_version,
        "hermesVersion": upstream,
        "smcRevision": smc_revision,
        "buildId": build_id,
    }
    (dest / "manifest" / "release-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    uninstall = dest / "uninstall" / "README.txt"
    if not uninstall.is_file() or uninstall.stat().st_size == 0:
        uninstall.write_text("SMC Hermes uninstall metadata\n", encoding="utf-8")
    assert_required_runtime(dest)
    scan_release_v2_tree(dest)
    return dest


def zip_release_tree(tree: Path, archive: Path) -> Path:
    archive.parent.mkdir(parents=True, exist_ok=True)
    if archive.exists():
        archive.unlink()
    fixed_mtime = (2020, 1, 1, 0, 0, 0)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(p for p in tree.rglob("*") if p.is_file()):
            arcname = path.relative_to(tree).as_posix()
            info = zipfile.ZipInfo(filename=arcname, date_time=fixed_mtime)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, path.read_bytes())
    return archive


def canonical_manifest_bytes(manifest: dict[str, Any]) -> bytes:
    payload = {
        "architecture": manifest["architecture"],
        "buildId": manifest["buildId"],
        "files": manifest["files"],
        "hermesVersion": manifest["hermesVersion"],
        "platform": manifest["platform"],
        "releaseVersion": manifest["releaseVersion"],
        "schema": manifest["schema"],
        "sha256": manifest["sha256"],
        "signerKeyId": manifest["signerKeyId"],
    }
    if manifest.get("smcRevision"):
        payload["smcRevision"] = manifest["smcRevision"]
    if manifest.get("sourceRevision"):
        payload["sourceRevision"] = manifest["sourceRevision"]
    if manifest.get("runtimeBuildSha256"):
        payload["runtimeBuildSha256"] = manifest["runtimeBuildSha256"]
    if manifest.get("runtime"):
        payload["runtime"] = manifest["runtime"]
    for key in (
        "capabilities",
        "managedConfigVersion",
        "runtimeProfileVersion",
        "runtimeProfile",
        "runtimeProfileDigest",
    ):
        if key in manifest:
            payload[key] = manifest[key]
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def signature_payload(manifest: dict[str, Any], artifact_digest: str) -> bytes:
    return canonical_manifest_bytes(manifest) + bytes.fromhex(artifact_digest)


def sign_release_manifest(manifest: dict[str, Any], artifact_digest: str, private_key) -> bytes:
    return private_key.sign(signature_payload(manifest, artifact_digest))


def verify_release_manifest(manifest: dict[str, Any], artifact_digest: str, signature: bytes, public_key) -> None:
    if manifest.get("schema") != RELEASE_V2_SCHEMA:
        raise ValueError("invalid release v2 schema")
    if manifest.get("sha256") != artifact_digest:
        raise ValueError("manifest sha256 mismatch")
    version = str(manifest.get("releaseVersion") or manifest.get("hermesVersion") or "")
    if version.lower() in FORBIDDEN_VERSIONS:
        raise ValueError("forbidden release version")
    files = manifest.get("files") or []
    if not files:
        raise ValueError("release manifest files missing")
    public_key.verify(signature, signature_payload(manifest, artifact_digest))


def _runtime_versions(tree: Path) -> dict[str, str]:
    meta = tree / "runtime" / "windows-runtime.json"
    if not meta.is_file():
        return {}
    data = json.loads(meta.read_text(encoding="utf-8"))
    python = str(data.get("python") or "").strip()
    node = str(data.get("node") or "").strip()
    if not python or not node:
        return {}
    result = {"python": python, "node": node}
    for key in ("sqlite", "npm", "npx"):
        val = str(data.get(key) or "").strip()
        if val:
            result[key] = val
    return result


def _runtime_capability_meta(tree: Path) -> dict[str, Any]:
    build_path = tree / "runtime" / "runtime-build.json"
    if not build_path.is_file():
        return {}
    data = json.loads(build_path.read_text(encoding="utf-8"))
    meta: dict[str, Any] = {}
    caps = data.get("capabilities")
    if isinstance(caps, dict):
        meta["capabilities"] = caps
    for key in (
        "managedConfigVersion",
        "runtimeProfileVersion",
        "runtimeProfile",
        "runtimeProfileDigest",
    ):
        if key in data:
            meta[key] = data[key]
    return meta


def build_release_manifest(
    *,
    tree: Path,
    archive: Path,
    release_version: str,
    hermes_version: str,
    build_id: str,
    source: dict[str, Any],
    signer_key_id: str,
    runtime_build_sha256: str = "",
) -> dict[str, Any]:
    _, upstream, smc_revision = parse_release_version(release_version, hermes_version=hermes_version)
    digest = sha256_file(archive)
    files = inventory_tree(tree)
    payload: dict[str, Any] = {
        "schema": RELEASE_V2_SCHEMA,
        "releaseVersion": release_version,
        "hermesVersion": upstream,
        "smcRevision": smc_revision,
        "platform": "windows",
        "architecture": "amd64",
        "sha256": digest,
        "buildId": build_id,
        "signerKeyId": signer_key_id,
        "sourceRevision": str(source.get("revision") or ""),
        "runtimeBuildSha256": runtime_build_sha256 or "",
        "files": files,
    }
    runtime = _runtime_versions(tree)
    if runtime:
        payload["runtime"] = runtime
    payload.update(_runtime_capability_meta(tree))
    return payload


def build_hermes_release_v2(
    runtime_tree: Path,
    dest: Path,
    *,
    source: dict[str, Any],
    release_version: str,
    signing_key_ref: Path | None = None,
    build_id: str = "",
) -> dict[str, Path]:
    hermes_version = str(source["version"])
    release_version, _, _ = parse_release_version(release_version, hermes_version=hermes_version)
    build_id = build_id or datetime.now(UTC).strftime("build-%Y%m%dT%H%M%SZ")
    work = dest / "release-v2"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    tree = assemble_self_contained_tree(
        runtime_tree,
        work / "tree",
        release_version=release_version,
        hermes_version=hermes_version,
        build_id=build_id,
    )
    archive = zip_release_tree(tree, work / "hermes-windows-amd64.zip")
    runtime_build_path = tree / "runtime" / "runtime-build.json"
    if not runtime_build_path.is_file():
        runtime_build_path = runtime_tree / "runtime" / "runtime-build.json"
    runtime_build_sha256 = sha256_file(runtime_build_path) if runtime_build_path.is_file() else ""
    key_id = SMOKE_KEY_ID
    private_key = None
    if signing_key_ref is not None:
        if not signing_key_ref.is_file():
            raise ValueError("signing key missing")
        from cryptography.hazmat.primitives import serialization

        private_key = serialization.load_pem_private_key(signing_key_ref.read_bytes(), password=None)
        key_id = RELEASE_KEY_ID if "TEST-ONLY" not in signing_key_ref.name else SMOKE_KEY_ID
    manifest = build_release_manifest(
        tree=tree,
        archive=archive,
        release_version=release_version,
        hermes_version=hermes_version,
        build_id=build_id,
        source=source,
        signer_key_id=key_id,
        runtime_build_sha256=runtime_build_sha256,
    )
    manifest_path = work / "release-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    sig_path = work / "release-manifest.sig"
    public_path = work / "release-public-key.pem"
    if private_key is not None:
        from cryptography.hazmat.primitives import serialization

        sig_path.write_bytes(sign_release_manifest(manifest, manifest["sha256"], private_key))
        public_path.write_bytes(
            private_key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )
    else:
        sig_path.write_bytes(b"")
    if source.get("dirty") and source.get("liveEligible"):
        raise ValueError("dirty source cannot be liveEligible")
    copied: dict[str, Path] = {}
    for item in (archive, manifest_path, sig_path):
        target = dest / item.name
        shutil.copy2(item, target)
        copied[item.name] = target
    if public_path.is_file() and public_path.stat().st_size > 0:
        target = dest / public_path.name
        shutil.copy2(public_path, target)
        copied[public_path.name] = target
    return {
        "tree": tree,
        "archive": copied.get(archive.name, archive),
        "manifest": copied.get(manifest_path.name, manifest_path),
        "signature": copied.get(sig_path.name, sig_path),
        "build_id": build_id,
    }
