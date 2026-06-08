import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.services.hermes_skill.mcp_tool_mapper import McpToolMapper
from app.services.mcp_skill_gateway.auth import McpAuthContext, McpAuthFailure, resolve_mcp_user
from app.services.mcp_skill_gateway.constants import MCP_PROTOCOL_VERSION, MCP_SERVER_NAME
from app.services.mcp_skill_gateway.errors import (
    MCP_FORBIDDEN,
    MCP_INTERNAL_ERROR,
    MCP_INVALID_REQUEST,
    MCP_METHOD_NOT_FOUND,
    MCP_TOOLS_LIST_FAILED,
    MCP_UNAUTHORIZED,
    map_skill_error,
    mcp_error,
    mcp_success,
)
from app.services.mcp_skill_gateway.session import mark_initialized

logger = logging.getLogger(__name__)


def _log_mcp_error(
    error_code: str,
    method: str,
    *,
    user_id: str | None = None,
    org_id: str | None = None,
    reason: str = "",
) -> None:
    logger.warning(
        "MCP gateway error errorCode=%s userId=%s orgId=%s method=%s reason=%s",
        error_code,
        user_id or "",
        org_id or "",
        method,
        reason,
    )


async def dispatch(
    body: dict,
    authorization: str | None,
    db: AsyncSession,
) -> dict:
    jsonrpc_id = body.get("id", 1)
    method = body.get("method", "")

    if not isinstance(body.get("jsonrpc"), str) or body.get("jsonrpc") != "2.0":
        _log_mcp_error(MCP_INVALID_REQUEST, method, reason="jsonrpc must be 2.0")
        return mcp_error(jsonrpc_id, MCP_INVALID_REQUEST, "jsonrpc must be '2.0'")

    auth_result = await resolve_mcp_user(authorization, db)
    if isinstance(auth_result, McpAuthFailure):
        _log_mcp_error(auth_result.error_code, method, reason=auth_result.reason)
        return mcp_error(jsonrpc_id, auth_result.error_code, auth_result.reason)

    user = auth_result.user
    org = auth_result.org
    user_id = user.id

    if method == "initialize":
        return await _handle_initialize(body, jsonrpc_id, user_id, org.id)

    if method == "tools/list":
        return await _handle_tools_list(jsonrpc_id, user_id, org.id, db)

    if method == "tools/call":
        return await _handle_tools_call(body, jsonrpc_id, user_id, org.id, db)

    _log_mcp_error(
        MCP_METHOD_NOT_FOUND,
        method,
        user_id=user_id,
        org_id=org.id,
        reason=f"Unknown method: {method}",
    )
    return mcp_error(jsonrpc_id, MCP_METHOD_NOT_FOUND, f"Method not found: {method}")


async def dispatch_authenticated(
    body: dict,
    user_org: tuple[Any, Any],
    db: AsyncSession,
) -> dict:
    user, org = user_org
    jsonrpc_id = body.get("id", 1)
    method = body.get("method", "")

    if not isinstance(body.get("jsonrpc"), str) or body.get("jsonrpc") != "2.0":
        _log_mcp_error(MCP_INVALID_REQUEST, method, reason="jsonrpc must be 2.0")
        return mcp_error(jsonrpc_id, MCP_INVALID_REQUEST, "jsonrpc must be '2.0'")

    user_id = user.id if hasattr(user, "id") else ""

    if method == "initialize":
        return await _handle_initialize(body, jsonrpc_id, user_id, org.id)

    if method == "tools/list":
        return await _handle_tools_list(jsonrpc_id, user_id, org.id, db)

    if method == "tools/call":
        return await _handle_tools_call(body, jsonrpc_id, user_id, org.id, db)

    _log_mcp_error(
        MCP_METHOD_NOT_FOUND,
        method,
        user_id=user_id,
        org_id=org.id,
        reason=f"Unknown method: {method}",
    )
    return mcp_error(jsonrpc_id, MCP_METHOD_NOT_FOUND, f"Method not found: {method}")


async def _handle_initialize(
    body: dict,
    jsonrpc_id: Any,
    user_id: str,
    org_id: str,
) -> dict:
    mark_initialized(user_id, org_id)
    params = body.get("params") or {}
    protocol_version = params.get("protocolVersion") or MCP_PROTOCOL_VERSION
    return mcp_success(
        jsonrpc_id,
        {
            "protocolVersion": protocol_version,
            "capabilities": {
                "tools": {
                    "listChanged": True,
                },
            },
            "serverInfo": {
                "name": MCP_SERVER_NAME,
                "version": settings.APP_VERSION,
            },
        },
    )


async def _handle_tools_list(
    jsonrpc_id: Any,
    user_id: str,
    org_id: str,
    db: AsyncSession,
) -> dict:
    try:
        mapper = McpToolMapper(db)
        tools = await mapper.list_tools(org_id, user_id=user_id)
        return mcp_success(jsonrpc_id, {"tools": tools})
    except ForbiddenError as exc:
        _log_mcp_error(
            MCP_FORBIDDEN,
            "tools/list",
            user_id=user_id,
            org_id=org_id,
            reason=exc.message,
        )
        return mcp_error(jsonrpc_id, MCP_FORBIDDEN, exc.message)
    except Exception as exc:
        reason = str(exc)[:256]
        _log_mcp_error(
            MCP_TOOLS_LIST_FAILED,
            "tools/list",
            user_id=user_id,
            org_id=org_id,
            reason=reason,
        )
        return mcp_error(jsonrpc_id, MCP_TOOLS_LIST_FAILED, reason)


async def _handle_tools_call(
    body: dict,
    jsonrpc_id: Any,
    user_id: str,
    org_id: str,
    db: AsyncSession,
) -> dict:
    params = body.get("params", {})
    tool_name = params.get("name", "")
    if not tool_name:
        _log_mcp_error(
            MCP_INVALID_REQUEST,
            "tools/call",
            user_id=user_id,
            org_id=org_id,
            reason="missing params.name",
        )
        return mcp_error(jsonrpc_id, MCP_INVALID_REQUEST, "Invalid params: missing params.name")

    arguments = params.get("arguments", {})
    mapper = McpToolMapper(db)
    try:
        result = await mapper.call_tool(
            tool_name,
            arguments,
            org_id,
            user_id=user_id,
            jsonrpc_id=jsonrpc_id,
        )
    except (NotFoundError, BadRequestError, ForbiddenError) as exc:
        error_response = map_skill_error(jsonrpc_id, exc.message_key, exc.message)
        _log_mcp_error(
            error_response["error"]["data"]["errorCode"],
            "tools/call",
            user_id=user_id,
            org_id=org_id,
            reason=exc.message,
        )
        return error_response
    except Exception as exc:
        reason = str(exc)[:256]
        _log_mcp_error(
            MCP_INTERNAL_ERROR,
            "tools/call",
            user_id=user_id,
            org_id=org_id,
            reason=reason,
        )
        return mcp_error(jsonrpc_id, MCP_INTERNAL_ERROR, reason)

    return mcp_success(
        jsonrpc_id,
        {
            "content": [{"type": "text", "text": "任务已创建"}],
            "structuredContent": result,
        },
    )
