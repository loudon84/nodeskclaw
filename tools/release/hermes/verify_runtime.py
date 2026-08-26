"""Verify a Hermes managed offline bundle against runtime-build metadata."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

from tools.release.hermes.build_wheelhouse import assert_windows_amd64_wheel
from tools.release.hermes.capability_matrix import CAPABILITY_KEYS
from tools.release.hermes.path_policy_gate import assert_path_policy_metadata
from tools.release.hermes.source_metadata import FORBIDDEN_VERSIONS

FORBIDDEN_NAMES = {
    "python.exe",
    "node.exe",
    "npm.exe",
    ".env",
    "config.yaml",
}
FORBIDDEN_PARTS = {".git", ".github", ".venv", "node_modules", "tests"}
CHROMIUM_FORBIDDEN_DIR_NAMES = {"chromium", ".local-chromium", "chrome-win", "chrome-linux"}
FORBIDDEN_SUFFIXES = {".key", ".pfx", ".p12"}


def _is_allowed_node_modules(rel: Path) -> bool:
    parts = [part.lower() for part in rel.parts]
    if "node_modules" not in parts:
        return True
    # Layer B Hermes production workspace may ship node_modules.
    try:
        idx = parts.index("hermes-workspace")
    except ValueError:
        return False
    return idx >= 1 and parts[idx - 1] == "node" and "node_modules" in parts[idx + 1 :]


def scan_forbidden(root: Path) -> None:
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        parts = {part.lower() for part in rel.parts}
        blocked = parts & (FORBIDDEN_PARTS - {"node_modules"})
        if blocked:
            raise ValueError(f"forbidden path in bundle: {rel}")
        if "node_modules" in parts and not _is_allowed_node_modules(rel):
            raise ValueError(f"forbidden path in bundle: {rel}")
        name = path.name.lower()
        if name in FORBIDDEN_NAMES:
            raise ValueError(f"forbidden file in bundle: {path.name}")
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            raise ValueError(f"secret suffix in bundle: {path.name}")
        if "private-key" in name or name.endswith(".key"):
            raise ValueError(f"private key in bundle: {path.name}")


def verify_bundle_tree(root: Path) -> dict[str, Any]:
    scan_forbidden(root)
    build_path = root / "runtime-build.json"
    profile_path = root / "runtime-profile.json"
    managed_path = root / "config" / "managed.defaults.yaml"
    if not build_path.is_file():
        raise ValueError("runtime-build.json missing")
    if not profile_path.is_file():
        raise ValueError("runtime-profile.json missing")
    if not managed_path.is_file():
        raise ValueError("managed.defaults.yaml missing")
    build = json.loads(build_path.read_text(encoding="utf-8"))
    if build.get("schema") != "smc.hermes.runtime-build.v1":
        raise ValueError("invalid runtime-build schema")
    version = str(build.get("version") or "")
    if version.lower() in FORBIDDEN_VERSIONS:
        raise ValueError("forbidden hermes version")
    caps = build.get("capabilities")
    if not isinstance(caps, dict):
        raise ValueError("runtime-build capabilities missing")
    for key in CAPABILITY_KEYS:
        if key not in caps or not isinstance(caps[key], bool):
            raise ValueError(f"runtime-build capability missing/invalid: {key}")
    if not build.get("runtimeProfileDigest"):
        raise ValueError("runtimeProfileDigest missing")
    if int(build.get("managedConfigVersion") or 0) != 2:
        raise ValueError("managedConfigVersion must be 2")
    if int(build.get("runtimeProfileVersion") or 0) < 2:
        raise ValueError("runtimeProfileVersion must be >= 2")
    profile_meta = json.loads(profile_path.read_text(encoding="utf-8"))
    if profile_meta.get("schema") != "smc.hermes.runtime-profile.v2":
        raise ValueError("invalid runtime-profile schema")
    if profile_meta.get("digest") != build.get("runtimeProfileDigest"):
        raise ValueError("runtime profile digest mismatch")
    managed_text = managed_path.read_text(encoding="utf-8")
    if "smc.opsi.managed-config.v2" not in managed_text:
        raise ValueError("managed.defaults.yaml schema missing")
    if "keys: {}" in managed_text and "defaults:" not in managed_text:
        raise ValueError("managed.defaults.yaml still empty v1 artifact")
    wheels = list((root / "python" / "wheels").glob("*.whl"))
    if not wheels:
        raise ValueError("missing python dependency")
    for wheel in wheels:
        assert_windows_amd64_wheel(wheel.name)
    app_wheels = list((root / "app").glob("*.whl"))
    if not app_wheels:
        raise ValueError("hermes wheel missing")
    node_packages = list((root / "node" / "packages").glob("*.tgz"))
    expected_node = int((build.get("node") or {}).get("packageCount") or 0)
    if expected_node and len(node_packages) < expected_node:
        raise ValueError("missing node dependency")
    if build.get("source", {}).get("dirty") and build.get("liveEligible"):
        raise ValueError("dirty source cannot be liveEligible")
    assert_path_policy_metadata(build)
    return build


def verify_bundle_zip(archive: Path) -> dict[str, Any]:
    with zipfile.ZipFile(archive) as zf:
        for name in zf.namelist():
            lowered = name.replace("\\", "/").lower()
            parts = [part for part in lowered.split("/") if part]
            blocked = set(parts) & (FORBIDDEN_PARTS - {"node_modules"})
            if blocked:
                raise ValueError(f"forbidden path in bundle: {name}")
            if "node_modules" in parts and not _is_allowed_node_modules(Path(*parts)):
                raise ValueError(f"forbidden path in bundle: {name}")
            base = Path(name).name.lower()
            if base in FORBIDDEN_NAMES:
                raise ValueError(f"forbidden file in bundle: {name}")
    extract = archive.parent / f"{archive.stem}-verify"
    extract.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(extract)
    return verify_bundle_tree(extract)
