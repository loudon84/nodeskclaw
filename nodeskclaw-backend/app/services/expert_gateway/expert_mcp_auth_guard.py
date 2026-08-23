from __future__ import annotations

from app.services.expert_gateway.errors import (
    EXPERT_SCOPE_DENIED,
    EXPERT_TOOL_NOT_ALLOWED,
    mcp_error_v2,
)
from app.services.mcp_skill_gateway.auth import McpAuthContext

MCP_SCOPE_TOOLS_LIST = "mcp:tools:list"
MCP_SCOPE_TOOLS_CALL = "mcp:tools:call"


def _normalize_headers(headers: dict[str, str] | None) -> dict[str, str]:
    if not headers:
        return {}
    return {str(k).lower(): v for k, v in headers.items()}


def extract_idempotency_key(headers: dict[str, str] | None) -> str | None:
    normalized = _normalize_headers(headers)
    raw = normalized.get("x-idempotency-key")
    if not raw:
        return None
    value = str(raw).strip()
    return value or None


class ExpertMcpAuthGuard:
    extract_idempotency_key = staticmethod(extract_idempotency_key)

    @staticmethod
    def is_client_token(auth_ctx: McpAuthContext | None) -> bool:
        return auth_ctx is not None and auth_ctx.auth_type == "mcp_client_token"

    @staticmethod
    def require_scope(
        auth_ctx: McpAuthContext | None,
        scope: str,
        jsonrpc_id,
    ) -> dict | None:
        if not ExpertMcpAuthGuard.is_client_token(auth_ctx):
            return None
        scopes = set(auth_ctx.scopes or [])
        if scope not in scopes:
            return mcp_error_v2(jsonrpc_id, EXPERT_SCOPE_DENIED, f"Scope {scope} required")
        return None

    @staticmethod
    def filter_catalog_tools(
        tools: list[dict],
        auth_ctx: McpAuthContext | None,
    ) -> list[dict]:
        if not ExpertMcpAuthGuard.is_client_token(auth_ctx):
            return tools
        if not auth_ctx.allowed_tools:
            return tools
        allowed = set(auth_ctx.allowed_tools)
        return [tool for tool in tools if tool.get("name") in allowed]

    @staticmethod
    def assert_skill_allowed(
        auth_ctx: McpAuthContext | None,
        skill_name: str,
        jsonrpc_id,
    ) -> dict | None:
        if not ExpertMcpAuthGuard.is_client_token(auth_ctx):
            return None
        if auth_ctx.allowed_skills and skill_name not in set(auth_ctx.allowed_skills):
            return mcp_error_v2(jsonrpc_id, EXPERT_TOOL_NOT_ALLOWED, "Skill not allowed for MCP client token")
        return None

    @staticmethod
    def filter_skill_tools(
        tools: list[dict],
        auth_ctx: McpAuthContext | None,
    ) -> list[dict]:
        if not ExpertMcpAuthGuard.is_client_token(auth_ctx):
            return tools
        if not auth_ctx.allowed_skills:
            return tools
        allowed = set(auth_ctx.allowed_skills)
        return [tool for tool in tools if tool.get("name") in allowed]
