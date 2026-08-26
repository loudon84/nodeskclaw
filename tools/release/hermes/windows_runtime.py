"""Assemble a self-contained Windows Hermes runtime from build artifacts."""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import tarfile
import time
import zipfile
from http.client import IncompleteRead
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from zipfile import ZIP_STORED, ZipFile

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_ROOT = ROOT / "infra" / "windows" / "hermes-agent" / "scripts"
ENDPOINT_SCRIPTS = (
    "HostOperations.ps1",
    "HostOperations.psm1",
    "SmcHermesManaged.psm1",
    "managed_config_apply.py",
)

PYTHON_VERSION = "3.12.8"
NODE_VERSION = "22.22.0"
PYTHON_EMBED_URL = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-embed-amd64.zip"
PYTHON_EMBED_SHA256 = "8d3f33be9eb810f23c102f08475af2854e50484b8e4e06275e937be61ce3d2fb"
NODE_DIST_URL = f"https://nodejs.org/dist/v{NODE_VERSION}/node-v{NODE_VERSION}-win-x64.zip"
NODE_DIST_SHA256 = "c97fa376d2becdc8863fcd3ca2dd9a83a9f3468ee7ccf7a6d076ec66a645c77a"
WINDOWS_VT_HOOK = Path(__file__).with_name("smc_windows_vt.py")
WINDOWS_VT_PTH_NAME = "zz_smc_windows_vt.pth"

SQLITE_VERSION = "3.53.4"
SQLITE_DLL_URL = "https://www3.sqlite.org/2026/sqlite-dll-win-x64-3530400.zip"
SQLITE_DLL_MIRROR_URLS = (
    SQLITE_DLL_URL,
    "https://www.sqlite.org/2026/sqlite-dll-win-x64-3530400.zip",
)
SQLITE_DLL_SHA3_256 = "deddee963c810d1eeac3ce5e15c7c41da21a1c54d7a39cf54fbf577d2f50de3a"
SQLITE_MIN_SAFE_VERSION = (3, 51, 3)
NODE_MIN_SAFE_VERSION = (22, 22, 0)

PE_AMD64 = 0x8664
DOWNLOAD_ATTEMPTS = 4
DOWNLOAD_TIMEOUT_S = 120
DOWNLOAD_CHUNK = 256 * 1024
Downloader = Callable[[str, Path, str], Path]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha3_256_file(path: Path) -> str:
    return hashlib.sha3_256(path.read_bytes()).hexdigest()


def parse_version_tuple(version_str: str) -> tuple[int, ...]:
    return tuple(int(x) for x in version_str.split("."))


def assert_pe_amd64(path: Path) -> None:
    data = path.read_bytes()
    if len(data) < 0x40 or data[:2] != b"MZ":
        raise ValueError(f"not a PE executable: {path.name}")
    e_lfanew = int.from_bytes(data[0x3C:0x40], "little")
    if e_lfanew <= 0 or e_lfanew + 6 > len(data) or data[e_lfanew : e_lfanew + 4] != b"PE\x00\x00":
        raise ValueError(f"not a PE executable: {path.name}")
    machine = int.from_bytes(data[e_lfanew + 4 : e_lfanew + 6], "little")
    if machine != PE_AMD64:
        raise ValueError(f"wrong architecture: {path.name}")


def _hash_bytes(payload: bytes, algo: str) -> str:
    if algo == "sha256":
        return hashlib.sha256(payload).hexdigest()
    if algo == "sha3_256":
        return hashlib.sha3_256(payload).hexdigest()
    raise ValueError(f"unsupported hash algo: {algo}")


def _read_url_bytes(url: str) -> bytes:
    """Read full response with Content-Length validation when present."""
    with urlopen(url, timeout=DOWNLOAD_TIMEOUT_S) as response:  # noqa: S310 - pinned official URL + digest
        expected = response.headers.get("Content-Length")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = response.read(DOWNLOAD_CHUNK)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        payload = b"".join(chunks)
        if expected is not None:
            try:
                want = int(expected)
            except ValueError:
                want = -1
            if want >= 0 and total != want:
                raise IncompleteRead(payload, want - total)
        return payload


