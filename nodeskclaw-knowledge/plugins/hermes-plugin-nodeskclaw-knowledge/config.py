"""Plugin settings: Hermes config first, then SMC_KB_* env vars."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


class ConfigError(ValueError):
    """Raised when required Knowledge plugin settings are missing."""


@dataclass(frozen=True, slots=True)
class PluginSettings:
    url: str
    token: str


def _pick_str(plugin_config: dict[str, Any] | None, key: str, env_name: str) -> str:
    if plugin_config:
        raw = plugin_config.get(key)
        if raw is not None and str(raw).strip():
            return str(raw).strip()
    return str(os.environ.get(env_name) or "").strip()


def load_settings(plugin_config: dict[str, Any] | None = None) -> PluginSettings:
    url = _pick_str(plugin_config, "url", "SMC_KB_API_URL").rstrip("/")
    token = _pick_str(plugin_config, "token", "SMC_KB_API_TOKEN")
    missing: list[str] = []
    if not url:
        missing.append("SMC_KB_API_URL / config.url")
    if not token:
        missing.append("SMC_KB_API_TOKEN / config.token")
    if missing:
        raise ConfigError(
            "Missing Knowledge plugin settings: "
            + ", ".join(missing)
            + ". Set ~/.hermes/.env or plugins.nodeskclaw-knowledge.config."
        )
    return PluginSettings(url=url, token=token)
