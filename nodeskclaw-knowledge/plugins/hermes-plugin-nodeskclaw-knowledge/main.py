"""Hermes plugin entry: register knowledge.retrieve."""

from __future__ import annotations

from typing import Any

from tools.knowledge import (
    TOOL_DESCRIPTION,
    TOOL_NAME,
    TOOL_SCHEMA,
    knowledge_retrieve,
    set_plugin_config,
)


def register(ctx: Any) -> None:
    plugin_config = None
    for attr in ("plugin_config", "config", "settings"):
        value = getattr(ctx, attr, None)
        if isinstance(value, dict):
            plugin_config = value
            break
    if plugin_config is None and hasattr(ctx, "get"):
        try:
            plugin_config = ctx.get("config")  # type: ignore[misc]
        except Exception:  # noqa: BLE001
            plugin_config = None
    if isinstance(plugin_config, dict):
        set_plugin_config(plugin_config)

    ctx.register_tool(
        name=TOOL_NAME,
        toolset="nodeskclaw-knowledge",
        schema=TOOL_SCHEMA,
        handler=knowledge_retrieve,
        description=TOOL_DESCRIPTION,
    )
