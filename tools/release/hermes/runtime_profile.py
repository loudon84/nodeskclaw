"""Runtime profile load/resolve (schema v2). Only declared packages enter the release."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from tools.release.hermes.capability_matrix import (
    CAPABILITY_KEYS,
    validate_capability_declaration,
)
from tools.release.simple_yaml import load_yaml

SCHEMA = "smc.hermes.runtime-profile.v2"
FORBIDDEN_NODE_VERSIONS = {"latest", "current", "*", "unversioned", "main", "master"}
FORBIDDEN_BASELINE_PATH_MARKERS = (
    "/data/hermes/",
    "/usr/local/bin/gbrain",
    "/data/hermes/obsidian-vault",
)
FORBIDDEN_INSTANCE_TOP_KEYS = {
    "model",
    "models",
    "providers",
    "provider",
    "auxiliary",
    "delegation",
    "API_SERVER_KEY",
    "api_server_key",
}


def load_profiles(path: Path) -> dict[str, Any]:
    data = load_yaml(path)
    if not isinstance(data, dict):
        raise ValueError(f"invalid runtime profile schema in {path}")
    schema = data.get("schema")
    if schema != SCHEMA:
        raise ValueError(f"invalid runtime profile schema in {path}: {schema}")
    profiles = data.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        raise ValueError("runtime profiles missing")
    for name, profile in profiles.items():
        validate_profile(name, profile)
    return data


def resolve_profile(data: dict[str, Any], name: str) -> dict[str, Any]:
    profiles = data.get("profiles") or {}
    if name not in profiles:
        raise ValueError(f"runtime profile not defined: {name}")
    profile = profiles[name]
    validate_profile(name, profile)
    return profile


def profile_digest(profile: dict[str, Any]) -> str:
    payload = json.dumps(profile, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_profile(name: str, profile: dict[str, Any]) -> None:
    if not isinstance(profile, dict):
        raise ValueError(f"invalid profile: {name}")
    if int(profile.get("version") or 0) < 2:
        raise ValueError(f"profile version must be >= 2: {name}")

    capabilities = profile.get("capabilities")
    if not isinstance(capabilities, dict):
        raise ValueError(f"capabilities missing: {name}")
    for key in CAPABILITY_KEYS:
        if key not in capabilities:
            raise ValueError(f"capability missing: {key}")
        if not isinstance(capabilities[key], bool):
            raise ValueError(f"capability must be boolean: {key}")
    for key in capabilities:
        if key not in CAPABILITY_KEYS:
            raise ValueError(f"unknown capability: {key}")

    python = profile.get("python") or {}
    extras = python.get("extras")
    if not isinstance(extras, list) or not extras:
        raise ValueError(f"python extras missing: {name}")
    required = python.get("requiredPackages")
    if not isinstance(required, list):
        raise ValueError(f"python requiredPackages missing: {name}")
    lazy = (python.get("lazyInstall") or {}).get("allowed")
    if lazy is True:
        raise ValueError(f"lazy python install forbidden: {name}")
    if lazy is not False:
        raise ValueError(f"python.lazyInstall.allowed must be false: {name}")

    node = profile.get("node") or {}
    packages = node.get("packages")
    if not isinstance(packages, list):
        raise ValueError(f"node packages missing: {name}")
    for item in packages:
        pkg_name = str((item or {}).get("name") or "")
        version = str((item or {}).get("version") or "")
        if not pkg_name:
            raise ValueError(f"node package name missing: {name}")
        if not version or version.lower() in FORBIDDEN_NODE_VERSIONS:
            raise ValueError(f"node package version not pinned: {pkg_name}")

    gateway = profile.get("gateway") or {}
    if gateway.get("bind") not in (None, "127.0.0.1"):
        raise ValueError(f"gateway bind must be 127.0.0.1: {name}")
    if gateway.get("authRequired") is not True:
        raise ValueError(f"gateway.authRequired must be true: {name}")
    if gateway.get("enabled") is not True:
        raise ValueError(f"gateway.enabled must be true: {name}")

    managed = profile.get("managedConfig")
    if not isinstance(managed, dict):
        raise ValueError(f"managedConfig missing: {name}")
    defaults = managed.get("defaults")
    enforced = managed.get("enforced")
    if not isinstance(defaults, dict) or not isinstance(enforced, dict):
        raise ValueError(f"managedConfig.defaults/enforced must be mappings: {name}")

    _validate_lazy_consistency(name, profile, enforced)
    _validate_baseline_paths(name, managed)
    _validate_forbidden_instance_keys(name, managed)
    _validate_disabled_capability_baseline(name, profile, managed)

    validate_capability_declaration(profile)


def _validate_lazy_consistency(name: str, profile: dict[str, Any], enforced: dict[str, Any]) -> None:
    security = enforced.get("security") or {}
    if not isinstance(security, dict):
        raise ValueError(f"managedConfig.enforced.security missing: {name}")
    allow_lazy = security.get("allow_lazy_installs")
    if allow_lazy is True:
        raise ValueError(f"allow_lazy_installs forbidden: {name}")
    if allow_lazy is not False:
        raise ValueError(f"enforced security.allow_lazy_installs must be false: {name}")
    py_lazy = ((profile.get("python") or {}).get("lazyInstall") or {}).get("allowed")
    if py_lazy is not False or allow_lazy is not False:
        raise ValueError(f"lazy install policy mismatch: {name}")


def _walk_strings(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, str):
        found.append(value)
    elif isinstance(value, dict):
        for child in value.values():
            found.extend(_walk_strings(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_walk_strings(child))
    return found


def _validate_baseline_paths(name: str, managed: dict[str, Any]) -> None:
    for text in _walk_strings(managed):
        lowered = text.replace("\\", "/").lower()
        for marker in FORBIDDEN_BASELINE_PATH_MARKERS:
            if marker in lowered:
                raise ValueError(f"Linux/instance path forbidden in managedConfig: {name}: {marker}")


def _validate_forbidden_instance_keys(name: str, managed: dict[str, Any]) -> None:
    for section_name in ("defaults", "enforced"):
        section = managed.get(section_name) or {}
        if not isinstance(section, dict):
            continue
        for key in section:
            if key in FORBIDDEN_INSTANCE_TOP_KEYS:
                raise ValueError(f"instance/secret key forbidden in managedConfig.{section_name}: {key}")


def _validate_disabled_capability_baseline(
    name: str, profile: dict[str, Any], managed: dict[str, Any]
) -> None:
    caps = profile.get("capabilities") or {}
    defaults = managed.get("defaults") or {}
    enforced = managed.get("enforced") or {}

    security = enforced.get("security") or {}
    if caps.get("tirith") is not True:
        if isinstance(security, dict) and security.get("tirith_enabled") is True:
            raise ValueError(f"tirith_enabled forbidden when tirith capability false: {name}")

    if caps.get("lspAutoInstall") is True:
        raise ValueError(f"lspAutoInstall forbidden without packaged language servers: {name}")
    lsp = defaults.get("lsp") or {}
    if isinstance(lsp, dict):
        strategy = str(lsp.get("install_strategy") or "")
        if lsp.get("enabled") is True and strategy in {"auto", "automatic"}:
            raise ValueError(f"LSP auto install forbidden: {name}")
        if strategy == "auto":
            raise ValueError(f"LSP auto install forbidden: {name}")

    secrets = defaults.get("secrets") or {}
    bitwarden = (secrets.get("bitwarden") or {}) if isinstance(secrets, dict) else {}
    if isinstance(bitwarden, dict) and bitwarden.get("auto_install") is True:
        raise ValueError(f"Bitwarden auto install forbidden: {name}")

    if caps.get("localStt") is not True:
        stt = defaults.get("stt") or {}
        if isinstance(stt, dict) and stt.get("enabled") is True and stt.get("provider") == "local":
            raise ValueError(f"local STT enabled but capability localStt=false: {name}")

    if caps.get("edgeTts") is not True:
        tts = defaults.get("tts") or {}
        if isinstance(tts, dict) and tts.get("provider") == "edge":
            raise ValueError(f"edge TTS provider set but capability edgeTts=false: {name}")

    if caps.get("hindsight") is not True:
        memory = defaults.get("memory") or {}
        if isinstance(memory, dict) and memory.get("provider") == "hindsight":
            raise ValueError(f"hindsight memory configured but capability false: {name}")