def _download_with_retries(
    url: str,
    dest: Path,
    expected_digest: str,
    *,
    algo: str,
    mirrors: tuple[str, ...] | None = None,
) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and _hash_bytes(dest.read_bytes(), algo) == expected_digest:
        return dest
    # Drop stale/partial cache so IncompleteRead leftovers never poison retry.
    if dest.is_file():
        dest.unlink(missing_ok=True)
    urls = mirrors or (url,)
    errors: list[str] = []
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        for candidate in urls:
            tmp = dest.with_suffix(dest.suffix + f".part.{attempt}")
            try:
                if tmp.is_file():
                    tmp.unlink(missing_ok=True)
                payload = _read_url_bytes(candidate)
                digest = _hash_bytes(payload, algo)
                if digest != expected_digest:
                    raise ValueError(f"hash mismatch for {dest.name} from {candidate}")
                tmp.write_bytes(payload)
                tmp.replace(dest)
                return dest
            except (IncompleteRead, TimeoutError, URLError, HTTPError, OSError, ValueError) as exc:
                errors.append(f"attempt={attempt} url={candidate}: {type(exc).__name__}: {exc}")
                if tmp.is_file():
                    tmp.unlink(missing_ok=True)
                continue
        if attempt < DOWNLOAD_ATTEMPTS:
            time.sleep(min(2 ** (attempt - 1), 8))
    raise ValueError(
        f"download failed for {dest.name} after {DOWNLOAD_ATTEMPTS} attempts: "
        + "; ".join(errors[-6:])
    )


def _download(url: str, dest: Path, expected_sha256: str) -> Path:
    return _download_with_retries(url, dest, expected_sha256, algo="sha256")


def _resolve_archive(
    *,
    name: str,
    url: str,
    expected_sha256: str,
    cache_dir: Path,
    supplied: Path | None,
    mode: str,
    downloader: Downloader | None,
) -> Path:
    if supplied is not None:
        if not supplied.is_file():
            raise ValueError(f"{name} archive missing: {supplied}")
        return supplied
    cached = cache_dir / Path(url).name
    if cached.is_file() and sha256_file(cached) == expected_sha256:
        return cached
    if mode == "offline":
        raise ValueError(f"offline build requires {name} archive cache")
    fetch = downloader or _download
    archive = fetch(url, cached, expected_sha256)
    if sha256_file(archive) != expected_sha256:
        raise ValueError(f"hash mismatch for {name} archive")
    return archive


