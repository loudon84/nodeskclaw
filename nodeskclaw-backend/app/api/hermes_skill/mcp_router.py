from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_member
from app.services.hermes_skill.mcp_tool_mapper import McpToolMapper

router = APIRouter()


def _ok(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


@router.post("/mcp")
async def mcp_jsonrpc(
    body: dict,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    _, org = user_org
    method = body.get("method", "")
    mapper = McpToolMapper(db)

    if method == "tools/list":
        tools = await mapper.list_tools(org.id)
        return {"jsonrpc": "2.0", "id": body.get("id"), "result": {"tools": tools}}

    if method == "tools/call":
        params = body.get("params", {})
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        result = await mapper.call_tool(tool_name, arguments, org.id)
        return {"jsonrpc": "2.0", "id": body.get("id"), "result": result}

    return {"jsonrpc": "2.0", "id": body.get("id"), "error": {"code": -32601, "message": "Method not found"}}
