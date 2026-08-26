"""Final verification: signature chain + OPSI read-back + secret scan."""

from __future__ import annotations

import json
import sys
import zipfile
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from tools.release.client.release_inventory import scan_secrets, sha256_file
from tools.release.hermes.path_policy_gate import (
    assert_hermes_path_policy,
    assert_path_policy_metadata,
)

ROOT = Path(__file__).resolve().parents[3]
PACKAGING = ROOT / "infra" / "opsi" / "products" / "smc-hermes-agent" / "packaging"

REQUIRED_FILES = (
    "manifests/client-release.json",
    "manifests/SHA256SUMS",
)


def _load_packaging(name: str):
    path = PACKAGING / f"{name}.py"
    spec = spec_from_file_location(f"smc_packaging_{name}", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"packaging module missing: {name}")
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_public_key(pem: bytes):
    from cryptography.hazmat.primitives.serialization import load_pem_public_key

    return load_pem_public_key(pem)


def _first(root: Path, pattern: str) -> Path:
    matches = sorted(root.glob(pattern))
    if not matches:
        raise ValueError(f"Release FAILED: missing {pattern}")
    return matches[0]


def verify_signature_chain(extracted: Path, hermes_zip: Path) -> None:
    artifact_v3 = _load_packaging("artifact_v3")
    product_release = _load_packaging("product_release")
    controller_manifest = _load_packaging("controller_manifest")
    public_pem = (extracted / "CLIENT_DATA" / "keys" / "release-public-key.pem").read_bytes()
    public = _load_public_key(public_pem)
    runtime_zip = _first(extracted, "CLIENT_DATA/artifacts/hermes-*.zip")
    runtime_man = _first(extracted, "CLIENT_DATA/artifacts/hermes-*.manifest.json")
    runtime_sig = _first(extracted, "CLIENT_DATA/artifacts/hermes-*.sig")
    manifest = json.loads(runtime_man.read_text(encoding="utf-8"))
    artifact_v3.verify_envelope(manifest, artifact_v3.sha256_file(runtime_zip), runtime_sig.read_bytes(), public)
    index = json.loads((extracted / "OPSI" / "product-release.json").read_text(encoding="utf-8"))
    product_release.verify_index(index, public)
    tree = extracted / "CLIENT_DATA" / "controller"
    signed = json.loads((tree / "controller.manifest.json").read_text(encoding="utf-8"))
    controller_manifest.verify_manifest(signed, public, tree)
    if manifest.get("sha256") != index["runtimes"][0]["artifactSha256"]:
        raise ValueError("Release FAILED: runtime artifact hash mismatch")
    if artifact_v3.sha256_file(runtime_man) != index["runtimes"][0]["manifestSha256"]:
        raise ValueError("Release FAILED: runtime manifest hash mismatch")
    build_member = None
    import zipfile

    with zipfile.ZipFile(runtime_zip) as zf:
        names = {name.replace("\\", "/"): name for name in zf.namelist()}
        if "runtime-build.json" in names:
            build_member = json.loads(zf.read(names["runtime-build.json"]))
    if build_member and build_member.get("version") != manifest.get("version"):
        raise ValueError("Release FAILED: runtime-build version mismatch")


