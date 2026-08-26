"""Hermes source freeze: git identity, pyproject/uv.lock digests, version SOT."""

from __future__ import annotations

import hashlib
import re
import subprocess
import tomllib
from pathlib import Path
from typing import Any

from tools.release.subprocess_text import command_output, run_command

FORBIDDEN_VERSIONS = {"latest", "current", "main", "unknown"}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_exact_version(value: str) -> str:
    text = str(value or "").strip()
    if not text or text.lower() in FORBIDDEN_VERSIONS:
        raise ValueError(f"forbidden hermes version: {value}")
    return text


def read_pyproject_version(repo: Path) -> str:
    pyproject = repo / "pyproject.toml"
    if not pyproject.is_file():
        raise ValueError("pyproject.toml missing")
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    version = str((data.get("project") or {}).get("version") or "")
    if not version:
        match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject.read_text(encoding="utf-8"), re.M)
        version = match.group(1) if match else ""
    return assert_exact_version(version)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return run_command(["git", *args], cwd=repo)


def freeze_source(
    repo: Path,
    *,
    hermes_version: str = "",
    allow_dirty: bool = False,
) -> dict[str, Any]:
    repo = repo.resolve()
    if not (repo / ".git").exists():
        raise ValueError(f"not a git repository: {repo}")
    pyproject = repo / "pyproject.toml"
    lock = repo / "uv.lock"
    if not pyproject.is_file():
        raise ValueError("pyproject.toml missing")
    if not lock.is_file():
        raise ValueError("uv.lock missing")
    source_version = read_pyproject_version(repo)
    requested = assert_exact_version(hermes_version) if hermes_version and hermes_version != "auto" else source_version
    if requested != source_version:
        raise ValueError(f"hermes version mismatch: cli={requested} pyproject={source_version}")
    rev = _git(repo, "rev-parse", "HEAD")
    if rev.returncode != 0:
        raise ValueError(command_output(rev, "git rev-parse failed"))
    branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    porcelain = _git(repo, "status", "--porcelain")
    dirty = bool(porcelain.stdout.strip())
    if dirty and not allow_dirty:
        raise ValueError("dirty source is forbidden for production builds")
    revision = rev.stdout.strip()
    if len(revision) < 7:
        raise ValueError("git revision too short")
    return {
        "revision": revision,
        "branch": (branch.stdout.strip() if branch.returncode == 0 else ""),
        "dirty": dirty,
        "version": source_version,
        "pyprojectSha256": sha256_file(pyproject),
        "lockSha256": sha256_file(lock),
        "liveEligible": not dirty,
    }
