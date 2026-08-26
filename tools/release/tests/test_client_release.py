from __future__ import annotations

import json
import re
import subprocess
import zipfile
from pathlib import Path

import pytest

from tools.release.client.build_client_release import build_all
from tools.release.client.release_inventory import scan_secrets
from tools.release.client.verify_client_release import verify_client_release, verify_hermes_installer_release

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
except ImportError:  # pragma: no cover
    Ed25519PrivateKey = None

ROOT = Path(__file__).resolve().parents[2]


def _git(repo: Path, *args: str) -> None:
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or "git failed")


def _hermes_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "hermes-agent"
    repo.mkdir()
    (repo / "pyproject.toml").write_text('[project]\nname = "hermes-agent"\nversion = "0.22.0"\n', encoding="utf-8")
    (repo / "uv.lock").write_text("version = 1\nrequires-python = '>=3.12'\n", encoding="utf-8")
    _git(repo, "init")
    _git(repo, "config", "user.email", "builder@example.com")
    _git(repo, "config", "user.name", "builder")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "freeze")
    return repo


def _write_config(path: Path, hermes_repo: Path, installer: Path) -> Path:
    path.write_text(
        "\n".join(
            [
                "schema: smc.client-release.config.v1",
                "release:",
                '  version: "1.7.1"',
                '  channel: "lab"',
                "clientRuntime:",
                "  platform: windows",
                "  architecture: amd64",
                "  python:",
                '    version: "3.12"',
                '    range: ">=3.12,<3.13"',
                "  node:",
                '    version: "22"',
                '    range: ">=22,<23"',
                "work:",
                "  enabled: true",
                "hermes:",
                f'  repo: "{hermes_repo.as_posix()}"',
                "  version: auto",
                "  profile: smc-managed",
                "opsi:",
                '  productVersion: "1.7.1"',
                '  packageVersion: "1"',
                '  controllerRevision: "2"',
                "  buildMode: native",
                "external:",
                f'  opsiClientInstaller: "{installer.as_posix()}"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def _key_ref(tmp_path: Path) -> Path:
    from cryptography.hazmat.primitives import serialization

    private = Ed25519PrivateKey.generate()
    key_ref = tmp_path / "TEST-ONLY-release.pem"
    key_ref.write_bytes(
        private.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    return key_ref


def _installer_managed_runtime_build() -> str:
    return json.dumps(
        {
            "schema": "smc.hermes.runtime-build.v1",
            "environment": {
                "path": {
                    "policy": "installer-managed",
                    "owner": "windows-installer",
                    "entries": [r"D:\Programs\SMC\Hermes\bin"],
                }
            },
        }
    )


def _write_fake_msi(path: Path) -> Path:
    path.write_bytes(b"\xd0\xcf" + b"\0" * 126)
    return path


def _fake_hermes_release_v2(dest: Path, *, signer_key_id: str = "TEST-ONLY-ed25519") -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    archive = dest / "hermes-windows-amd64.zip"
    manifest = dest / "release-manifest.json"
    sig = dest / "release-manifest.sig"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("bin/hermes.exe", b"@echo off\r\necho 0.22.0\r\n")
        zf.writestr("runtime/runtime-build.json", _installer_managed_runtime_build())
    manifest.write_text(
        json.dumps(
            {
                "schema": "smc.hermes.release.v2",
                "releaseVersion": "0.22.0-smc.1",
                "hermesVersion": "0.22.0",
                "sha256": __import__("hashlib").sha256(archive.read_bytes()).hexdigest(),
                "signerKeyId": signer_key_id,
                "files": [],
            }
        ),
        encoding="utf-8",
    )
    sig.write_bytes(b"")
    return archive


def _inputs(tmp_path: Path) -> dict[str, Path]:
    hermes_repo = _hermes_repo(tmp_path)
    work = tmp_path / "work-dist"
    work.mkdir()
    (work / "copilot-desktop-1.7.1-setup.exe").write_bytes(b"setup")
    (work / "copilot-desktop-1.7.1-portable.exe").write_bytes(b"portable")
    hermes = tmp_path / "hermes-0.22.0-windows.zip"
    with zipfile.ZipFile(hermes, "w") as zf:
        zf.writestr("hermes.exe", b"SMOKE-HERMES-CLI 0.22.0\n")
        zf.writestr("README.txt", b"fixture")
    installer = tmp_path / "opsi-client-agent-installer.exe"
    installer.write_bytes(b"opsi-client")
    config = _write_config(tmp_path / "client-release.yaml", hermes_repo, installer)
    return {
        "config": config,
        "hermes_repo": hermes_repo,
        "work": work,
        "hermes": hermes,
        "installer": installer,
        "key": _key_ref(tmp_path),
    }


def test_rb14_secret_scan_fails(tmp_path: Path):
    dest = tmp_path / "rel"
    dest.mkdir()
    (dest / ".env").write_text("SECRET=1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="secret"):
        scan_secrets(dest)


def test_rb15_final_release_ready(tmp_path: Path, monkeypatch):
    if Ed25519PrivateKey is None:
        pytest.skip("cryptography required")
    from tools.release.client import build_client_release as bcr

    monkeypatch.setattr(
        bcr,
        "freeze_smc",
        lambda allow_dirty: {"revision": "a" * 40, "dirty": False, "liveEligible": True},
    )
    paths = _inputs(tmp_path)
    dest = bcr.build_all(
        config_path=paths["config"],
        output=tmp_path / "dist",
        hermes_repo=paths["hermes_repo"],
        opsi_client_installer=paths["installer"],
        signing_key_ref=paths["key"],
        allow_dirty=True,
        work_dist=paths["work"],
        hermes_zip=paths["hermes"],
        opsi_tooling="zipfile",
        mode="offline",
    )
    manifest = json.loads((dest / "manifests" / "client-release.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == "smc.client-release.v1"
    assert manifest["liveEligible"] is True
    assert manifest["buildStatus"] == "success"
    assert manifest["certificationStatus"] == "uncertified"
    verified = verify_client_release(dest, stage=dest / "opsi" / "stage", require_signatures=True)
    assert verified["liveEligible"] is True
    assert any((dest / "opsi").glob("*.fixture.zip"))


def test_hermes_installer_release_without_opsi(tmp_path: Path, monkeypatch):
    if Ed25519PrivateKey is None:
        pytest.skip("cryptography required")
    from tools.release.client import build_client_release as bcr
    from tools.release.client import release_inventory as ri

    monkeypatch.setattr(ri, "authenticode_status", lambda _path: "NotSigned")
    monkeypatch.setattr(
        bcr,
        "freeze_smc",
        lambda allow_dirty: {"revision": "a" * 40, "dirty": False, "liveEligible": True},
    )
    paths = _inputs(tmp_path)
    config_text = paths["config"].read_text(encoding="utf-8") + "\nhermesInstaller:\n  enabled: true\n  releaseVersion: \"0.22.0-smc.1\"\n"
    config_path = tmp_path / "client-release-v2.yaml"
    config_path.write_text(config_text, encoding="utf-8")
    fake_installer = tmp_path / "smc-hermes-agent_0.22.0-smc.1_windows-amd64.exe"
    # Minimal MZ stub so release gates reject ZIP-rename while unit tests stay offline.
    fake_installer.write_bytes(b"MZ" + b"\0" * 126)
    _write_fake_msi(fake_installer.with_suffix(".msi"))

    def _fake_bundle(repo, dest, **kwargs):
        return _fake_hermes_release_v2(dest, signer_key_id="TEST-ONLY-ed25519")

    monkeypatch.setattr(bcr, "build_managed_bundle", _fake_bundle)
    dest = bcr.build_hermes_installer_release(
        config_path=config_path,
        output=tmp_path / "dist",
        hermes_repo=paths["hermes_repo"],
        signing_key_ref=paths["key"],
        allow_dirty=True,
        work_dist=paths["work"],
        installer_exe=fake_installer,
        smoke_installer=False,
    )
    manifest = json.loads((dest / "manifests" / "client-release.json").read_text(encoding="utf-8"))
    assert manifest["hermesInstaller"]["sha256"]
    assert "opsi" not in manifest
    assert not list((dest / "opsi").glob("*.opsi"))
    verify_hermes_installer_release(dest, require_signatures=True, signing_key_ref=paths["key"])
    assert manifest.get("liveEligible") is False


def test_hermes_installer_rejects_renamed_zip(tmp_path: Path):
    from tools.release.client.build_client_release import _is_pe_executable, _is_msi_package

    renamed = tmp_path / "smc-hermes-agent_0.22.0-smc.1_windows-amd64.exe"
    with zipfile.ZipFile(renamed, "w") as zf:
        zf.writestr("bootstrap.ps1", "exit 0")
    assert not _is_pe_executable(renamed)
    msi = tmp_path / "smc-hermes-agent_0.22.0-smc.1_windows-amd64.msi"
    msi.write_bytes(b"not-an-msi")
    assert not _is_msi_package(msi)


def test_hermes_installer_smoke_and_test_key_not_live(tmp_path: Path, monkeypatch):
    if Ed25519PrivateKey is None:
        pytest.skip("cryptography required")
    from tools.release.client import build_client_release as bcr
    from tools.release.client import release_inventory as ri

    monkeypatch.setattr(ri, "authenticode_status", lambda _path: "NotSigned")
    monkeypatch.setattr(
        bcr,
        "freeze_smc",
        lambda allow_dirty: {"revision": "a" * 40, "dirty": False, "liveEligible": True},
    )
    paths = _inputs(tmp_path)
    config_text = (
        paths["config"].read_text(encoding="utf-8")
        + "\nhermesInstaller:\n  enabled: true\n  releaseVersion: \"0.22.0-smc.1\"\n"
    )
    config_path = tmp_path / "client-release-v2-smoke.yaml"
    config_path.write_text(config_text, encoding="utf-8")
    fake_installer = tmp_path / "smc-hermes-agent_0.22.0-smc.1_windows-amd64.exe"
    fake_installer.write_bytes(b"MZ" + b"\0" * 126)
    _write_fake_msi(fake_installer.with_suffix(".msi"))

    def _fake_bundle(repo, dest, **kwargs):
        return _fake_hermes_release_v2(dest, signer_key_id="TEST-ONLY-ed25519")

    monkeypatch.setattr(bcr, "build_managed_bundle", _fake_bundle)

    def _capture(src, dest):
        dest.mkdir(parents=True, exist_ok=True)
        target = dest / src.name
        target.write_bytes(src.read_bytes())
        meta = {
            "name": src.name,
            "sha256": __import__("hashlib").sha256(target.read_bytes()).hexdigest(),
            "bytes": target.stat().st_size,
            "authenticodeStatus": "Valid",
            "version": "0.22.0-smc.1",
        }
        msi_src = src.with_suffix(".msi")
        if msi_src.is_file():
            msi_dest = dest / msi_src.name
            msi_dest.write_bytes(msi_src.read_bytes())
            meta["msiSha256"] = __import__("hashlib").sha256(msi_dest.read_bytes()).hexdigest()
        return meta

    monkeypatch.setattr(bcr, "capture_hermes_installer", _capture)
    dest = bcr.build_hermes_installer_release(
        config_path=config_path,
        output=tmp_path / "dist",
        hermes_repo=paths["hermes_repo"],
        signing_key_ref=paths["key"],
        allow_dirty=True,
        work_dist=paths["work"],
        installer_exe=fake_installer,
        smoke_installer=True,
    )
    manifest = json.loads((dest / "manifests" / "client-release.json").read_text(encoding="utf-8"))
    assert manifest["liveEligible"] is False


def test_hermes_installer_unsigned_not_live(tmp_path: Path, monkeypatch):
    if Ed25519PrivateKey is None:
        pytest.skip("cryptography required")
    from tools.release.client import build_client_release as bcr
    from tools.release.client import release_inventory as ri

    monkeypatch.setattr(ri, "authenticode_status", lambda _path: "NotSigned")
    monkeypatch.setattr(
        bcr,
        "freeze_smc",
        lambda allow_dirty: {"revision": "a" * 40, "dirty": False, "liveEligible": True},
    )
    paths = _inputs(tmp_path)
    config_text = (
        paths["config"].read_text(encoding="utf-8")
        + "\nhermesInstaller:\n  enabled: true\n  releaseVersion: \"0.22.0-smc.1\"\n"
    )
    config_path = tmp_path / "client-release-v2-unsigned.yaml"
    config_path.write_text(config_text, encoding="utf-8")
    fake_installer = tmp_path / "smc-hermes-agent_0.22.0-smc.1_windows-amd64.exe"
    fake_installer.write_bytes(b"MZ" + b"\0" * 126)
    _write_fake_msi(fake_installer.with_suffix(".msi"))

    def _fake_bundle(repo, dest, **kwargs):
        return _fake_hermes_release_v2(dest, signer_key_id="smc-hermes-release-ed25519-v1")

    def _capture(src, dest):
        dest.mkdir(parents=True, exist_ok=True)
        target = dest / src.name
        target.write_bytes(src.read_bytes())
        meta = {
            "name": src.name,
            "sha256": __import__("hashlib").sha256(target.read_bytes()).hexdigest(),
            "bytes": target.stat().st_size,
            "authenticodeStatus": "NotSigned",
            "version": "0.22.0-smc.1",
        }
        msi_src = src.with_suffix(".msi")
        if msi_src.is_file():
            msi_dest = dest / msi_src.name
            msi_dest.write_bytes(msi_src.read_bytes())
            meta["msiSha256"] = __import__("hashlib").sha256(msi_dest.read_bytes()).hexdigest()
        return meta

    monkeypatch.setattr(bcr, "build_managed_bundle", _fake_bundle)
    monkeypatch.setattr(bcr, "capture_hermes_installer", _capture)
    dest = bcr.build_hermes_installer_release(
        config_path=config_path,
        output=tmp_path / "dist",
        hermes_repo=paths["hermes_repo"],
        signing_key_ref=paths["key"],
        allow_dirty=True,
        work_dist=paths["work"],
        installer_exe=fake_installer,
        smoke_installer=False,
    )
    manifest = json.loads((dest / "manifests" / "client-release.json").read_text(encoding="utf-8"))
    assert manifest["liveEligible"] is False


def test_hermes_installer_verifier_exception_fail_closed(tmp_path: Path, monkeypatch):
    if Ed25519PrivateKey is None:
        pytest.skip("cryptography required")
    from tools.release.client import build_client_release as bcr
    from tools.release.client import release_inventory as ri

    monkeypatch.setattr(ri, "authenticode_status", lambda _path: "NotSigned")
    monkeypatch.setattr(
        bcr,
        "freeze_smc",
        lambda allow_dirty: {"revision": "a" * 40, "dirty": False, "liveEligible": True},
    )
    paths = _inputs(tmp_path)
    config_text = (
        paths["config"].read_text(encoding="utf-8")
        + "\nhermesInstaller:\n  enabled: true\n  releaseVersion: \"0.22.0-smc.1\"\n"
    )
    config_path = tmp_path / "client-release-v2-verify-fail.yaml"
    config_path.write_text(config_text, encoding="utf-8")
    fake_installer = tmp_path / "smc-hermes-agent_0.22.0-smc.1_windows-amd64.exe"
    fake_installer.write_bytes(b"MZ" + b"\0" * 126)
    _write_fake_msi(fake_installer.with_suffix(".msi"))

    def _fake_bundle(repo, dest, **kwargs):
        return _fake_hermes_release_v2(dest, signer_key_id="TEST-ONLY-ed25519")

    def _capture(src, dest):
        dest.mkdir(parents=True, exist_ok=True)
        target = dest / src.name
        target.write_bytes(src.read_bytes())
        meta = {
            "name": src.name,
            "sha256": __import__("hashlib").sha256(target.read_bytes()).hexdigest(),
            "bytes": target.stat().st_size,
            "authenticodeStatus": "NotSigned",
            "version": "0.22.0-smc.1",
        }
        msi_src = src.with_suffix(".msi")
        if msi_src.is_file():
            msi_dest = dest / msi_src.name
            msi_dest.write_bytes(msi_src.read_bytes())
            meta["msiSha256"] = __import__("hashlib").sha256(msi_dest.read_bytes()).hexdigest()
        return meta

    monkeypatch.setattr(bcr, "build_managed_bundle", _fake_bundle)
    monkeypatch.setattr(bcr, "capture_hermes_installer", _capture)

    def _boom(*args, **kwargs):
        raise ValueError("verifier exception")

    monkeypatch.setattr(bcr, "verify_hermes_installer_release", _boom)
    with pytest.raises((ValueError, SystemExit)):
        bcr.build_hermes_installer_release(
            config_path=config_path,
            output=tmp_path / "dist",
            hermes_repo=paths["hermes_repo"],
            signing_key_ref=paths["key"],
            allow_dirty=True,
            work_dist=paths["work"],
            installer_exe=fake_installer,
            smoke_installer=False,
        )


def test_stage_all_does_not_require_prebuilt_opsi(tmp_path: Path, monkeypatch):
    if Ed25519PrivateKey is None:
        pytest.skip("cryptography required")
    from tools.release.client import build_client_release as bcr

    monkeypatch.setattr(
        bcr,
        "freeze_smc",
        lambda allow_dirty: {"revision": "a" * 40, "dirty": False, "liveEligible": True},
    )
    paths = _inputs(tmp_path)
    dest = build_all(
        config_path=paths["config"],
        output=tmp_path / "dist",
        hermes_repo=paths["hermes_repo"],
        opsi_client_installer=paths["installer"],
        signing_key_ref=paths["key"],
        allow_dirty=True,
        work_dist=paths["work"],
        hermes_zip=paths["hermes"],
        opsi_pkg=None,
        opsi_tooling="zipfile",
    )
    assert dest.is_dir()
    assert list((dest / "opsi").glob("*.fixture.zip"))

def test_powershell_wrapper_stage_parity_with_python() -> None:
    from tools.release.client.build_client_release import STAGES

    wrapper = (ROOT.parent / "scripts" / "build-client-release.ps1").read_text(encoding="utf-8")
    match = re.search(r"ValidateSet\(([^)]+)\)", wrapper)
    assert match, "PowerShell ValidateSet missing"
    ps_stages = [part.strip().strip('"') for part in match.group(1).split(",")]
    assert tuple(ps_stages) == STAGES


def test_hermes_installer_verify_rejects_immutable_path_policy(tmp_path: Path, monkeypatch):
    if Ed25519PrivateKey is None:
        pytest.skip("cryptography required")
    from tools.release.client import build_client_release as bcr
    from tools.release.client import release_inventory as ri

    monkeypatch.setattr(ri, "authenticode_status", lambda _path: "NotSigned")
    monkeypatch.setattr(
        bcr,
        "freeze_smc",
        lambda allow_dirty: {"revision": "a" * 40, "dirty": False, "liveEligible": True},
    )
    paths = _inputs(tmp_path)
    config_text = (
        paths["config"].read_text(encoding="utf-8")
        + '\nhermesInstaller:\n  enabled: true\n  releaseVersion: "0.22.0-smc.1"\n'
    )
    config_path = tmp_path / "client-release-immutable.yaml"
    config_path.write_text(config_text, encoding="utf-8")
    fake_installer = tmp_path / "smc-hermes-agent_0.22.0-smc.1_windows-amd64.exe"
    fake_installer.write_bytes(b"MZ" + b"\0" * 126)
    _write_fake_msi(fake_installer.with_suffix(".msi"))

    def _fake_bundle(repo, dest, **kwargs):
        dest.mkdir(parents=True, exist_ok=True)
        archive = dest / "hermes-windows-amd64.zip"
        manifest = dest / "release-manifest.json"
        sig = dest / "release-manifest.sig"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("bin/hermes.exe", b"cli")
            zf.writestr(
                "runtime/runtime-build.json",
                json.dumps(
                    {
                        "schema": "smc.hermes.runtime-build.v1",
                        "environment": {"path": {"policy": "immutable"}},
                    }
                ),
            )
        manifest.write_text(
            json.dumps(
                {
                    "schema": "smc.hermes.release.v2",
                    "releaseVersion": "0.22.0-smc.1",
                    "hermesVersion": "0.22.0",
                    "sha256": __import__("hashlib").sha256(archive.read_bytes()).hexdigest(),
                    "signerKeyId": "TEST-ONLY-ed25519",
                    "files": [],
                }
            ),
            encoding="utf-8",
        )
        sig.write_bytes(b"")
        return archive

    monkeypatch.setattr(bcr, "build_managed_bundle", _fake_bundle)
    with pytest.raises((ValueError, SystemExit), match="installer-managed|fields invalid|Release FAILED"):
        bcr.build_hermes_installer_release(
            config_path=config_path,
            output=tmp_path / "dist",
            hermes_repo=paths["hermes_repo"],
            signing_key_ref=paths["key"],
            allow_dirty=True,
            work_dist=paths["work"],
            installer_exe=fake_installer,
            smoke_installer=False,
        )