def verify_hermes_installer_release(
    root: Path,
    *,
    require_signatures: bool = True,
    signing_key_ref: Path | None = None,
) -> dict:
    scan_secrets(root)
    missing = [rel for rel in REQUIRED_FILES if not (root / rel).is_file()]
    if missing:
        raise ValueError(f"client release incomplete: {missing}")
    manifest = json.loads((root / "manifests" / "client-release.json").read_text(encoding="utf-8"))
    if manifest.get("schema") != "smc.client-release.v1":
        raise ValueError("invalid client-release schema")
    if "hermesInstaller" not in manifest:
        raise ValueError("hermesInstaller missing from client release manifest")
    work_dir = root / "work"
    hermes_dir = root / "hermes"
    installer_dir = root / "hermes-installer"
    if not any(work_dir.glob("copilot-desktop-*-setup.exe")):
        raise ValueError("Work setup installer missing")
    release_zip = _first(hermes_dir, "hermes-windows-amd64.zip")
    release_manifest = _first(hermes_dir, "release-manifest.json")
    installer = _first(installer_dir, "smc-hermes-agent_*_windows-amd64.exe")
    msi = _first(installer_dir, "smc-hermes-agent_*_windows-amd64.msi")
    if (root / "opsi").is_dir() and list((root / "opsi").glob("*.opsi")):
        raise ValueError("Hermes installer release must not include .opsi product")
    if sha256_file(release_zip) != manifest["hermes"]["artifactSha256"]:
        raise ValueError("Hermes release artifact hash mismatch")
    if sha256_file(release_manifest) != manifest["hermes"]["manifestSha256"]:
        raise ValueError("Hermes release manifest hash mismatch")
    if sha256_file(installer) != manifest["hermesInstaller"]["sha256"]:
        raise ValueError("Hermes installer hash mismatch")
    with installer.open("rb") as fh:
        pe_header = fh.read(2)
    if pe_header != b"MZ":
        raise ValueError("Hermes installer is not a PE executable (ZIP rename forbidden)")
    with msi.open("rb") as fh:
        msi_header = fh.read(2)
    if msi_header != b"\xd0\xcf":
        raise ValueError("Hermes installer MSI is invalid")
    expected_msi = manifest["hermesInstaller"].get("msiSha256")
    if expected_msi and sha256_file(msi) != expected_msi:
        raise ValueError("Hermes installer MSI hash mismatch")
    signer = str(json.loads(release_manifest.read_text(encoding="utf-8")).get("signerKeyId") or "")
    if manifest.get("liveEligible") and signer.startswith("TEST-ONLY"):
        raise ValueError("TEST-ONLY signer cannot be liveEligible")
    if require_signatures and signing_key_ref is not None and signing_key_ref.is_file():
        from cryptography.hazmat.primitives.serialization import load_pem_private_key

        from tools.release.hermes.release_v2 import verify_release_manifest

        private = load_pem_private_key(signing_key_ref.read_bytes(), password=None)
        public = private.public_key()
        payload = json.loads(release_manifest.read_text(encoding="utf-8"))
        sig_path = hermes_dir / "release-manifest.sig"
        if sig_path.is_file() and sig_path.stat().st_size > 0:
            verify_release_manifest(
                payload,
                sha256_file(release_zip),
                sig_path.read_bytes(),
                public,
            )
    if manifest.get("liveEligible") and not require_signatures:
        raise ValueError("liveEligible requires signature chain")
    assert_hermes_path_policy()
    with zipfile.ZipFile(release_zip) as zf:
        names = {name.replace("\\", "/"): name for name in zf.namelist()}
        build_member = None
        if "runtime/runtime-build.json" in names:
            build_member = json.loads(zf.read(names["runtime/runtime-build.json"]))
        elif "runtime-build.json" in names:
            build_member = json.loads(zf.read(names["runtime-build.json"]))
        if build_member is None:
            raise ValueError("runtime-build.json missing from Hermes release archive")
        assert_path_policy_metadata(build_member)
    return manifest


def verify_client_release(
    root: Path,
    *,
    stage: Path | None = None,
    require_signatures: bool = True,
) -> dict:
    scan_secrets(root)
    missing = [rel for rel in REQUIRED_FILES if not (root / rel).is_file()]
    if missing:
        raise ValueError(f"client release incomplete: {missing}")
    manifest = json.loads((root / "manifests" / "client-release.json").read_text(encoding="utf-8"))
    if manifest.get("schema") != "smc.client-release.v1":
        raise ValueError("invalid client-release schema")
    work_dir = root / "work"
    hermes_dir = root / "hermes"
    opsi_dir = root / "opsi"
    bootstrap = root / "bootstrap"
    if not any(work_dir.glob("copilot-desktop-*-setup.exe")):
        raise ValueError("Work setup installer missing")
    hermes_zip = _first(hermes_dir, "hermes-*.zip")
    packages = list(opsi_dir.glob("*.opsi")) + list(opsi_dir.glob("*.fixture.zip"))
    if not packages:
        raise ValueError("OPSI product missing")
    opsi_pkg = packages[0]
    installer = _first(bootstrap, "opsi-client-agent-installer.exe")
    if sha256_file(hermes_zip) != manifest["hermes"]["artifactSha256"]:
        raise ValueError("Hermes artifact hash mismatch")
    if sha256_file(opsi_pkg) != manifest["opsi"]["artifactSha256"]:
        raise ValueError("OPSI artifact hash mismatch")
    if sha256_file(installer) != manifest["opsiClientAgent"]["sha256"]:
        raise ValueError("OPSI client installer hash mismatch")
    if any("private" in p.name.lower() and "public" not in p.name.lower() for p in root.rglob("*") if p.is_file()):
        raise ValueError("private material cannot be liveEligible")
    readback = _load_packaging("opsi_readback")
    extracted = Path(stage) if stage and (Path(stage) / "OPSI" / "control.toml").is_file() else None
    if require_signatures:
        extract_root = root / "opsi" / "readback"
        packed_tree = readback.extract_opsi(opsi_pkg, extract_root)
        compare_stage = extracted or packed_tree
        readback.readback_opsi(opsi_pkg, compare_stage, extract_root=root / "opsi" / "readback-verify")
        verify_signature_chain(packed_tree, hermes_zip)
    if manifest.get("liveEligible") and not require_signatures:
        raise ValueError("liveEligible requires signature chain")
    assert_hermes_path_policy()
    return manifest
