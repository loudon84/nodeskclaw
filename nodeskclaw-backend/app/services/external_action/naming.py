from __future__ import annotations

import re
from typing import Iterable

META_TOOL_KEYS = frozenset({
    "COMPOSIO_SEARCH_TOOLS",
    "COMPOSIO_MANAGE_CONNECTIONS",
    "COMPOSIO_MULTI_EXECUTE_TOOL",
    "REMOTE_BASH",
    "REMOTE_WORKBENCH",
})
_NON_NAME = re.compile(r"[^a-z0-9_]+")
_REPEATED = re.compile(r"_+")


def _segment(value: str) -> str:
    collapsed = _REPEATED.sub("_", _NON_NAME.sub("_", value.lower()))
    return collapsed.strip("_")


def surface_name(provider: str, toolkit_slug: str, provider_tool_key: str) -> str:
    return "__".join(["ext", _segment(provider), _segment(toolkit_slug), _segment(provider_tool_key)])


def surface_names_for_accounts(accounts: Iterable[tuple[str, str]], policies: Iterable[tuple[str, str, str]]) -> list[str]:
    names: list[str] = []
    policy_rows = [
        (provider, toolkit, tool_key)
        for provider, toolkit, tool_key in policies
        if tool_key not in META_TOOL_KEYS
    ]
    for account_provider, account_toolkit in accounts:
        for provider, toolkit, tool_key in policy_rows:
            if provider == account_provider and toolkit == account_toolkit:
                names.append(surface_name(provider, toolkit, tool_key))
    return names


def has_surface_collision(external_names: list[str], connector_names: Iterable[str]) -> bool:
    seen: set[str] = set()
    for name in external_names:
        if name in seen:
            return True
        seen.add(name)
    return any(name in seen for name in connector_names)
