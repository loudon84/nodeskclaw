"""Static gate: persistent PATH is installer-managed; all other writers are forbidden."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
HERMES_WINDOWS = ROOT / "infra" / "windows" / "hermes-agent"

# Production source only — tests and future migration tools are allowlisted.
ALLOWLIST_DIR_PARTS = {
    ("tests",),
    ("migration",),
    ("forensic",),
}

SCAN_SUFFIXES = {".ps1", ".psm1", ".psd1", ".wxs", ".wxi", ".xml", ".cs", ".bat", ".cmd"}

HERMES_BIN_PATH = r"D:\Programs\SMC\Hermes\bin"
ALLOWED_PATH_POLICY = "installer-managed"
ALLOWED_PATH_OWNER = "windows-installer"
ALLOWED_PATH_KEYS = frozenset({"policy", "owner", "entries"})
ALLOWED_WIX_PATH_COMPONENT_ID = "cmpHermesMachinePath"
ALLOWED_WIX_PATH_ENV_ID = "envHermesBinPath"
_WIX_NS = "{http://wixtoolset.org/schemas/v4/wxs}"

# Persistent Machine/User PATH writers (case-insensitive, multiline-tolerant).
# WiX Environment PATH is handled by the exact-component allowlist, not this list.
FORBIDDEN_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "SetEnvironmentVariable PATH Machine/User",
        re.compile(
            r"""SetEnvironmentVariable\s*\(\s*["']Path["']\s*,.*?["'](?:Machine|User)["']""",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "EnvironmentVariableTarget PATH Machine/User",
        re.compile(
            r"""EnvironmentVariableTarget\s*::\s*(?:Machine|User).*?["']Path["']"""
            r"""|["']Path["'].*?EnvironmentVariableTarget\s*::\s*(?:Machine|User)""",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "setx PATH",
        re.compile(r"""\bsetx\s+(?:/M\s+)?["']?Path["']?""", re.IGNORECASE),
    ),
    (
        "HKCU Environment Path write",
        re.compile(
            r"""HKCU:\\Environment["']?[^\n]{0,120}\bPath\b"""
            r"""|Set-ItemProperty[^\n]{0,160}HKCU:\\Environment[^\n]{0,80}\bPath\b""",
            re.IGNORECASE,
        ),
    ),
    (
        "Session Manager Environment Path write",
        re.compile(
            r"""Session\s+Manager\\Environment[^\n]{0,120}\bPath\b"""
            r"""|Set-ItemProperty[^\n]{0,200}Session\s+Manager\\Environment[^\n]{0,80}\bPath\b""",
            re.IGNORECASE,
        ),
    ),
    (
        "Add/Remove-SmcMachinePath production API",
        re.compile(r"""\b(?:Add|Remove)-SmcMachinePath\b"""),
    ),
]


def _is_allowlisted(rel: Path) -> bool:
    parts = tuple(part.lower() for part in rel.parts)
    for allow in ALLOWLIST_DIR_PARTS:
        if len(parts) >= len(allow) and parts[: len(allow)] == allow:
            return True
        # allow .../tests/... anywhere under hermes-agent
        if allow[0] in parts:
            return True
    return False


def _iter_scan_files(root: Path) -> list[Path]:
    files: list[Path] = []
    if not root.is_dir():
        return files
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SCAN_SUFFIXES:
            continue
        rel = path.relative_to(root)
        if _is_allowlisted(rel):
            continue
        files.append(path)
    return files


def scan_persistent_path_mutations(root: Path | None = None) -> list[str]:
    """Return human-readable hits; empty list means PASS."""
    base = root or HERMES_WINDOWS
    hits: list[str] = []
    for path in _iter_scan_files(base):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        # Normalize newlines for multiline patterns.
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        for label, pattern in FORBIDDEN_PATTERNS:
            if pattern.search(normalized):
                rel = path.relative_to(base) if base in path.parents or path == base else path
                hits.append(f"{label}: {rel.as_posix()}")
    return hits


def assert_no_persistent_path_mutations(root: Path | None = None) -> None:
    hits = scan_persistent_path_mutations(root)
    if hits:
        joined = "; ".join(hits[:12])
        raise ValueError(f"PERSISTENT_PATH_MUTATION_FORBIDDEN: {joined}")


def _local_tag(tag: str) -> str:
    if tag.startswith("{"):
        return tag.rsplit("}", 1)[-1]
    return tag


def _attr(element: ET.Element, name: str) -> str:
    for key, value in element.attrib.items():
        if _local_tag(key) == name:
            return value
    return ""


def _describe_wix_path_env(component_id: str, env: ET.Element) -> str:
    return (
        f"Id={_attr(env, 'Id') or '(missing)'} "
        f"Component={component_id or '(missing)'} "
        f"Name={_attr(env, 'Name')} Value={_attr(env, 'Value')} "
        f"System={_attr(env, 'System') or '(missing)'}"
    )


def _is_approved_wix_path_env(component_id: str, env: ET.Element) -> bool:
    return (
        component_id == ALLOWED_WIX_PATH_COMPONENT_ID
        and _attr(env, "Id") == ALLOWED_WIX_PATH_ENV_ID
        and _attr(env, "Name").upper() == "PATH"
        and _attr(env, "Value") == HERMES_BIN_PATH
        and _attr(env, "System").lower() == "yes"
        and _attr(env, "Permanent").lower() == "no"
        and _attr(env, "Part").lower() == "first"
        and _attr(env, "Action").lower() == "set"
    )


def _iter_wix_path_environments(root_el: ET.Element) -> list[tuple[str, ET.Element]]:
    found: list[tuple[str, ET.Element]] = []
    for component in root_el.iter():
        if _local_tag(component.tag) != "Component":
            continue
        component_id = _attr(component, "Id")
        for child in list(component):
            if _local_tag(child.tag) != "Environment":
                continue
            if _attr(child, "Name").upper() != "PATH":
                continue
            found.append((component_id, child))
    return found


def assert_wix_path_environment_allowlist(root: Path | None = None) -> None:
    """Allow exactly one per-machine WiX PATH Environment of the approved shape."""
    base = root or HERMES_WINDOWS
    wix_files = list(base.rglob("*.wxs")) + list(base.rglob("*.wxi"))
    approved = 0
    rejects: list[str] = []
    for path in wix_files:
        rel = path.relative_to(base)
        if _is_allowlisted(rel):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        try:
            tree = ET.fromstring(text)
        except ET.ParseError as exc:
            raise ValueError(f"PERSISTENT_PATH_MUTATION_FORBIDDEN: invalid WiX XML {rel.as_posix()}: {exc}") from exc
        for component_id, env in _iter_wix_path_environments(tree):
            if _is_approved_wix_path_env(component_id, env):
                approved += 1
                continue
            rejects.append(f"{rel.as_posix()}: {_describe_wix_path_env(component_id, env)}")
    if rejects:
        raise ValueError(
            "PERSISTENT_PATH_MUTATION_FORBIDDEN: unapproved WiX Environment PATH in "
            + "; ".join(rejects)
        )
    if approved != 1:
        raise ValueError(
            "PERSISTENT_PATH_MUTATION_FORBIDDEN: approved WiX Environment PATH "
            f"component {ALLOWED_WIX_PATH_COMPONENT_ID} must appear exactly once "
            f"(found {approved})"
        )


def path_policy_payload() -> dict[str, Any]:
    return {
        "path": {
            "policy": ALLOWED_PATH_POLICY,
            "owner": ALLOWED_PATH_OWNER,
            "entries": [HERMES_BIN_PATH],
        }
    }


def assert_path_policy_metadata(build: dict[str, Any]) -> None:
    env = build.get("environment")
    if not isinstance(env, dict):
        raise ValueError("environment.path.policy missing (environment block)")
    path = env.get("path")
    if not isinstance(path, dict):
        raise ValueError("environment.path.policy missing (path block)")
    extra = set(path) - ALLOWED_PATH_KEYS
    missing = ALLOWED_PATH_KEYS - set(path)
    if extra or missing:
        raise ValueError(
            "environment.path fields invalid "
            f"(missing={sorted(missing)} extra={sorted(extra)})"
        )
    if path.get("policy") != ALLOWED_PATH_POLICY:
        raise ValueError("environment.path.policy must be installer-managed")
    if path.get("owner") != ALLOWED_PATH_OWNER:
        raise ValueError("environment.path.owner must be windows-installer")
    entries = path.get("entries")
    if entries != [HERMES_BIN_PATH]:
        raise ValueError("environment.path.entries must be the single fixed Hermes bin path")


def assert_hermes_path_policy(root: Path | None = None) -> None:
    """Full static + WiX allowlist gate used by release verification."""
    assert_no_persistent_path_mutations(root)
    assert_wix_path_environment_allowlist(root)
