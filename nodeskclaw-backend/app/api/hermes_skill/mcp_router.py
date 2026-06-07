from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_member
from app.core.exceptions import NotFoundError, BadRequestError, ForbiddenError
from app.services.hermes_skill.mcp_tool_mapper import McpToolMapper

router = APIRouter()

_JSONRPC_ERROR_MAP = {
    "errors.skill.tool_not_found": -32001,
    "errors.skill.tool_not_installed": -32002,
    "errors.skill.permission_denied": -32003,
    "errors.skill.input_schema_validation_failed": -32004,
}


def _jsonrpc_error(jsonrpc_id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": jsonrpc_id, "error": {"code": code, "message": message}}


@router.post("/mcp")
async def mcp_jsonrpc(
    body: dict,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    jsonrpc_id = body.get("id", 1)
    method = body.get("method", "")

    if not isinstance(body.get("jsonrpc"), str) or body.get("jsonrpc") != "2.0":
        return _jsonrpc_error(jsonrpc_id, -32600, "Invalid Request: jsonrpc must be '2.0'")

    mapper = McpToolMapper(db)
    user_id = user.id if hasattr(user, "id") else ""

    if method == "tools/list":
        tools = await mapper.list_tools(org.id, user_id=user_id)
        return {"jsonrpc": "2.0", "id": jsonrpc_id, "result": {"tools": tools}}

    if method == "tools/call":
        params = body.get("params", {})
        tool_name = params.get("name", "")
        if not tool_name:
            return _jsonrpc_error(jsonrpc_id, -32602, "Invalid params: missing params.name")
        arguments = params.get("arguments", {})
        try:
            result = await mapper.call_tool(tool_name, arguments, org.id, user_id=user_id, jsonrpc_id=jsonrpc_id)
        except NotFoundError as exc:
            code = _JSONRPC_ERROR_MAP.get(exc.message_key, -32001)
            return _jsonrpc_error(jsonrpc_id, code, exc.message)
        except BadRequestError as exc:
            code = _JSONRPC_ERROR_MAP.get(exc.message_key, -32004)
            return _jsonrpc_error(jsonrpc_id, code, exc.message)
        except ForbiddenError as exc:
            code = _JSONRPC_ERROR_MAP.get(exc.message_key, -32003)
            return _jsonrpc_error(jsonrpc_id, code, exc.message)
        except Exception as exc:
            return _jsonrpc_error(jsonrpc_id, -32005, f"Task creation failed: {str(exc)[:256]}")
        return {
            "jsonrpc": "2.0",
            "id": jsonrpc_id,
            "result": {
                "content": [{"type": "text", "text": "任务已创建"}],
                "structuredContent": result,
            },
        }

    return _jsonrpc_error(jsonrpc_id, -32601, "Method not found")
