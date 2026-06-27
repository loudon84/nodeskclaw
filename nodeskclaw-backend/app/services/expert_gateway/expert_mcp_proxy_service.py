from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.expert_gateway.errors import EXPERT_UPSTREAM_MCP_ERROR, mcp_error_v2
from app.services.hermes_external import hermes_agent_mcp_gateway_service as agent_mcp


class ExpertMcpProxyService:
    @staticmethod
    async def list_upstream_tools(
        db: AsyncSession,
        org_id: str,
        user_id: str,
        agent_profile: str,
    ) -> list[dict[str, Any]]:
        body = {"jsonrpc": "2.0", "id": "expert-sync-tools", "method": "tools/list", "params": {}}
        response = await agent_mcp.dispatch_agent_mcp(db, org_id, user_id, agent_profile, body)
        if "error" in response:
            raise RuntimeError(response["error"].get("message", "upstream tools/list failed"))
        result = response.get("result") if isinstance(response.get("result"), dict) else {}
        tools = result.get("tools")
        return tools if isinstance(tools, list) else []

    @staticmethod
    async def call_upstream_tool(
        db: AsyncSession,
        org_id: str,
        user_id: str,
        agent_profile: str,
        upstream_tool_name: str,
        arguments: dict[str, Any],
        *,
        jsonrpc_id: Any = "expert-call",
    ) -> dict[str, Any]:
        body = {
            "jsonrpc": "2.0",
            "id": jsonrpc_id,
            "method": "tools/call",
            "params": {"name": upstream_tool_name, "arguments": arguments},
        }
        return await agent_mcp.dispatch_agent_mcp(db, org_id, user_id, agent_profile, body)

    @staticmethod
    def parse_upstream_result(response: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        if "error" in response:
            err = response["error"]
            data = err.get("data") if isinstance(err.get("data"), dict) else {}
            error_code = str(data.get("errorCode") or EXPERT_UPSTREAM_MCP_ERROR)
            return None, mcp_error_v2(response.get("id"), error_code, str(err.get("message") or ""), data=data)
        result = response.get("result")
        return result if isinstance(result, dict) else {}, None
