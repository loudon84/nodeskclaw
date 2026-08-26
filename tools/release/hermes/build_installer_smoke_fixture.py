#!/usr/bin/env python3
"""Generate release-v2-smoke fixture for installer Pester tests."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.release.hermes.managed_config import (  # noqa: E402
    compile_managed_defaults,
    render_managed_defaults_yaml,
)
from tools.release.hermes.release_v2 import (  # noqa: E402
    assemble_self_contained_tree,
    build_release_manifest,
    zip_release_tree,
)
from tools.release.hermes.runtime_profile import load_profiles, resolve_profile  # noqa: E402
from tools.release.hermes.windows_runtime import write_hermes_launcher  # noqa: E402


def _pe_amd64() -> bytes:
    data = bytearray(0x88)
    data[0:2] = b"MZ"
    data[0x3C:0x40] = (0x80).to_bytes(4, "little")
    data[0x80:0x84] = b"PE\x00\x00"
    data[0x84:0x86] = (0x8664).to_bytes(2, "little")
    return bytes(data)


def build_fixture(dest: Path, *, release_version: str = "0.22.0-smc.1") -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    work = dest / "_work"
    runtime = work / "runtime"
    for rel in (
        "bin",
        "python",
        "node/hermes-agent",
        "scripts",
        "runtime",
        "manifest",
        "uninstall",
        "config",
    ):
        (runtime / rel).mkdir(parents=True, exist_ok=True)
    pe = _pe_amd64()
    try:
        write_hermes_launcher(runtime / "bin" / "hermes.exe")
    except ValueError:
        (runtime / "bin" / "hermes.exe").write_bytes(pe)
    (runtime / "python" / "python.exe").write_bytes(pe)
    (runtime / "python" / "sqlite3.dll").write_bytes(pe)
    (runtime / "node" / "node.exe").write_bytes(pe)
    (runtime / "node" / "npm.cmd").write_text("@echo 10.9.4\r\n", encoding="ascii")
    (runtime / "node" / "npx.cmd").write_text("@echo 10.9.4\r\n", encoding="ascii")
    (runtime / "node" / "hermes-agent" / "package.json").write_text(
        json.dumps({"name": "hermes-agent", "private": True}) + "\n",
        encoding="utf-8",
    )
    # FR-216-19: fixture managed.defaults.yaml from real Runtime Profile compiler.
    profiles = load_profiles(ROOT / "release" / "hermes-runtime-profiles.yaml")
    profile = resolve_profile(profiles, "smc-managed")
    managed_payload = compile_managed_defaults(profile, profile_name="smc-managed")
    managed_text = render_managed_defaults_yaml(profile, profile_name="smc-managed")
    (runtime / "config" / "managed.defaults.yaml").write_text(managed_text, encoding="utf-8")
    scripts_src = ROOT / "infra" / "windows" / "hermes-agent" / "scripts"
    for name in (
        "HostOperations.ps1",
        "HostOperations.psm1",
        "SmcHermesManaged.psm1",
        "managed_config_apply.py",
    ):
        src = scripts_src / name
        if src.is_file():
            shutil.copy2(src, runtime / "scripts" / name)
    (runtime / "runtime" / "runtime-build.json").write_text(
        json.dumps(
            {
                "schema": "smc.hermes.runtime-build.v1",
                "liveEligible": False,
                "capabilities": {
                    "apiServer": True,
                    "mcp": True,
                    "filesystemMcp": True,
                    "web": True,
                    "localStt": True,
                    "edgeTts": True,
                    "hindsight": True,
                    "tirith": False,
                    "lspAutoInstall": False,
                },
                "managedConfigVersion": 2,
                "runtimeProfileVersion": int(managed_payload["profileVersion"]),
                "runtimeProfile": "smc-managed",
                "runtimeProfileDigest": str(managed_payload["profileDigest"]),
                "environment": {
                    "path": {
                        "policy": "installer-managed",
                        "owner": "windows-installer",
                        "entries": [r"D:\Programs\SMC\Hermes\bin"],
                    }
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (runtime / "runtime" / "windows-runtime.json").write_text(
        json.dumps(
            {
                "schema": "smc.hermes.windows-runtime.v2",
                "python": "3.12.8",
                "node": "22.22.0",
                "sqlite": "3.53.4",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    tree = assemble_self_contained_tree(
        runtime,
        work / "tree",
        release_version=release_version,
        hermes_version="0.22.0",
        build_id="build-smoke-fixture",
    )
    archive = zip_release_tree(tree, dest / "hermes-windows-amd64.zip")
    manifest = build_release_manifest(
        tree=tree,
        archive=archive,
        release_version=release_version,
        hermes_version="0.22.0",
        build_id="build-smoke-fixture",
        source={"revision": "smoke", "dirty": False, "liveEligible": False},
        signer_key_id="TEST-ONLY-ed25519",
    )
    (dest / "release-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (dest / "release-manifest.sig").write_bytes(b"")
    shutil.rmtree(work)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dest",
        type=Path,
        default=ROOT / "infra/windows/hermes-agent/tests/fixtures/release-v2-smoke",
    )
    parser.add_argument("--release-version", default="0.22.0-smc.1")
    args = parser.parse_args()
    build_fixture(args.dest, release_version=args.release_version)
    print(args.dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
