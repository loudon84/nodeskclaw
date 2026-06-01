"""JSONC (JSON with Comments) parsing utilities.

Provides safe parsing for openclaw.json and similar config files
that may contain JS-style comments (// and /* */) or trailing commas.
Also includes config-level guards applied before every write.
"""

from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)


def strip_jsonc(text: str) -> str:
    """Strip JS-style comments (// and /* */) and trailing commas from JSON text."""
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r",\s*([}\]])", r"\1", text)
    return text


def parse_config_json(raw: str) -> dict:
    """Parse a JSON string that may contain JSONC comments.

    Tries standard json.loads first; falls back to stripping comments.
    Raises ValueError if the text cannot be parsed even after stripping.
    """
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    try:
        return json.loads(strip_jsonc(raw))
    except json.JSONDecodeError as e:
        raise ValueError(
            f"JSON 格式无法解析（已尝试去除注释）: {e}"
        ) from e


def deep_merge_config(base: dict, patch: dict) -> dict:
    """Recursively merge *patch* into *base* (mutates *base* in place).

    - dict + dict  -> recurse (preserves keys in *base* not mentioned in *patch*)
    - anything else -> *patch* value replaces *base* value
    """
    for key, val in patch.items():
        if isinstance(val, dict) and isinstance(base.get(key), dict):
            deep_merge_config(base[key], val)
        else:
            base[key] = val
    return base


# Paths must stay in sync with CHANNEL_PLUGIN_DIR / LEARNING_PLUGIN_DIR
# constructed in llm_config_service.py.
_CHANNEL_PLUGIN_PATHS: dict[str, str] = {
    "nodeskclaw": "/root/.openclaw/extensions/openclaw-channel-nodeskclaw",
    "learning": "/root/.openclaw/extensions/openclaw-channel-learning",
}


def ensure_channel_plugin_integrity(config: dict) -> dict:
    """If a channel plugin section exists in *channels*, guarantee the
    matching plugin load-path and entries record are present too.

    Called before every openclaw.json write via the gene-install adapter
    so that a Gene's ``runtime_config`` patch can never silently remove
    the channel-plugin wiring.
    """
    channels = config.get("channels", {})
    for channel_id, plugin_path in _CHANNEL_PLUGIN_PATHS.items():
        if channel_id not in channels:
            continue
        plugins = config.setdefault("plugins", {})
        load = plugins.setdefault("load", {})
        paths = load.setdefault("paths", [])
        if plugin_path not in paths:
            logger.warning(
                "ensure_channel_plugin_integrity: %s plugin path missing, auto-repaired",
                channel_id,
            )
            paths.append(plugin_path)
        entries = plugins.setdefault("entries", {})
        if channel_id not in entries:
            logger.warning(
                "ensure_channel_plugin_integrity: %s plugin entry missing, auto-repaired",
                channel_id,
            )
            entries[channel_id] = {"enabled": True}
    return config


def ensure_exec_security(config: dict) -> dict:
    """Enforce headless exec policy: security=full + ask=off.

    NoDeskClaw runs in non-interactive K8s pods where exec approval
    prompts would hang forever. This is called before every openclaw.json
    write to guarantee the setting is never lost.
    """
    tools = config.setdefault("tools", {})
    exec_cfg = tools.setdefault("exec", {})
    exec_cfg["security"] = "full"
    exec_cfg["ask"] = "off"
    return config
