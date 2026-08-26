"""Copy Work installers and the official OPSI client installer into a release tree."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

SECRET_NAMES = {".env", "credentials", "password", "token", "secret", "private-key"}
SECRET_SUFFIXES = {".key", ".pfx", ".p12"}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture_file(src: Path, dest: Path) -> dict[str, Any]:
    if not src.is_file():
        raise ValueError(f"artifact missing: {src}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return {
        "name": dest.name,
        "sha256": sha256_file(dest),
        "bytes": dest.stat().st_size,
    }


def authenticode_status(path: Path) -> str:
    if path.suffix.lower() not in {".exe", ".msi"}:
        return "n/a"
    if os.name != "nt":
        return "n/a"
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"(Get-AuthenticodeSignature -LiteralPath '{path}').Status",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    status = (result.stdout or "").strip()
    return status or "unknown"


def capture_work_installers(source_dir: Path, dest: Path) -> dict[str, Any]:
    dest.mkdir(parents=True, exist_ok=True)
    setup = next(iter(source_dir.glob("copilot-desktop-*-setup.exe")), None)
    portable = next(iter(source_dir.glob("copilot-desktop-*-portable.exe")), None)
    if setup is None or portable is None:
        raise ValueError("Work Windows installers missing")
    setup_meta = capture_file(setup, dest / setup.name)
    portable_meta = capture_file(portable, dest / portable.name)
    version = setup.name.replace("copilot-desktop-", "").replace("-setup.exe", "")
    return {
        "version": version,
        "sha256": setup_meta["sha256"],
        "setupSha256": setup_meta["sha256"],
        "portableSha256": portable_meta["sha256"],
        "authenticodeStatus": authenticode_status(dest / setup.name),
    }


def capture_opsi_client_installer(src: Path, dest: Path) -> dict[str, Any]:
    copied = capture_file(src, dest / src.name)
    copied["authenticodeStatus"] = authenticode_status(dest / src.name)
    copied["version"] = src.stem
    return copied


def capture_hermes_installer(src: Path, dest: Path) -> dict[str, Any]:
    copied = capture_file(src, dest / src.name)
    copied["authenticodeStatus"] = authenticode_status(dest / src.name)
    parts = src.name.replace("_windows-amd64.exe", "").split("_", 1)
    copied["version"] = parts[1] if len(parts) == 2 else src.stem
    msi_src = src.with_suffix(".msi")
    if msi_src.is_file():
        capture_file(msi_src, dest / msi_src.name)
        copied["msiSha256"] = sha256_file(dest / msi_src.name)
    return copied


def write_sha256sums(root: Path) -> Path:
    lines = []
    for path in sorted(p for p in root.rglob("*") if p.is_file() and p.name != "SHA256SUMS"):
        rel = path.relative_to(root).as_posix()
        lines.append(f"{sha256_file(path)}  {rel}")
    out = root / "manifests" / "SHA256SUMS"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def scan_secrets(root: Path) -> None:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        name = path.name.lower()
        if path.suffix.lower() in SECRET_SUFFIXES:
            raise ValueError(f"secret suffix in release: {path.relative_to(root)}")
        if any(token in name for token in SECRET_NAMES) and "public" not in name:
            raise ValueError(f"secret name in release: {path.relative_to(root)}")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
