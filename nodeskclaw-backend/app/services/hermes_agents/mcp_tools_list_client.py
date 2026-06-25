import logging
from typing import Any

import httpx

from app.core.exceptions import BadRequestError

logger = logging.getLogger(__name__)

REGISTRY_TOOL_PREFIXES = (
    "hermes.instances.",
    "hermes.instance.",
    "hermes.skills.",
    "genehub.",
)


def is_business_skill_tool(name: str) -> bool:
    if not name:
        return False
    for prefix in REGISTRY_TOOL_PREFIXES:
        if name.startswith(prefix):
            return False
    return True


def filter_tools(
    tools: list[dict[str, Any]],
    *,
    tool_filter: str = "skill_only",
    include_registry_tools: bool = False,
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for tool in tools:
        name = tool.get("name") or ""
        if tool_filter == "skill_only" and not include_registry_tools:
            if not is_business_skill_tool(name):
                continue
        filtered.append({
            "name": name,
            "description": tool.get("description") or "",
            "inputSchema": tool.get("inputSchema") or {},
        })
    return filtered


def sanitize_tool_snapshot(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "name": t.get("name"),
            "description": t.get("description"),
            "inputSchema": t.get("inputSchema"),
        }
        for t in tools
    ]


async def fetch_mcp_tools_list(
    url: str,
    token: str,
    *,
    params: dict | None = None,
    timeout: float = 30.0,
) -> list[dict[str, Any]]:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": params or {},
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "X-Client": "nodeskclaw-router-sync",
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPError as exc:
        logger.warning("MCP tools/list request failed for %s: %s", url, exc)
        raise BadRequestError(
            "无法连接 MCP Skill Gateway，请检查 NODESKCLAW_MCP_URL",
            "errors.mcp_router.mcp_unreachable",
        ) from exc

    if "error" in body:
        err = body["error"]
        message = err.get("message") if isinstance(err, dict) else str(err)
        raise BadRequestError(
            f"MCP tools/list 失败: {message}",
            "errors.mcp_router.mcp_unreachable",
        )

    result = body.get("result") or {}
    tools = result.get("tools")
    if not isinstance(tools, list):
        raise BadRequestError(
            "MCP tools/list 响应格式无效",
            "errors.mcp_router.mcp_unreachable",
        )
    return tools
