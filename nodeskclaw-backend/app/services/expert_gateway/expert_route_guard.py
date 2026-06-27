ROUTE_OVERRIDE_KEYS = frozenset({
    "_routing",
    "_execution",
    "route_config",
    "profile",
    "agent_alias",
    "agentAlias",
    "runtime",
    "runtime_name",
    "runtimeName",
    "workspace_override",
    "workspaceOverride",
    "api_server_url",
    "apiServerUrl",
})


def find_route_override_keys(arguments: dict | None) -> list[str]:
    if not isinstance(arguments, dict):
        return []
    return sorted(key for key in arguments if key in ROUTE_OVERRIDE_KEYS)
