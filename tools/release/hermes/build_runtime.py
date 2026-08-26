"""Build a Hermes managed offline bundle from a local git repository."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.release.hermes.build_node_packages import (  # noqa: E402
    inventory_packages,
    package_lock_digest,
    resolve_node_root,
    verify_declared_packages,
)
from tools.release.hermes.build_node_workspace import build_hermes_node_workspace  # noqa: E402
from tools.release.hermes.build_wheel import build_wheel  # noqa: E402
from tools.release.hermes.build_wheelhouse import (  # noqa: E402
    inventory_wheels,
    resolve_wheelhouse,
    verify_required_wheels,
    wheelhouse_digest,
    write_requirements_lock,
)
from tools.release.hermes.capability_matrix import (  # noqa: E402
    capabilities_payload,
    enabled_binaries,
    expected_imports,
    expected_node_packages,
    expected_required_packages,
    validate_capability_declaration,
)
from tools.release.hermes.gateway_smoke import run_gateway_smoke  # noqa: E402
from tools.release.hermes.managed_config import (  # noqa: E402
    assert_managed_defaults_roundtrip,
    compile_managed_defaults,
    render_managed_defaults_yaml,
)
from tools.release.hermes.path_policy_gate import path_policy_payload  # noqa: E402
from tools.release.hermes.release_v2 import build_hermes_release_v2  # noqa: E402
from tools.release.hermes.release_version import resolve_release_version  # noqa: E402
from tools.release.hermes.runtime_profile import (  # noqa: E402
    load_profiles,
    profile_digest,
    resolve_profile,
)
from tools.release.hermes.source_metadata import freeze_source  # noqa: E402
from tools.release.hermes.verify_runtime import scan_forbidden, verify_bundle_tree  # noqa: E402
from tools.release.hermes.windows_runtime import (  # noqa: E402
    _extract_zip,
    _promote_runtime_root,
    build_windows_runtime,
)
DEFAULT_PROFILE = ROOT / "release" / "hermes-runtime-profiles.yaml"
DEFAULT_REQUIRES = {"python": ">=3.12,<3.13", "node": ">=22.22,<23"}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_runtime_build(
    dest: Path,
    *,
    source: dict[str, Any],
    profile_name: str,
    profile: dict[str, Any],
    python_items: list[dict[str, Any]],
    node_items: list[dict[str, Any]],
    node_lock_digest: str,
    build_id: str,
    requires: dict[str, str] | None = None,
) -> dict[str, Any]:
    digest = profile_digest(profile)
    payload = {
        "schema": "smc.hermes.runtime-build.v1",
        "version": source["version"],
        "platform": "windows",
        "architecture": "amd64",
        "requires": requires or DEFAULT_REQUIRES,
        "source": {
            "revision": source["revision"],
            "branch": source.get("branch", ""),
            "dirty": source["dirty"],
            "pyprojectSha256": source["pyprojectSha256"],
            "lockSha256": source["lockSha256"],
        },
        "profile": {"name": profile_name, "version": int(profile["version"])},
        "capabilities": capabilities_payload(profile),
        "managedConfigVersion": 2,
        "runtimeProfileVersion": int(profile["version"]),
        "runtimeProfile": profile_name,
        "runtimeProfileDigest": digest,
        "python": {
            "wheelCount": len(python_items),
            "wheelhouseDigest": wheelhouse_digest(python_items),
            "abi": "cp312",
            "requiredPackages": expected_required_packages(profile),
        },
        "node": {
            "packageCount": len(node_items),
            "packageLockDigest": node_lock_digest,
            "requiredPackages": expected_node_packages(profile),
        },
        "buildId": build_id,
        "liveEligible": bool(source.get("liveEligible")),
        "environment": path_policy_payload(),
    }
    dest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def assemble_bundle(
    dest: Path,
    *,
    wheel: Path,
    wheelhouse: Path,
    node_root: Path,
    profile_name: str,
    profile: dict[str, Any],
    source: dict[str, Any],
    requires: dict[str, str] | None = None,
) -> Path:
    validate_capability_declaration(profile)
    if dest.exists():
        shutil.rmtree(dest)
    app = dest / "app"
    python_wheels = dest / "python" / "wheels"
    node = dest / "node"
    config = dest / "config"
    licenses = dest / "LICENSES"
    for path in (app, python_wheels, node / "packages", config, licenses):
        path.mkdir(parents=True)
    shutil.copy2(wheel, app / wheel.name)
    copied = 0
    for item in sorted(wheelhouse.glob("*.whl")):
        shutil.copy2(item, python_wheels / item.name)
        copied += 1
    if copied == 0:
        raise ValueError("missing python dependency")
    python_items = inventory_wheels(python_wheels)
    required = expected_required_packages(profile)
    verify_required_wheels(python_items, required)
    if not (app / wheel.name).is_file():
        raise ValueError("hermes wheel missing")
    write_requirements_lock(dest / "python" / "requirements.lock", python_items)
    if (node_root / "package.json").is_file():
        shutil.copy2(node_root / "package.json", node / "package.json")
    if (node_root / "package-lock.json").is_file():
        shutil.copy2(node_root / "package-lock.json", node / "package-lock.json")
    packages_src = node_root / "packages"
    if packages_src.is_dir():
        for item in packages_src.glob("*.tgz"):
            shutil.copy2(item, node / "packages" / item.name)
    declared = (profile.get("node") or {}).get("packages") or []
    verify_declared_packages(declared, node / "packages")
    for required_node in expected_node_packages(profile):
        token = required_node.lstrip("@").replace("/", "-")
        names = {path.name.lower() for path in (node / "packages").glob("*.tgz")}
        if not any(token.lower() in name for name in names):
            raise ValueError(f"missing node dependency: {required_node}")
    binaries = enabled_binaries(profile)
    if binaries:
        raise ValueError(
            f"Release FAILED: enabled binary capabilities not packaged: {', '.join(binaries)}"
        )
    node_items = inventory_packages(node / "packages")
    package_json = (
        json.loads((node / "package.json").read_text(encoding="utf-8"))
        if (node / "package.json").is_file()
        else {}
    )
    node_digest = package_lock_digest(package_json, node_items)

    managed_payload = compile_managed_defaults(profile, profile_name=profile_name)
    managed_text = render_managed_defaults_yaml(profile, profile_name=profile_name)
    assert_managed_defaults_roundtrip(managed_text, managed_payload)
    (config / "managed.defaults.yaml").write_text(managed_text, encoding="utf-8")
    (config / "config.schema.yaml").write_text("schema: smc.hermes.config.v1\n", encoding="utf-8")
    (licenses / "NOTICE").write_text("SMC Hermes managed offline bundle\n", encoding="utf-8")

    digest = profile_digest(profile)
    (dest / "runtime-profile.json").write_text(
        json.dumps(
            {
                "schema": "smc.hermes.runtime-profile.v2",
                "name": profile_name,
                "digest": digest,
                "profile": profile,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    build_id = datetime.now(UTC).strftime("build-%Y%m%dT%H%M%SZ")
    write_runtime_build(
        dest / "runtime-build.json",
        source=source,
        profile_name=profile_name,
        profile=profile,
        python_items=python_items,
        node_items=node_items,
        node_lock_digest=node_digest,
        build_id=build_id,
        requires=requires,
    )
    scan_forbidden(dest)
    verify_bundle_tree(dest)
    return dest


def zip_bundle(tree: Path, archive: Path) -> Path:
    archive.parent.mkdir(parents=True, exist_ok=True)
    if archive.exists():
        archive.unlink()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(p for p in tree.rglob("*") if p.is_file()):
            zf.write(path, arcname=path.relative_to(tree).as_posix())
    return archive


def verify_capability_imports(
    runtime_tree: Path,
    profile: dict[str, Any],
    *,
    runner: Any | None = None,
) -> list[str]:
    """Run controlled import probes against embedded Python (FR-214-20)."""
    modules = expected_imports(profile)
    if not modules:
        return []
    python_exe = runtime_tree / "python" / "python.exe"
    if runner is not None:
        for module in modules:
            runner(python_exe, module)
        return modules
    if os.name != "nt":
        return modules
    if not python_exe.is_file():
        raise ValueError("import gate: embedded python.exe missing")
    for module in modules:
        # Module names come only from capability_matrix allowlist.
        result = subprocess.run(
            [str(python_exe), "-c", f"import {module}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            check=False,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise ValueError(
                f"Release FAILED: capability import failed for {module}: {detail}"
            )
    return modules


def verify_windows_runtime(
    runtime_tree: Path,
    *,
    expected_version: str = "",
) -> None:
    hermes_exe = runtime_tree / "bin" / "hermes.exe"
    python_exe = runtime_tree / "python" / "python.exe"
    node_exe = runtime_tree / "node" / "node.exe"

    for executable in (hermes_exe, python_exe, node_exe):
        if not executable.is_file():
            raise ValueError(f"runtime executable missing: {executable}")

    if os.name != "nt":
        raise ValueError("Windows runtime functional verification requires Windows build host")

    system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    test_cwd = system_root / "Temp"
    test_home = runtime_tree.parent / "runtime-functional-test-home"
    test_home.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["HERMES_HOME"] = str(test_home)

    result = subprocess.run(
        [str(hermes_exe), "--version"],
        cwd=str(test_cwd),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )

    if result.returncode != 0:
        raise ValueError(
            "Hermes runtime launcher verification failed: "
            f"exit={result.returncode}; "
            f"stdout={(result.stdout or '').strip()}; "
            f"stderr={(result.stderr or '').strip()}"
        )

    output = (result.stdout or "").strip() or (result.stderr or "").strip()
    if expected_version and expected_version not in output:
        raise ValueError(
            "Hermes runtime version mismatch: "
            f"expected={expected_version}; actual={output}"
        )


def build_managed_bundle(
    repo: Path,
    dest: Path,
    *,
    profile_name: str = "smc-managed",
    profiles_path: Path | None = None,
    hermes_version: str = "",
    allow_dirty: bool = False,
    wheelhouse: Path | None = None,
    node_root: Path | None = None,
    wheel: Path | None = None,
    requires: dict[str, str] | None = None,
    mode: str = "online",
    wheelhouse_downloader=None,
    release_version: str = "",
    signing_key_ref: Path | None = None,
    smc_revision: int = 1,
    python_archive: Path | None = None,
    node_archive: Path | None = None,
    sqlite_archive: Path | None = None,
    hermes_workspace: Path | None = None,
    runtime_cache: Path | None = None,
    runtime_downloader=None,
    skip_gateway_smoke: bool = False,
    skip_runtime_functional: bool = False,
    import_runner=None,
) -> Path:
    if mode not in {"online", "offline"}:
        raise ValueError(f"unsupported build mode: {mode}")
    source = freeze_source(repo, hermes_version=hermes_version, allow_dirty=allow_dirty)
    profiles = load_profiles(profiles_path or DEFAULT_PROFILE)
    profile = resolve_profile(profiles, profile_name)
    work = dest / "work"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    if wheel is None:
        wheel = build_wheel(repo, work / "wheel")
    extras = list((profile.get("python") or {}).get("extras") or [])
    wheelhouse = resolve_wheelhouse(
        repo,
        work / "wheelhouse",
        extras,
        supplied=wheelhouse,
        mode=mode,
        downloader=wheelhouse_downloader,
    )
    declared = (profile.get("node") or {}).get("packages") or []
    node_root = resolve_node_root(declared, work / "node", supplied=node_root, mode=mode)
    for manifest_name in ("package.json", "package-lock.json"):
        src_manifest = repo / manifest_name
        if src_manifest.is_file():
            shutil.copy2(src_manifest, node_root / manifest_name)
    tree = assemble_bundle(
        work / "bundle",
        wheel=wheel,
        wheelhouse=wheelhouse,
        node_root=node_root,
        profile_name=profile_name,
        profile=profile,
        source=source,
        requires=requires,
    )
    hermes_ws_dest = tree / "node" / "hermes-workspace"
    if hermes_workspace is not None:
        if not hermes_workspace.is_dir():
            raise ValueError(f"hermes workspace missing: {hermes_workspace}")
        shutil.copytree(hermes_workspace, hermes_ws_dest)
    elif mode == "online" and (repo / "package-lock.json").is_file() and node_archive:
        ws_node_extract = work / "_node-for-workspace"
        _extract_zip(node_archive, ws_node_extract)
        ws_node_root = _promote_runtime_root(ws_node_extract, ("node.exe",))
        build_hermes_node_workspace(repo, ws_node_root, hermes_ws_dest)
        shutil.rmtree(ws_node_extract, ignore_errors=True)

    build_id = datetime.now(UTC).strftime("build-%Y%m%dT%H%M%SZ")
    archive = dest / f"hermes-{source['version']}-windows-amd64.zip"
    zip_bundle(tree, archive)
    (dest / f"{archive.name}.sha256").write_text(sha256_file(archive) + "\n", encoding="utf-8")
    shutil.copy2(tree / "runtime-build.json", dest / "runtime-build.json")
    if not release_version:
        release_version = resolve_release_version(str(source["version"]), smc_revision)
    runtime_tree = build_windows_runtime(
        tree,
        dest / "windows-runtime",
        cache_dir=runtime_cache or (dest / "runtime-cache"),
        python_archive=python_archive,
        node_archive=node_archive,
        sqlite_archive=sqlite_archive,
        mode=mode,
        downloader=runtime_downloader,
        skip_functional_gates=skip_runtime_functional,
    )

    # Copy managed defaults into runtime tree for installer / doctor read-back.
    managed_src = tree / "config" / "managed.defaults.yaml"
    managed_dest = runtime_tree / "config" / "managed.defaults.yaml"
    managed_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(managed_src, managed_dest)

    # Static matrix consistency always; live import/CLI/gateway gates are Windows-host only.
    if import_runner is not None or (os.name == "nt" and not skip_runtime_functional):
        verify_capability_imports(runtime_tree, profile, runner=import_runner)
    else:
        # Still resolve expected imports so allowlist / matrix errors fail closed.
        expected_imports(profile)

    if os.name == "nt" and not skip_runtime_functional:
        verify_windows_runtime(runtime_tree, expected_version=str(source["version"]))
        if not skip_gateway_smoke:
            run_gateway_smoke(runtime_tree, profile=profile, profile_name=profile_name)

    build_hermes_release_v2(
        runtime_tree,
        dest,
        source=source,
        release_version=release_version,
        signing_key_ref=signing_key_ref,
        build_id=build_id,
    )
    return archive


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--dest", type=Path, required=True)
    parser.add_argument("--profile", default="smc-managed")
    parser.add_argument("--profiles", type=Path)
    parser.add_argument("--hermes-version", default="")
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--wheelhouse", type=Path)
    parser.add_argument("--node-root", type=Path)
    parser.add_argument("--wheel", type=Path)
    parser.add_argument("--mode", choices=("online", "offline"), default="online")
    parser.add_argument("--skip-gateway-smoke", action="store_true")
    args = parser.parse_args()
    archive = build_managed_bundle(
        args.repo,
        args.dest,
        profile_name=args.profile,
        profiles_path=args.profiles,
        hermes_version=args.hermes_version,
        allow_dirty=args.allow_dirty,
        wheelhouse=args.wheelhouse,
        node_root=args.node_root,
        wheel=args.wheel,
        mode=args.mode,
        skip_gateway_smoke=args.skip_gateway_smoke,
    )
    print(archive)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
