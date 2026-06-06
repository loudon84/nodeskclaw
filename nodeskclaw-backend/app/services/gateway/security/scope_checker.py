from dataclasses import dataclass


_METHOD_SCOPE_MAP: dict[str, str] = {
    "tools/list": "mcp:tools:read",
    "tools/call": "mcp:tools:execute",
    "resources/list": "mcp:resources:read",
    "resources/read": "mcp:resources:read",
    "prompts/list": "mcp:prompts:read",
    "prompts/get": "mcp:prompts:read",
}


@dataclass
class ScopeCheckResult:
    is_allowed: bool
    required_scope: str | None = None
    check_status: str = "checked"


class ScopeChecker:
    @staticmethod
    def check_scope(jwt_scopes: list[str] | None, method: str) -> ScopeCheckResult:
        if jwt_scopes is None:
            return ScopeCheckResult(is_allowed=True, check_status="skipped")

        required = _METHOD_SCOPE_MAP.get(method)
        if required is None:
            return ScopeCheckResult(is_allowed=True, required_scope=None, check_status="no_mapping")

        if required in jwt_scopes:
            return ScopeCheckResult(is_allowed=True, required_scope=required, check_status="checked")

        return ScopeCheckResult(is_allowed=False, required_scope=required, check_status="checked")
