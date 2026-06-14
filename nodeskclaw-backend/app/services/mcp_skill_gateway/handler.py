import logging
import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.services.hermes_skill.mcp_tool_mapper import McpToolMapper
from app.services.mcp_skill_gateway.audit_service import log_mcp_call
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
from app.services.mcp_skill_gateway.hermes_docker_tools import (
    HermesDockerToolProvider,
    extract_instance_id_from_arguments,
    is_genehub_tool,
    is_hermes_docker_tool,
    list_tools as list_docker_tools,
    resolve_instance_ref,
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


async def _collect_tools(user_id: str, org_id: str, db: AsyncSession) -> list[dict[str, Any]]:
    mapper = McpToolMapper(db)
    skill_tools = await mapper.list_tools(org_id, user_id=user_id)
    docker_tools = list_docker_tools()
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for tool in docker_tools + skill_tools:
        name = tool.get("name")
        if not name or name in seen:
            continue
        seen.add(name)
        merged.append(tool)
    return merged


async def count_available_tools(user_id: str, org_id: str, db: AsyncSession) -> int:
    return len(await _collect_tools(user_id, org_id, db))


async def _handle_tools_list(
    jsonrpc_id: Any,
    user_id: str,
    org_id: str,
    db: AsyncSession,
) -> dict:
    try:
        tools = await _collect_tools(user_id, org_id, db)
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


def _is_docker_gateway_tool(tool_name: str) -> bool:
    return is_hermes_docker_tool(tool_name) or is_genehub_tool(tool_name)


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

    arguments = params.get("arguments") or {}
    if not isinstance(arguments, dict):
        arguments = {}

    started = time.perf_counter()
    instance_id: str | None = None

    if _is_docker_gateway_tool(tool_name):
        provider = HermesDockerToolProvider(db)
        try:
            result = await provider.call_tool(tool_name, arguments, org_id, user_id)
            if tool_name != "hermes.instances.list":
                ref = extract_instance_id_from_arguments(arguments)
                if ref:
                    try:
                        resolved = await resolve_instance_ref(ref, org_id, db)
                        instance_id = resolved.id
                    except (NotFoundError, BadRequestError):
                        instance_id = None
            duration_ms = int((time.perf_counter() - started) * 1000)
            await log_mcp_call(
                db,
                org_id=org_id,
                user_id=user_id,
                tool_name=tool_name,
                status="ok",
                duration_ms=duration_ms,
                instance_id=instance_id,
                arguments=arguments,
            )
            return mcp_success(
                jsonrpc_id,
                {
                    "content": [{"type": "text", "text": "ok"}],
                    "structuredContent": result,
                },
            )
        except (NotFoundError, BadRequestError, ForbiddenError) as exc:
            error_response = map_skill_error(jsonrpc_id, exc.message_key, exc.message)
            duration_ms = int((time.perf_counter() - started) * 1000)
            error_data = error_response.get("error", {}).get("data", {})
            await log_mcp_call(
                db,
                org_id=org_id,
                user_id=user_id,
                tool_name=tool_name,
                status="failed",
                duration_ms=duration_ms,
                instance_id=instance_id,
                arguments=arguments,
                error_code=error_data.get("errorCode"),
                error_message=exc.message,
            )
            _log_mcp_error(
                error_data.get("errorCode", MCP_INTERNAL_ERROR),
                "tools/call",
                user_id=user_id,
                org_id=org_id,
                reason=exc.message,
            )
            return error_response
        except Exception as exc:
            reason = str(exc)[:256]
            duration_ms = int((time.perf_counter() - started) * 1000)
            await log_mcp_call(
                db,
                org_id=org_id,
                user_id=user_id,
                tool_name=tool_name,
                status="failed",
                duration_ms=duration_ms,
                instance_id=instance_id,
                arguments=arguments,
                error_code=MCP_INTERNAL_ERROR,
                error_message=reason,
            )
            _log_mcp_error(
                MCP_INTERNAL_ERROR,
                "tools/call",
                user_id=user_id,
                org_id=org_id,
                reason=reason,
            )
            return mcp_error(jsonrpc_id, MCP_INTERNAL_ERROR, reason)

    mapper = McpToolMapper(db)
    try:
        result = await mapper.call_tool(
            tool_name,
            arguments,
            org_id,
            user_id=user_id,
            jsonrpc_id=jsonrpc_id,
        )
        duration_ms = int((time.perf_counter() - started) * 1000)
        await log_mcp_call(
            db,
            org_id=org_id,
            user_id=user_id,
            tool_name=tool_name,
            status="ok",
            duration_ms=duration_ms,
            arguments=arguments,
        )
    except (NotFoundError, BadRequestError, ForbiddenError) as exc:
        error_response = map_skill_error(jsonrpc_id, exc.message_key, exc.message)
        duration_ms = int((time.perf_counter() - started) * 1000)
        error_data = error_response.get("error", {}).get("data", {})
        await log_mcp_call(
            db,
            org_id=org_id,
            user_id=user_id,
            tool_name=tool_name,
            status="failed",
            duration_ms=duration_ms,
            arguments=arguments,
            error_code=error_data.get("errorCode"),
            error_message=exc.message,
        )
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
        duration_ms = int((time.perf_counter() - started) * 1000)
        await log_mcp_call(
            db,
            org_id=org_id,
            user_id=user_id,
            tool_name=tool_name,
            status="failed",
            duration_ms=duration_ms,
            arguments=arguments,
            error_code=MCP_INTERNAL_ERROR,
            error_message=reason,
        )
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
