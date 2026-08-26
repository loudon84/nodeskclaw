"""Controlled capability → dependency/import matrix (FR-214-02 / FR-214-20).

Import module names come only from this allowlist. Profile text is never
interpolated into Python probe code.

v2.1.6: baseline PyYAML is always required for Managed Config Apply (FR-216-04),
independent of capability toggles — not a new capability key.
"""

from __future__ import annotations

from typing import Any

# Canonical capability keys for schema v2.
CAPABILITY_KEYS = (
    "apiServer",
    "mcp",
    "filesystemMcp",
    "web",
    "localStt",
    "edgeTts",
    "hindsight",
    "tirith",
    "lspAutoInstall",
)

# Always-on Runtime packages / imports (Config Integrity, FR-216-04).
BASELINE_REQUIRED_PACKAGES = ("pyyaml",)
BASELINE_IMPORTS = ("yaml",)

# Controlled matrix: extras / required Python packages / import probes /
# node package names / binary ids required when capability is enabled.
CAPABILITY_MATRIX: dict[str, dict[str, list[str]]] = {
    "apiServer": {
        "extras": ["messaging"],
        "required": ["aiohttp"],
        "imports": ["aiohttp"],
        "node": [],
        "binaries": [],
    },
    "mcp": {
        "extras": ["mcp"],
        "required": ["mcp"],
        "imports": ["mcp"],
        "node": [],
        "binaries": [],
    },
    "filesystemMcp": {
        "extras": [],
        "required": [],
        "imports": [],
        "node": ["@modelcontextprotocol/server-filesystem"],
        "binaries": [],
    },
    "web": {
        "extras": ["web"],
        "required": [],
        "imports": [],
        "node": [],
        "binaries": [],
    },
    "localStt": {
        "extras": ["voice"],
        "required": [],
        "imports": [],
        "node": [],
        "binaries": [],
    },
    "edgeTts": {
        "extras": ["edge-tts"],
        "required": ["edge-tts"],
        "imports": ["edge_tts"],
        "node": [],
        "binaries": [],
    },
    "hindsight": {
        "extras": ["hindsight"],
        "required": [],
        "imports": [],
        "node": [],
        "binaries": [],
    },
    "tirith": {
        "extras": [],
        "required": [],
        "imports": [],
        "node": [],
        "binaries": ["tirith"],
    },
    "lspAutoInstall": {
        "extras": [],
        "required": [],
        "imports": [],
        "node": [],
        "binaries": [],
    },
}

# Import names that probes may execute. Subset of matrix imports + baseline.
ALLOWED_IMPORT_MODULES = frozenset(
    {
        *(module for spec in CAPABILITY_MATRIX.values() for module in spec.get("imports", [])),
        *BASELINE_IMPORTS,
    }
)


def _enabled_caps(profile: dict[str, Any]) -> dict[str, bool]:
    caps = profile.get("capabilities") or {}
    if not isinstance(caps, dict):
        raise ValueError("capabilities must be a mapping")
    return {key: bool(caps.get(key)) for key in CAPABILITY_KEYS}


def _declared_extras(profile: dict[str, Any]) -> set[str]:
    extras = (profile.get("python") or {}).get("extras") or []
    if not isinstance(extras, list):
        raise ValueError("python.extras must be a list")
    return {str(item) for item in extras}


def _declared_required(profile: dict[str, Any]) -> set[str]:
    required = (profile.get("python") or {}).get("requiredPackages") or []
    if not isinstance(required, list):
        raise ValueError("python.requiredPackages must be a list")
    return {str(item) for item in required}


def _declared_node_names(profile: dict[str, Any]) -> set[str]:
    packages = (profile.get("node") or {}).get("packages") or []
    if not isinstance(packages, list):
        raise ValueError("node.packages must be a list")
    return {str((item or {}).get("name") or "") for item in packages if (item or {}).get("name")}


