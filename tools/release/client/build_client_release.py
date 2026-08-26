"""Unified client release orchestrator (R00-R18)."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.release.client.release_config import load_release_config  # noqa: E402
from tools.release.subprocess_text import command_output, run_command
from tools.release.client.release_inventory import (  # noqa: E402
    capture_hermes_installer,
    capture_opsi_client_installer,
    capture_work_installers,
    scan_secrets,
    sha256_file,
    write_json,
    write_sha256sums,
)
from tools.release.client.release_manifest import build_client_release_manifest  # noqa: E402
from tools.release.client.verify_client_release import verify_client_release, verify_hermes_installer_release  # noqa: E402
from tools.release.hermes.build_runtime import build_managed_bundle  # noqa: E402
from tools.release.hermes.release_version import resolve_from_source, smc_revision_from_config  # noqa: E402
from tools.release.hermes.source_metadata import freeze_source  # noqa: E402

STAGES = (
    "preflight",
    "work",
    "hermes",
    "hermes-installer",
    "runtime",
    "opsi-stage",
    "opsi-package",
    "assemble",
    "verify",
    "all",
)
MAKEPACKAGE = ROOT / "infra" / "opsi" / "products" / "smc-hermes-agent" / "packaging" / "makepackage.py"
HERMES_INSTALLER_SCRIPT = ROOT / "infra" / "windows" / "hermes-agent" / "installer" / "build.ps1"


def _run(cmd: list[str], cwd: Path | None = None) -> None:
    result = run_command(cmd, cwd=cwd)
    if result.returncode != 0:
        raise SystemExit(command_output(result, "command failed"))


def load_makepackage():
    spec = spec_from_file_location("smc_makepackage", MAKEPACKAGE)
    if spec is None or spec.loader is None:
        raise SystemExit("makepackage.py missing")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def freeze_smc(allow_dirty: bool) -> dict[str, Any]:
    result = run_command(["git", "rev-parse", "HEAD"], cwd=ROOT)
    porcelain = run_command(["git", "status", "--porcelain"], cwd=ROOT)
    dirty = bool(porcelain.stdout.strip())
    if dirty and not allow_dirty:
        raise ValueError("dirty smc-copilot source is forbidden for production builds")
    revision = (result.stdout or "").strip()
    if len(revision) < 7:
        raise ValueError("smc-copilot git revision missing")
    return {"revision": revision, "dirty": dirty, "liveEligible": not dirty}


def stage_root(output: Path, version: str, build_id: str) -> Path:
    path = output / "client-release" / version / build_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def run_work(config: dict[str, Any], dest: Path, *, work_dist: Path | None, runner=_run) -> dict[str, Any]:
    if not config["work"].get("enabled"):
        raise ValueError("Work build is required for client release")
    if work_dist is None:
        runner(["npx", "nx", "run", "work:package-win"], cwd=ROOT)
        work_dist = ROOT / "apps" / "work" / "dist"
    return capture_work_installers(work_dist, dest / "work")


def run_preflight(config: dict[str, Any], *, allow_dirty: bool, hermes_repo: Path | None) -> dict[str, Any]:
    smc = freeze_smc(allow_dirty)
    repo = Path(hermes_repo or config["hermes"]["repo"])
    hermes = freeze_source(
        repo,
        hermes_version="" if config["hermes"]["version"] == "auto" else str(config["hermes"]["version"]),
        allow_dirty=allow_dirty,
    )
    return {"smc": smc, "hermes": hermes}


def copy_release_v2_artifacts(hermes_build_dir: Path, dest: Path) -> dict[str, Any]:
    hermes_dir = dest / "hermes"
    hermes_dir.mkdir(parents=True, exist_ok=True)
    copied: dict[str, Path] = {}
    for name in ("hermes-windows-amd64.zip", "release-manifest.json", "release-manifest.sig", "release-public-key.pem"):
        src = hermes_build_dir / name
        if src.is_file():
            target = hermes_dir / name
            if src.resolve() != target.resolve():
                shutil.copy2(src, target)
            copied[name] = target
    archive = copied.get("hermes-windows-amd64.zip", hermes_dir / "hermes-windows-amd64.zip")
    manifest = copied.get("release-manifest.json", hermes_dir / "release-manifest.json")
    manifest_sha = sha256_file(manifest) if manifest.is_file() else ("00" * 32)
    manifest_data = json.loads(manifest.read_text(encoding="utf-8")) if manifest.is_file() else {}
    return {
        "artifactSha256": sha256_file(archive) if archive.is_file() else ("00" * 32),
        "manifestSha256": manifest_sha,
        "version": str(manifest_data.get("hermesVersion") or manifest_data.get("releaseVersion") or ""),
        "releaseVersion": str(manifest_data.get("releaseVersion") or ""),
    }


def _is_pe_executable(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            return fh.read(2) == b"MZ"
    except OSError:
        return False


def _is_msi_package(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            return fh.read(2) == b"\xd0\xcf"
    except OSError:
        return False


def run_hermes_installer(
    dest: Path,
    *,
    release_version: str,
    smoke: bool = True,
    payload_source: Path | None = None,
) -> Path:
    if not HERMES_INSTALLER_SCRIPT.is_file():
        raise ValueError("hermes installer build script missing")
    out = dest / "hermes-installer-build"
    out.mkdir(parents=True, exist_ok=True)
    cmd = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(HERMES_INSTALLER_SCRIPT),
        "-ReleaseVersion",
        release_version,
        "-OutputDir",
        str(out),
    ]
    if smoke:
        cmd.append("-Smoke")
    elif payload_source is not None:
        cmd.extend(["-PayloadSource", str(payload_source)])
    result = run_command(cmd)
    if result.returncode != 0:
        raise SystemExit(command_output(result, "hermes installer build failed"))
    matches = sorted(out.glob("smc-hermes-agent_*_windows-amd64.exe"))
    if not matches:
        raise SystemExit("Release FAILED: hermes installer exe missing")
    exe = matches[0]
    if not _is_pe_executable(exe):
        raise SystemExit("Release FAILED: hermes installer is not a PE executable (ZIP rename forbidden)")
    msi_matches = sorted(out.glob("smc-hermes-agent_*_windows-amd64.msi"))
    if not msi_matches or not _is_msi_package(msi_matches[0]):
        raise SystemExit("Release FAILED: hermes installer MSI missing or invalid")
    return exe


def copy_runtime_artifacts(hermes_zip: Path, dest: Path) -> dict[str, Any]:
    hermes_dir = dest / "hermes"
    hermes_dir.mkdir(parents=True, exist_ok=True)
    copied = hermes_dir / hermes_zip.name
    if hermes_zip.resolve() != copied.resolve():
        shutil.copy2(hermes_zip, copied)
    manifest = hermes_zip.with_name(hermes_zip.name.replace(".zip", ".manifest.json"))
    sig = hermes_zip.with_name(hermes_zip.name.replace(".zip", ".sig"))
    manifest_dest = hermes_dir / manifest.name
    manifest_sha = ""
    if manifest.is_file():
        if manifest.resolve() != manifest_dest.resolve():
            shutil.copy2(manifest, manifest_dest)
        manifest_sha = sha256_file(manifest_dest)
    if sig.is_file():
        sig_dest = hermes_dir / sig.name
        if sig.resolve() != sig_dest.resolve():
            shutil.copy2(sig, sig_dest)
    return {
        "artifactSha256": sha256_file(copied),
        "manifestSha256": manifest_sha or ("00" * 32),
        "version": hermes_zip.name.split("-")[1] if "-" in hermes_zip.name else "",
    }


def copy_opsi_package(opsi_pkg: Path, dest: Path) -> dict[str, Any]:
    opsi_dir = dest / "opsi"
    opsi_dir.mkdir(parents=True, exist_ok=True)
    copied = opsi_dir / opsi_pkg.name
    if opsi_pkg.resolve() != copied.resolve():
        shutil.copy2(opsi_pkg, copied)
    sha_file = opsi_pkg.with_name(opsi_pkg.name + ".sha256")
    if sha_file.is_file():
        sha_dest = opsi_dir / sha_file.name
        if sha_file.resolve() != sha_dest.resolve():
            shutil.copy2(sha_file, sha_dest)
    return {"artifactSha256": sha256_file(copied)}


def run_hermes(
    config: dict[str, Any],
    dest: Path,
    *,
    hermes_repo: Path | None,
    allow_dirty: bool,
    mode: str,
    wheelhouse: Path | None,
    node_root: Path | None,
    hermes_zip: Path | None,
    wheelhouse_downloader=None,
    release_version: str = "",
    signing_key_ref: Path | None = None,
) -> Path:
    if hermes_zip is not None:
        return hermes_zip
    repo = Path(hermes_repo or config["hermes"]["repo"])
    archive = build_managed_bundle(
        repo,
        dest / "hermes-build",
        profile_name=str(config["hermes"]["profile"]),
        hermes_version="" if config["hermes"]["version"] == "auto" else str(config["hermes"]["version"]),
        allow_dirty=allow_dirty,
        wheelhouse=wheelhouse,
        node_root=node_root,
        mode=mode,
        wheelhouse_downloader=wheelhouse_downloader,
        release_version=release_version,
        signing_key_ref=signing_key_ref,
        smc_revision=smc_revision_from_config(config),
    )
    return archive


def run_opsi_pipeline(
    config: dict[str, Any],
    dest: Path,
    *,
    hermes_zip: Path,
    signing_key_ref: Path,
    opsi_tooling: str,
    stop_after: str = "package",
) -> dict[str, Any]:
    make = load_makepackage()
    prepared = make.prepare_release_stage(
        dest / "opsi-build",
        hermes_zip,
        signing_key_ref,
        hermes_version="" if config["hermes"]["version"] == "auto" else str(config["hermes"]["version"]),
        product_version=str(config["opsi"]["productVersion"]),
        package_version=str(config["opsi"]["packageVersion"]),
        controller_revision=str(config["opsi"]["controllerRevision"]),
    )
    stage = prepared["stage"]
    stage_copy = dest / "opsi" / "stage"
    if stage_copy.exists():
        shutil.rmtree(stage_copy)
    shutil.copytree(stage, stage_copy)
    runtime = prepared["runtime"]
    hermes_dir = dest / "hermes"
    hermes_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(runtime["artifact"], hermes_dir / runtime["artifact"].name)
    shutil.copy2(runtime["manifest"], hermes_dir / runtime["manifest"].name)
    shutil.copy2(runtime["signature"], hermes_dir / runtime["signature"].name)
    result = {
        "stage": stage_copy,
        "prepared": prepared,
        "hermes_zip": hermes_dir / runtime["artifact"].name,
        "archive": None,
    }
    if stop_after == "stage":
        return result
    archive = make.package_stage(
        stage,
        dest / "opsi-build",
        prepared["product_version"],
        prepared["package_version"],
        opsi_tooling=opsi_tooling,
    )
    make.readback_opsi(archive, stage, extract_root=dest / "opsi-build" / "readback")
    result["archive"] = archive
    return result


def assemble(
    dest: Path,
    *,
    config: dict[str, Any],
    work: dict[str, Any],
    hermes: dict[str, Any],
    opsi: dict[str, Any] | None,
    opsi_client: dict[str, Any] | None,
    build_id: str,
    live_eligible: bool,
    hermes_installer: dict[str, Any] | None = None,
) -> dict[str, Any]:
    scan_secrets(dest)
    requirements = {
        "python": config["clientRuntime"]["python"]["range"],
        "node": config["clientRuntime"]["node"]["range"],
    }
    manifest = build_client_release_manifest(
        release_version=str(config["release"]["version"]),
        requirements=requirements,
        work=work,
        hermes=hermes,
        opsi=opsi,
        opsi_client_agent=opsi_client,
        build_id=build_id,
        live_eligible=live_eligible,
        hermes_installer=hermes_installer,
    )
    write_json(dest / "manifests" / "client-release.json", manifest)
    write_json(
        dest / "manifests" / "provenance.json",
        {"buildId": build_id, "releaseVersion": config["release"]["version"], "createdAt": datetime.now(UTC).isoformat()},
    )
    write_json(
        dest / "manifests" / "sbom.cdx.json",
        {"bomFormat": "CycloneDX", "specVersion": "1.5", "version": 1, "components": []},
    )
    write_sha256sums(dest)
    return manifest


def _enroll_script(explicit: Path | None) -> Path | None:
    if explicit and explicit.is_file():
        return explicit
    preferred = ROOT / "scripts" / "opsi-enroll-local-client.ps1"
    if preferred.is_file():
        return preferred
    fallback = ROOT / "scripts" / "opsi-connect-lab-client.ps1"
    return fallback if fallback.is_file() else None


def _hermes_installer_enabled(config: dict[str, Any]) -> bool:
    installer = config.get("hermesInstaller") or {}
    return bool(installer.get("enabled"))


def build_hermes_installer_release(
    *,
    config_path: Path,
    output: Path,
    hermes_repo: Path | None = None,
    signing_key_ref: Path | None = None,
    allow_dirty: bool = False,
    work_dist: Path | None = None,
    mode: str = "online",
    wheelhouse: Path | None = None,
    node_root: Path | None = None,
    wheelhouse_downloader=None,
    installer_exe: Path | None = None,
    smoke_installer: bool = False,
) -> Path:
    config = load_release_config(config_path)
    build_id = datetime.now(UTC).strftime("build-%Y%m%dT%H%M%SZ")
    dest = stage_root(output, str(config["release"]["version"]), build_id)
    frozen = run_preflight(config, allow_dirty=allow_dirty, hermes_repo=hermes_repo)
    work = run_work(config, dest, work_dist=work_dist)
    release_version = resolve_from_source(str(frozen["hermes"]["version"]), config)
    if signing_key_ref is None or not signing_key_ref.is_file():
        raise SystemExit("Release FAILED: --signing-key-ref required")
    built_zip = run_hermes(
        config,
        dest,
        hermes_repo=hermes_repo,
        allow_dirty=allow_dirty,
        mode=mode,
        wheelhouse=wheelhouse,
        node_root=node_root,
        hermes_zip=None,
        wheelhouse_downloader=wheelhouse_downloader,
        release_version=release_version,
        signing_key_ref=signing_key_ref,
    )
    hermes_meta = copy_release_v2_artifacts(dest / "hermes-build", dest)
    hermes_meta.update(
        {
            "profile": config["hermes"]["profile"],
            "sourceRevision": frozen["hermes"]["revision"],
            "version": frozen["hermes"]["version"],
        }
    )
    built_installer = installer_exe or run_hermes_installer(
        dest,
        release_version=release_version,
        smoke=smoke_installer,
        payload_source=None if smoke_installer else (dest / "hermes-build"),
    )
    if not _is_pe_executable(built_installer):
        raise SystemExit("Release FAILED: hermes installer is not a PE executable (ZIP rename forbidden)")
    installer_meta = capture_hermes_installer(built_installer, dest / "hermes-installer")
    auth_status = str(installer_meta.get("authenticodeStatus") or "unknown")
    smoke_key = False
    release_manifest_path = dest / "hermes" / "release-manifest.json"
    if release_manifest_path.is_file():
        release_manifest = json.loads(release_manifest_path.read_text(encoding="utf-8"))
        smoke_key = str(release_manifest.get("signerKeyId") or "").startswith("TEST-ONLY")
    live = bool(
        frozen["smc"]["liveEligible"]
        and frozen["hermes"]["liveEligible"]
        and not smoke_installer
        and not smoke_key
        and auth_status == "Valid"
    )
    assemble(
        dest,
        config=config,
        work=work,
        hermes=hermes_meta,
        opsi=None,
        opsi_client=None,
        build_id=build_id,
        live_eligible=False,
        hermes_installer=installer_meta,
    )
    verified = verify_hermes_installer_release(dest, require_signatures=True, signing_key_ref=signing_key_ref)
    if live:
        verified["liveEligible"] = True
        write_json(dest / "manifests" / "client-release.json", verified)
        write_sha256sums(dest)
        verify_hermes_installer_release(dest, require_signatures=True, signing_key_ref=signing_key_ref)
    elif verified.get("liveEligible"):
        raise SystemExit("Release FAILED: liveEligible requires production PE/MSI, Authenticode Valid, and non-smoke provenance")
    return dest


def build_all(
    *,
    config_path: Path,
    output: Path,
    hermes_repo: Path | None = None,
    opsi_client_installer: Path | None = None,
    signing_key_ref: Path | None = None,
    allow_dirty: bool = False,
    work_dist: Path | None = None,
    hermes_zip: Path | None = None,
    opsi_pkg: Path | None = None,
    enroll_script: Path | None = None,
    mode: str = "online",
    wheelhouse: Path | None = None,
    node_root: Path | None = None,
    opsi_tooling: str = "native",
    wheelhouse_downloader=None,
) -> Path:
    config = load_release_config(config_path)
    if _hermes_installer_enabled(config):
        return build_hermes_installer_release(
            config_path=config_path,
            output=output,
            hermes_repo=hermes_repo,
            signing_key_ref=signing_key_ref,
            allow_dirty=allow_dirty,
            work_dist=work_dist,
            mode=mode,
            wheelhouse=wheelhouse,
            node_root=node_root,
            wheelhouse_downloader=wheelhouse_downloader,
        )
    build_id = datetime.now(UTC).strftime("build-%Y%m%dT%H%M%SZ")
    dest = stage_root(output, str(config["release"]["version"]), build_id)
    frozen = run_preflight(config, allow_dirty=allow_dirty, hermes_repo=hermes_repo)
    work = run_work(config, dest, work_dist=work_dist)
    built_zip = run_hermes(
        config,
        dest,
        hermes_repo=hermes_repo,
        allow_dirty=allow_dirty,
        mode=mode,
        wheelhouse=wheelhouse,
        node_root=node_root,
        hermes_zip=hermes_zip,
        wheelhouse_downloader=wheelhouse_downloader,
    )
    if signing_key_ref is None or not signing_key_ref.is_file():
        raise SystemExit("Release FAILED: --signing-key-ref required")
    pipeline = run_opsi_pipeline(
        config,
        dest,
        hermes_zip=built_zip,
        signing_key_ref=signing_key_ref,
        opsi_tooling=opsi_tooling,
        stop_after="package" if opsi_pkg is None else "stage",
    )
    hermes_meta = copy_runtime_artifacts(pipeline["hermes_zip"], dest)
    hermes_meta.update(
        {
            "profile": config["hermes"]["profile"],
            "sourceRevision": frozen["hermes"]["revision"],
            "version": frozen["hermes"]["version"],
        }
    )
    packaged = opsi_pkg or pipeline["archive"]
    if packaged is None:
        raise SystemExit("Release FAILED: OPSI package missing")
    opsi_meta = copy_opsi_package(packaged, dest)
    opsi_meta.update(
        {
            "productVersion": config["opsi"]["productVersion"],
            "packageVersion": config["opsi"]["packageVersion"],
            "controllerRevision": config["opsi"]["controllerRevision"],
        }
    )
    installer = Path(opsi_client_installer or config["external"]["opsiClientInstaller"])
    opsi_client = capture_opsi_client_installer(installer, dest / "bootstrap")
    script = _enroll_script(enroll_script)
    if script is not None:
        shutil.copy2(script, dest / "bootstrap" / "opsi-enroll-local-client.ps1")
    live = bool(frozen["smc"]["liveEligible"] and frozen["hermes"]["liveEligible"])
    assemble(
        dest,
        config=config,
        work=work,
        hermes=hermes_meta,
        opsi=opsi_meta,
        opsi_client=opsi_client,
        build_id=build_id,
        live_eligible=False,
    )
    verified = verify_client_release(dest, stage=pipeline["stage"], require_signatures=True)
    if live:
        verified["liveEligible"] = True
        write_json(dest / "manifests" / "client-release.json", verified)
        write_sha256sums(dest)
        verify_client_release(dest, stage=pipeline["stage"], require_signatures=True)
    return dest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", nargs="?", default="all", choices=STAGES)
    parser.add_argument("--config", type=Path, default=ROOT / "release" / "client-release.yaml")
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--hermes-repo", type=Path)
    parser.add_argument("--opsi-client-installer", type=Path)
    parser.add_argument("--signing-key-ref", type=Path)
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--work-dist", type=Path)
    parser.add_argument("--hermes-zip", type=Path)
    parser.add_argument("--opsi-package", type=Path)
    parser.add_argument("--wheelhouse", type=Path)
    parser.add_argument("--node-root", type=Path)
    parser.add_argument("--mode", choices=("online", "offline"), default="online")
    parser.add_argument("--opsi-tooling", choices=("zipfile", "native"), default="native")
    args = parser.parse_args()
    config = load_release_config(args.config)
    build_id = datetime.now(UTC).strftime("build-%Y%m%dT%H%M%SZ")
    dest = stage_root(args.output, str(config["release"]["version"]), build_id)
    if args.stage == "preflight":
        run_preflight(config, allow_dirty=args.allow_dirty, hermes_repo=args.hermes_repo)
        return 0
    if args.stage == "work":
        run_work(config, dest, work_dist=args.work_dist)
        return 0
    if args.stage == "hermes":
        archive = run_hermes(
            config,
            dest,
            hermes_repo=args.hermes_repo,
            allow_dirty=args.allow_dirty,
            mode=args.mode,
            wheelhouse=args.wheelhouse,
            node_root=args.node_root,
            hermes_zip=args.hermes_zip,
            signing_key_ref=args.signing_key_ref,
        )
        copy_runtime_artifacts(archive, dest)
        print(archive)
        return 0
    if args.stage == "hermes-installer":
        if args.signing_key_ref is None:
            raise SystemExit("Release FAILED: --signing-key-ref required")
        frozen = run_preflight(config, allow_dirty=args.allow_dirty, hermes_repo=args.hermes_repo)
        release_version = resolve_from_source(str(frozen["hermes"]["version"]), config)
        archive = run_hermes(
            config,
            dest,
            hermes_repo=args.hermes_repo,
            allow_dirty=args.allow_dirty,
            mode=args.mode,
            wheelhouse=args.wheelhouse,
            node_root=args.node_root,
            hermes_zip=args.hermes_zip,
            release_version=release_version,
            signing_key_ref=args.signing_key_ref,
        )
        copy_release_v2_artifacts(dest / "hermes-build", dest)
        installer = run_hermes_installer(
            dest,
            release_version=release_version,
            smoke=False,
            payload_source=dest / "hermes-build",
        )
        if not _is_pe_executable(installer):
            raise SystemExit("Release FAILED: hermes installer is not a PE executable (ZIP rename forbidden)")
        capture_hermes_installer(installer, dest / "hermes-installer")
        print(installer)
        return 0
    if args.stage in {"runtime", "opsi-stage", "opsi-package"}:
        if args.signing_key_ref is None:
            raise SystemExit("Release FAILED: --signing-key-ref required")
        archive = run_hermes(
            config,
            dest,
            hermes_repo=args.hermes_repo,
            allow_dirty=args.allow_dirty,
            mode=args.mode,
            wheelhouse=args.wheelhouse,
            node_root=args.node_root,
            hermes_zip=args.hermes_zip,
        )
        stop = "package" if args.stage == "opsi-package" else "stage"
        pipeline = run_opsi_pipeline(
            config,
            dest,
            hermes_zip=archive,
            signing_key_ref=args.signing_key_ref,
            opsi_tooling=args.opsi_tooling,
            stop_after=stop,
        )
        if pipeline["archive"] is not None:
            copy_opsi_package(pipeline["archive"], dest)
        print(pipeline["stage"] if stop == "stage" else pipeline["archive"])
        return 0
    if args.stage == "assemble":
        if not args.work_dist or not args.hermes_zip or not args.opsi_package:
            raise SystemExit("Release FAILED: assemble requires --work-dist --hermes-zip --opsi-package")
        if args.signing_key_ref is None:
            raise SystemExit("Release FAILED: --signing-key-ref required")
        dest = build_all(
            config_path=args.config,
            output=args.output,
            hermes_repo=args.hermes_repo,
            opsi_client_installer=args.opsi_client_installer,
            signing_key_ref=args.signing_key_ref,
            allow_dirty=args.allow_dirty,
            work_dist=args.work_dist,
            hermes_zip=args.hermes_zip,
            opsi_pkg=args.opsi_package,
            mode=args.mode,
            wheelhouse=args.wheelhouse,
            node_root=args.node_root,
            opsi_tooling=args.opsi_tooling,
        )
        print(dest)
        return 0
    if args.stage == "verify":
        verify_client_release(args.output, require_signatures=True)
        return 0
    dest = build_all(
        config_path=args.config,
        output=args.output,
        hermes_repo=args.hermes_repo,
        opsi_client_installer=args.opsi_client_installer,
        signing_key_ref=args.signing_key_ref,
        allow_dirty=args.allow_dirty,
        work_dist=args.work_dist,
        hermes_zip=args.hermes_zip,
        opsi_pkg=args.opsi_package,
        mode=args.mode,
        wheelhouse=args.wheelhouse,
        node_root=args.node_root,
        opsi_tooling=args.opsi_tooling,
    )
    print(dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
