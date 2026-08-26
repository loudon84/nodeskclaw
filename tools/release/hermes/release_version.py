"""Single SOT for Hermes installer releaseVersion: <pyproject>-smc.<revision>."""

from __future__ import annotations

from typing import Any

from tools.release.hermes.source_metadata import assert_exact_version

RELEASE_VERSION_PREFIX = "smc."


def _smc_revision(value: Any) -> int:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"invalid smc revision: {value}")
    try:
        revision = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid smc revision: {value}") from exc
    if revision < 1:
        raise ValueError(f"invalid smc revision: {value}")
    return revision


def resolve_release_version(hermes_version: str, smc_revision: int) -> str:
    version = assert_exact_version(hermes_version)
    revision = _smc_revision(smc_revision)
    return f"{version}-{RELEASE_VERSION_PREFIX}{revision}"


def smc_revision_from_config(config: dict[str, Any]) -> int:
    installer = config.get("hermesInstaller") or {}
    if "smcRevision" not in installer:
        return 1
    return _smc_revision(installer.get("smcRevision"))


def resolve_from_source(hermes_version: str, config: dict[str, Any]) -> str:
    resolved = resolve_release_version(hermes_version, smc_revision_from_config(config))
    declared = str((config.get("hermesInstaller") or {}).get("releaseVersion") or "").strip()
    if declared and declared != resolved:
        raise ValueError(f"release version mismatch: config={declared} resolved={resolved}")
    return resolved