def validate_capability_declaration(profile: dict[str, Any]) -> None:
    """Capability enabled → profile must declare matrix extras/required/node."""
    caps = profile.get("capabilities")
    if not isinstance(caps, dict):
        raise ValueError("capabilities missing")
    for key in CAPABILITY_KEYS:
        if key not in caps:
            raise ValueError(f"capability missing: {key}")
        if not isinstance(caps[key], bool):
            raise ValueError(f"capability must be boolean: {key}")
    for key, unknown in caps.items():
        if key not in CAPABILITY_KEYS:
            raise ValueError(f"unknown capability: {key}")
        _ = unknown

    enabled = _enabled_caps(profile)
    extras = _declared_extras(profile)
    required = _declared_required(profile)
    node_names = _declared_node_names(profile)

    for cap, on in enabled.items():
        if not on:
            continue
        spec = CAPABILITY_MATRIX[cap]
        for extra in spec["extras"]:
            if extra not in extras:
                raise ValueError(
                    f"Release FAILED: capability {cap} requires Python extra {extra}"
                )
        for pkg in spec["required"]:
            if pkg not in required:
                raise ValueError(
                    f"Release FAILED: capability {cap} requires Python package {pkg}"
                )
        for node_pkg in spec["node"]:
            if node_pkg not in node_names:
                raise ValueError(
                    f"Release FAILED: capability {cap} requires Node package {node_pkg}"
                )
        if cap == "lspAutoInstall":
            raise ValueError(
                "Release FAILED: lspAutoInstall requires packaged language servers"
            )
        if cap == "filesystemMcp":
            node = profile.get("node") or {}
            if node.get("required") is not True:
                raise ValueError(
                    "Release FAILED: capability filesystemMcp requires node.required=true"
                )


def expected_required_packages(profile: dict[str, Any]) -> list[str]:
    """Union of profile.requiredPackages, matrix-derived, and baseline packages."""
    declared = list(_declared_required(profile))
    seen = {name.replace("-", "_").lower() for name in declared}
    result = list(declared)
    for cap, on in _enabled_caps(profile).items():
        if not on:
            continue
        for pkg in CAPABILITY_MATRIX[cap]["required"]:
            key = pkg.replace("-", "_").lower()
            if key not in seen:
                seen.add(key)
                result.append(pkg)
    for pkg in BASELINE_REQUIRED_PACKAGES:
        key = pkg.replace("-", "_").lower()
        if key not in seen:
            seen.add(key)
            result.append(pkg)
    return result


def expected_imports(profile: dict[str, Any]) -> list[str]:
    """Import probe modules for enabled capabilities + baseline (allowlist only)."""
    modules: list[str] = []
    seen: set[str] = set()
    for module in BASELINE_IMPORTS:
        if module not in ALLOWED_IMPORT_MODULES:
            raise ValueError(f"import module not allowlisted: {module}")
        if module not in seen:
            seen.add(module)
            modules.append(module)
    for cap, on in _enabled_caps(profile).items():
        if not on:
            continue
        for module in CAPABILITY_MATRIX[cap]["imports"]:
            if module not in ALLOWED_IMPORT_MODULES:
                raise ValueError(f"import module not allowlisted: {module}")
            if module not in seen:
                seen.add(module)
                modules.append(module)
    return modules


def expected_node_packages(profile: dict[str, Any]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for cap, on in _enabled_caps(profile).items():
        if not on:
            continue
        for name in CAPABILITY_MATRIX[cap]["node"]:
            if name not in seen:
                seen.add(name)
                names.append(name)
    return names


def enabled_binaries(profile: dict[str, Any]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for cap, on in _enabled_caps(profile).items():
        if not on:
            continue
        for name in CAPABILITY_MATRIX[cap]["binaries"]:
            if name not in seen:
                seen.add(name)
                names.append(name)
    return names


def capabilities_payload(profile: dict[str, Any]) -> dict[str, bool]:
    caps = profile.get("capabilities") or {}
    return {key: bool(caps.get(key)) for key in CAPABILITY_KEYS}