def _extract_zip(archive: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    with ZipFile(archive) as zf:
        zf.extractall(dest)


def _find_file(root: Path, name: str) -> Path:
    matches = sorted(path for path in root.rglob(name) if path.is_file())
    if not matches:
        raise ValueError(f"{name} missing")
    return matches[0]


def _promote_runtime_root(extracted: Path, names: tuple[str, ...]) -> Path:
    found = [_find_file(extracted, name) for name in names]
    parents = {path.parent.resolve() for path in found}
    if len(parents) != 1:
        raise ValueError("runtime layout is not a single directory")
    return next(iter(parents))


def _enable_python_site(python_root: Path) -> None:
    pth = python_root / "python312._pth"
    lines = [
        "python312.zip",
        ".",
        r"Lib\site-packages",
        "import site",
        "",
    ]
    pth.write_text("\n".join(lines), encoding="ascii")
    (python_root / "Lib" / "site-packages").mkdir(parents=True, exist_ok=True)


def _resolve_sqlite_archive(
    *,
    cache_dir: Path,
    supplied: Path | None,
    mode: str,
    downloader: Downloader | None,
) -> Path:
    if supplied is not None:
        if not supplied.is_file():
            raise ValueError(f"sqlite archive missing: {supplied}")
        return supplied
    cached = cache_dir / Path(SQLITE_DLL_URL).name
    if cached.is_file() and sha3_256_file(cached) == SQLITE_DLL_SHA3_256:
        return cached
    if mode == "offline":
        raise ValueError("offline build requires sqlite archive cache")
    fetch = downloader or _download_sha3
    archive = fetch(SQLITE_DLL_URL, cached, SQLITE_DLL_SHA3_256)
    if sha3_256_file(archive) != SQLITE_DLL_SHA3_256:
        raise ValueError("hash mismatch for sqlite archive")
    return archive


def _download_sha3(url: str, dest: Path, expected_sha3_256: str) -> Path:
    mirrors = SQLITE_DLL_MIRROR_URLS if url in SQLITE_DLL_MIRROR_URLS or url == SQLITE_DLL_URL else (url,)
    return _download_with_retries(
        url,
        dest,
        expected_sha3_256,
        algo="sha3_256",
        mirrors=mirrors,
    )


def _overlay_safe_sqlite(python_root: Path, sqlite_archive: Path) -> str:
    extract = python_root / "_sqlite-extract"
    extract.mkdir(parents=True, exist_ok=True)
    with ZipFile(sqlite_archive) as zf:
        zf.extractall(extract)
    dll = _find_file(extract, "sqlite3.dll")
    assert_pe_amd64(dll)
    target = python_root / "sqlite3.dll"
    shutil.copy2(dll, target)
    shutil.rmtree(extract, ignore_errors=True)
    return str(target)


def _gate_sqlite_version(python_exe: Path) -> str:
    result = subprocess.run(
        [str(python_exe), "-c", "import sqlite3; print(sqlite3.sqlite_version)"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(f"sqlite3 import failed: {result.stderr.strip()}")
    version_str = result.stdout.strip()
    version_tuple = parse_version_tuple(version_str)
    if version_tuple < SQLITE_MIN_SAFE_VERSION:
        raise ValueError(
            f"sqlite3 version {version_str} below minimum safe version "
            f"{'.'.join(str(x) for x in SQLITE_MIN_SAFE_VERSION)}"
        )
    return version_str


def _gate_node_version(node_exe: Path) -> str:
    result = subprocess.run(
        [str(node_exe), "--version"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(f"node version check failed: {result.stderr.strip()}")
    version_str = result.stdout.strip().lstrip("v")
    version_tuple = parse_version_tuple(version_str)
    if version_tuple < NODE_MIN_SAFE_VERSION:
        raise ValueError(
            f"node version {version_str} below minimum safe version "
            f"{'.'.join(str(x) for x in NODE_MIN_SAFE_VERSION)}"
        )
    return version_str


def _gate_npm_npx(node_root: Path) -> tuple[str, str]:
    npm_cmd = node_root / "npm.cmd"
    npx_cmd = node_root / "npx.cmd"
    if not npm_cmd.is_file():
        raise ValueError("npm.cmd missing from node root")
    if not npx_cmd.is_file():
        raise ValueError("npx.cmd missing from node root")
    npm_result = subprocess.run(
        [str(npm_cmd), "--version"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        cwd=str(node_root),
    )
    if npm_result.returncode != 0:
        raise ValueError(f"npm version check failed: {npm_result.stderr.strip()}")
    npx_result = subprocess.run(
        [str(npx_cmd), "--version"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        cwd=str(node_root),
    )
    if npx_result.returncode != 0:
        raise ValueError(f"npx version check failed: {npx_result.stderr.strip()}")
    return npm_result.stdout.strip(), npx_result.stdout.strip()


def _install_windows_console_hook(site_packages: Path) -> None:
    # Isolated embed skips sitecustomize; site-packages .pth import lines still run.
    if not WINDOWS_VT_HOOK.is_file():
        raise ValueError("missing Windows console VT hook")
    site_packages.mkdir(parents=True, exist_ok=True)
    shutil.copy2(WINDOWS_VT_HOOK, site_packages / WINDOWS_VT_HOOK.name)
    (site_packages / WINDOWS_VT_PTH_NAME).write_text("import smc_windows_vt\n", encoding="ascii")


def _install_wheels(wheels: list[Path], site_packages: Path) -> None:
    if not wheels:
        raise ValueError("missing python dependency")
    site_packages.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    for wheel in wheels:
        if wheel.name.lower() in seen:
            continue
        seen.add(wheel.name.lower())
        if not zipfile.is_zipfile(wheel):
            raise ValueError(f"invalid wheel: {wheel.name}")
        with ZipFile(wheel) as zf:
            zf.extractall(site_packages)


SMC_INSTALL_METHOD_STAMP = b"smc-managed\n"


def _install_method_code_root(site_packages: Path) -> Path:
    """Return the directory that owns installed hermes_cli (the code-scoped stamp root)."""
    direct = site_packages / "hermes_cli"
    if direct.is_dir():
        return site_packages
    nested = [path for path in site_packages.glob("*/hermes_cli") if path.is_dir()]
    if len(nested) == 1:
        return nested[0].parent
    raise ValueError("installed hermes_cli code root missing")


def stamp_smc_managed_install_method(site_packages: Path) -> Path:
    """Write the code-scoped stamp next to installed hermes_cli and verify bytes."""
    code_root = _install_method_code_root(site_packages)
    stamp = code_root / ".install_method"
    stamp.write_bytes(SMC_INSTALL_METHOD_STAMP)
    if stamp.read_bytes() != SMC_INSTALL_METHOD_STAMP:
        raise ValueError("install-method stamp mismatch")
    return stamp


def _load_distlib_launcher() -> bytes:
    try:
        import pip._vendor.distlib as distlib_mod
    except ImportError as exc:
        raise ValueError("Windows console launcher stub missing (distlib t64.exe)") from exc
    root = Path(distlib_mod.__file__).resolve().parent
    launcher = root / "t64.exe"
    if not launcher.is_file():
        raise ValueError("Windows console launcher stub missing (distlib t64.exe)")
    return launcher.read_bytes()


def write_hermes_launcher(dest: Path, *, python_rel: str = r"<launcher_dir>\..\python\python.exe") -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    script = (
        "# -*- coding: utf-8 -*-\n"
        "import re\n"
        "import sys\n"
        "from hermes_cli.main import main\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    sys.argv[0] = re.sub(r'(-script\\.pyw|\\.exe)?$', '', sys.argv[0])\n"
        "    sys.exit(main())\n"
    )
    buf = io.BytesIO()
    with ZipFile(buf, "w", compression=ZIP_STORED) as zf:
        zf.writestr("__main__.py", script)
    shebang = f"#!{python_rel}\r\n".encode("ascii")
    dest.write_bytes(_load_distlib_launcher() + shebang + buf.getvalue())
    assert_pe_amd64(dest)
    return dest


def _extract_npm_pack(archive: Path, node_modules: Path) -> None:
    if not tarfile.is_tarfile(archive):
        raise ValueError(f"invalid node package: {archive.name}")
    with tarfile.open(archive, "r:gz") as tar:
        members = [member for member in tar.getmembers() if member.name.startswith("package/")]
        if not members:
            raise ValueError(f"invalid node package: {archive.name}")
        staging = node_modules / f".{archive.stem}"
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True)
        tar.extractall(staging, members=members, filter="data")
    package_root = staging / "package"
    pkg_json = package_root / "package.json"
    if not pkg_json.is_file():
        raise ValueError(f"invalid node package: {archive.name}")
    name = str(json.loads(pkg_json.read_text(encoding="utf-8")).get("name") or "").strip()
    if not name:
        raise ValueError(f"invalid node package: {archive.name}")
    target = node_modules.joinpath(*name.split("/"))
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(package_root), str(target))
    shutil.rmtree(staging, ignore_errors=True)


def _copy_endpoint_scripts(dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for name in ENDPOINT_SCRIPTS:
        src = SCRIPTS_ROOT / name
        if not src.is_file():
            raise ValueError(f"missing endpoint script: {name}")
        shutil.copy2(src, dest / name)


def _collect_wheels(bundle_root: Path) -> list[Path]:
    wheels = sorted((bundle_root / "app").glob("*.whl"))
    wheels.extend(sorted((bundle_root / "python" / "wheels").glob("*.whl")))
    if not wheels:
        raise ValueError("missing python dependency")
    return wheels


def build_windows_runtime(
    bundle_root: Path,
    dest: Path,
    *,
    python_version: str = PYTHON_VERSION,
    node_version: str = NODE_VERSION,
    cache_dir: Path | None = None,
    python_archive: Path | None = None,
    node_archive: Path | None = None,
    sqlite_archive: Path | None = None,
    mode: str = "online",
    downloader: Downloader | None = None,
    skip_functional_gates: bool = False,
) -> Path:
    bundle_root = bundle_root.resolve()
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    cache = cache_dir or (dest.parent / "runtime-cache")
    py_zip = _resolve_archive(
        name="python",
        url=PYTHON_EMBED_URL,
        expected_sha256=PYTHON_EMBED_SHA256,
        cache_dir=cache,
        supplied=python_archive,
        mode=mode,
        downloader=downloader,
    )
    node_zip = _resolve_archive(
        name="node",
        url=NODE_DIST_URL,
        expected_sha256=NODE_DIST_SHA256,
        cache_dir=cache,
        supplied=node_archive,
        mode=mode,
        downloader=downloader,
    )
    sqlite_zip = _resolve_sqlite_archive(
        cache_dir=cache,
        supplied=sqlite_archive,
        mode=mode,
        downloader=downloader,
    )

    python_extract = dest / "_python-extract"
    node_extract = dest / "_node-extract"
    _extract_zip(py_zip, python_extract)
    _extract_zip(node_zip, node_extract)
    python_src = _promote_runtime_root(python_extract, ("python.exe",))
    node_src = _promote_runtime_root(node_extract, ("node.exe",))
    python_root = dest / "python"
    node_root = dest / "node"
    shutil.copytree(python_src, python_root)
    shutil.copytree(node_src, node_root)
    shutil.rmtree(python_extract, ignore_errors=True)
    shutil.rmtree(node_extract, ignore_errors=True)

    _enable_python_site(python_root)
    site_packages = python_root / "Lib" / "site-packages"
    _install_wheels(_collect_wheels(bundle_root), site_packages)
    stamp_smc_managed_install_method(site_packages)
    _install_windows_console_hook(site_packages)
    _overlay_safe_sqlite(python_root, sqlite_zip)

    # Layer A: profile-declared MCP packages (tgz tarballs) → node/node_modules/
    packages = bundle_root / "node" / "packages"
    tarballs = sorted(packages.glob("*.tgz")) if packages.is_dir() else []
    if tarballs:
        top_node_modules = node_root / "node_modules"
        top_node_modules.mkdir(parents=True, exist_ok=True)
        for archive in tarballs:
            _extract_npm_pack(archive, top_node_modules)

    # Layer B: Hermes production workspace → node/hermes-agent/
    # Contains package.json, package-lock.json, and node_modules from npm ci (or bundle copy).
    hermes_agent_ws = node_root / "hermes-agent"
    hermes_ws_src = bundle_root / "node" / "hermes-workspace"
    if hermes_ws_src.is_dir():
        shutil.copytree(hermes_ws_src, hermes_agent_ws)
    else:
        hermes_agent_ws.mkdir(parents=True, exist_ok=True)
        for manifest_name in ("package.json", "package-lock.json"):
            src_manifest = bundle_root / "node" / manifest_name
            if src_manifest.is_file():
                shutil.copy2(src_manifest, hermes_agent_ws / manifest_name)

    write_hermes_launcher(dest / "bin" / "hermes.exe")
    _copy_endpoint_scripts(dest / "scripts")
    runtime_dir = dest / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    for name in ("runtime-build.json", "runtime-profile.json"):
        src = bundle_root / name
        if src.is_file():
            shutil.copy2(src, runtime_dir / name)
    config_src = bundle_root / "config" / "managed.defaults.yaml"
    if config_src.is_file():
        config_dest = dest / "config"
        config_dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(config_src, config_dest / "managed.defaults.yaml")
    # Runtime gates (functional verification on Windows build host)
    actual_sqlite = ""
    actual_node = ""
    actual_npm = ""
    actual_npx = ""
    if os.name == "nt" and not skip_functional_gates:
        actual_sqlite = _gate_sqlite_version(python_root / "python.exe")
        actual_node = _gate_node_version(node_root / "node.exe")
        actual_npm, actual_npx = _gate_npm_npx(node_root)

    metadata = {
        "schema": "smc.hermes.windows-runtime.v2",
        "python": python_version,
        "node": node_version,
        "sqlite": actual_sqlite or SQLITE_VERSION,
        "npm": actual_npm,
        "npx": actual_npx,
        "platform": "windows",
        "architecture": "amd64",
    }
    (runtime_dir / "windows-runtime.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    assert_pe_amd64(dest / "bin" / "hermes.exe")
    assert_pe_amd64(python_root / "python.exe")
    assert_pe_amd64(node_root / "node.exe")
    if not (python_root / "sqlite3.dll").is_file():
        raise ValueError("sqlite3.dll overlay missing")
    if not site_packages.is_dir():
        raise ValueError("site-packages missing")
    if not (site_packages / WINDOWS_VT_HOOK.name).is_file():
        raise ValueError("Windows console VT hook missing")
    if not (site_packages / WINDOWS_VT_PTH_NAME).is_file():
        raise ValueError("Windows console VT hook missing")
    stamp = site_packages / ".install_method"
    if not stamp.is_file():
        nested = list(site_packages.glob("*/.install_method"))
        stamp = nested[0] if nested else stamp
    if not stamp.is_file() or stamp.read_bytes() != SMC_INSTALL_METHOD_STAMP:
        raise ValueError("install-method stamp missing")
    if not (node_root / "hermes-agent").is_dir():
        raise ValueError("node/hermes-agent workspace missing")
    return dest
