"""Compile Profile managedConfig into managed.defaults.yaml (FR-214-17 / FR-216-03)."""

from __future__ import annotations

import copy
from typing import Any

import yaml

from tools.release.hermes.runtime_profile import profile_digest

MANAGED_SCHEMA = "smc.opsi.managed-config.v2"


def compile_managed_defaults(
    profile: dict[str, Any],
    *,
    profile_name: str,
) -> dict[str, Any]:
    managed = profile.get("managedConfig") or {}
    defaults = copy.deepcopy(managed.get("defaults") or {})
    enforced = copy.deepcopy(managed.get("enforced") or {})
    if not isinstance(defaults, dict) or not isinstance(enforced, dict):
        raise ValueError("managedConfig.defaults/enforced must be mappings")
    payload = {
        "schema": MANAGED_SCHEMA,
        "profile": profile_name,
        "profileVersion": int(profile.get("version") or 0),
        "profileDigest": profile_digest(profile),
        "defaults": defaults,
        "enforced": enforced,
    }
    return payload


def dump_managed_yaml(payload: dict[str, Any]) -> str:
    """Production Managed Config serializer (FR-216-03): PyYAML safe_dump."""
    text = yaml.safe_dump(
        payload,
        allow_unicode=True,
        sort_keys=True,
        default_flow_style=False,
        width=10_000,
    )
    if not text.endswith("\n"):
        text += "\n"
    # Normalize CRLF → LF for deterministic artifacts.
    return text.replace("\r\n", "\n").replace("\r", "\n")


def render_managed_defaults_yaml(
    profile: dict[str, Any],
    *,
    profile_name: str,
) -> str:
    payload = compile_managed_defaults(profile, profile_name=profile_name)
    return dump_managed_yaml(payload)


def assert_managed_defaults_roundtrip(text: str, expected: dict[str, Any]) -> None:
    """Independent PyYAML oracle + deep semantic equality (FR-216-05 / FR-216-06)."""
    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValueError(f"managed.defaults.yaml standard parse failed: {exc}") from exc
    if not isinstance(loaded, dict):
        raise ValueError("managed.defaults.yaml read-back failed: root is not a mapping")
    if loaded.get("schema") != MANAGED_SCHEMA:
        raise ValueError("managed.defaults.yaml schema mismatch")
    if loaded.get("profile") != expected.get("profile"):
        raise ValueError("managed.defaults.yaml profile mismatch")
    if int(loaded.get("profileVersion") or 0) != int(expected.get("profileVersion") or 0):
        raise ValueError("managed.defaults.yaml profileVersion mismatch")
    if loaded.get("profileDigest") != expected.get("profileDigest"):
        raise ValueError("managed.defaults.yaml profileDigest mismatch")
    if loaded.get("defaults") != expected.get("defaults"):
        raise ValueError("managed.defaults.yaml defaults semantic mismatch")
    if loaded.get("enforced") != expected.get("enforced"):
        raise ValueError("managed.defaults.yaml enforced semantic mismatch")
    # Round-trip dump again to catch type drift (string→bool/null/number).
    again = dump_managed_yaml(loaded)
    reloaded = yaml.safe_load(again)
    if reloaded != loaded:
        raise ValueError("managed.defaults.yaml dump/load type drift detected")
