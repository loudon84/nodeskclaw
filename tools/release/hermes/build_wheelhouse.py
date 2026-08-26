"""Windows AMD64 Python wheelhouse inventory and fail-closed platform checks."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from tools.release.subprocess_text import command_output, run_command

WHEEL_RE = re.compile(
    r"^(?P<name>.+)-(?P<version>[^-]+)-(?P<python>[^-]+)-(?P<abi>[^-]+)-(?P<plat>.+)\.whl$",
    re.I,
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def classify_wheel(filename: str) -> dict[str, str]:
    match = WHEEL_RE.match(Path(filename).name)
    if not match:
        raise ValueError(f"unrecognized wheel name: {filename}")
    return match.groupdict()


def assert_windows_amd64_wheel(filename: str) -> None:
    info = classify_wheel(filename)
    plat = info["plat"].lower()
    if plat in {"any", "py3-none-any"} or plat.endswith("any"):
        return
    if "manylinux" in plat or "linux" in plat or "macosx" in plat or "darwin" in plat:
        raise ValueError(f"wrong platform wheel: {filename}")
    if "win_arm64" in plat or plat == "win32":
        raise ValueError(f"wrong platform wheel: {filename}")
    if "win_amd64" not in plat:
        raise ValueError(f"wrong platform wheel: {filename}")
    abi = info["abi"].lower()
    py_tag = info["python"].lower()
    if "cp" in py_tag and "cp312" not in py_tag and abi not in {"none", "abi3"}:
        raise ValueError(f"wrong python abi wheel: {filename}")


def inventory_wheels(wheelhouse: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(wheelhouse.glob("*.whl")):
        assert_windows_amd64_wheel(path.name)
        info = classify_wheel(path.name)
        items.append(
            {
                "name": info["name"],
                "version": info["version"],
                "filename": path.name,
                "sha256": sha256_file(path),
                "platform": info["plat"],
            }
        )
    if not items:
        raise ValueError("python wheelhouse empty")
    return items


def wheelhouse_digest(items: list[dict[str, Any]]) -> str:
    payload = "\n".join(f"{item['filename']}|{item['sha256']}" for item in items)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_requirements_lock(dest: Path, items: list[dict[str, Any]]) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{item['filename']} sha256={item['sha256']}" for item in items]
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dest


def verify_required_wheels(items: list[dict[str, Any]], required_names: list[str]) -> None:
    present = {item["name"].replace("-", "_").lower() for item in items}
    for name in required_names:
        key = name.replace("-", "_").lower()
        if key not in present:
            raise ValueError(f"missing python dependency: {name}")


def assert_wheelhouse_binary_only(dest: Path) -> None:
    sdists = sorted(dest.glob("*.tar.gz")) + sorted(dest.glob("*.zip"))
    if sdists:
        raise ValueError(f"sdist-only dependency forbidden: {sdists[0].name}")


def resolve_wheelhouse(
    repo: Path,
    dest: Path,
    extras: list[str],
    *,
    supplied: Path | None = None,
    mode: str = "online",
    downloader=None,
) -> Path:
    if supplied is not None:
        assert_wheelhouse_binary_only(supplied)
        inventory_wheels(supplied)
        return supplied
    if mode == "offline":
        raise ValueError("offline build requires --wheelhouse cache")
    fetch = downloader or download_wheelhouse
    return fetch(repo, dest, extras)


def download_wheelhouse(repo: Path, dest: Path, extras: list[str]) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    target = "."
    if extras:
        target = f".[{','.join(extras)}]"
    # uv 0.11+ removed `uv pip download`; use pip cross-platform fetch.
    cmd = [
        "python",
        "-m",
        "pip",
        "download",
        "--only-binary",
        ":all:",
        "--platform",
        "win_amd64",
        "--python-version",
        "3.12",
        "--implementation",
        "cp",
        "-d",
        str(dest),
        target,
    ]
    result = run_command(cmd, cwd=repo)
    if result.returncode != 0:
        raise ValueError(command_output(result, "wheelhouse download failed"))
    # FR-216-04: ensure baseline Managed Config dependency is present offline.
    _ensure_baseline_wheels(dest, ("PyYAML",))
    assert_wheelhouse_binary_only(dest)
    inventory_wheels(dest)
    return dest


def _ensure_baseline_wheels(dest: Path, packages: tuple[str, ...]) -> None:
    existing = list(dest.glob("*.whl"))
    present: set[str] = set()
    if existing:
        present = {item["name"].replace("-", "_").lower() for item in inventory_wheels(dest)}
    missing = [pkg for pkg in packages if pkg.replace("-", "_").lower() not in present]
    if not missing:
        return
    cmd = [
        "python",
        "-m",
        "pip",
        "download",
        "--only-binary",
        ":all:",
        "--platform",
        "win_amd64",
        "--python-version",
        "3.12",
        "--implementation",
        "cp",
        "-d",
        str(dest),
        *missing,
    ]
    result = run_command(cmd)
    if result.returncode != 0:
        raise ValueError(command_output(result, f"baseline wheel download failed: {missing}"))
