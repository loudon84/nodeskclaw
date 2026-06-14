import json
import logging
import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.services.hermes_skill.mcp_tool_mapper import McpToolMapper
from app.services.mcp_skill_gateway.approval_service import check_tool_grant, get_grant_annotation
from app.services.mcp_skill_gateway.audit_service import log_mcp_call
from app.services.mcp_skill_gateway.auth import McpAuthContext, McpAuthFailure, resolve_mcp_user
from app.services.mcp_skill_gateway.constants import MCP_PROTOCOL_VERSION, MCP_SERVER_NAME
from app.services.mcp_skill_gateway.errors import (
    MCP_INTERNAL_ERROR,
    MCP_INVALID_ARGUMENTS,
    MCP_METHOD_NOT_FOUND,
    MCP_TOOLS_LIST_FAILED,
    map_app_error,
    mcp_error_v2,
    mcp_success,
)
from app.services.mcp_skill_gateway.genehub_tools import (
    GeneHubMcpToolProvider,
    extract_genehub_error_context,
    is_genehub_tool,
    summarize_genehub_result,
)
from app.services.mcp_skill_gateway.hermes_docker_tools import (
    HermesDockerToolProvider,
    extract_instance_id_from_arguments,
    is_hermes_docker_tool,
    summarize_tool_result,
)
from app.services.mcp_skill_gateway.hermes_instance_resolver import resolve_instance_ref
from app.services.mcp_skill_gateway.mcp_tool_registry import (
    build_tool_descriptor,
    get_tool,
    list_enabled_tools,
)
from app.services.mcp_skill_gateway.session import get_client_name, mark_initialized

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


def _tool_call_success(jsonrpc_id: Any, result: dict[str, Any]) -> dict:
    return mcp_success(
        jsonrpc_id,
        {
            "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
            "isError": False,
        },
    )


def _extra_error_data(exc: Exception, arguments: dict[str, Any]) -> dict[str, Any]:
    data: dict[str, Any] = extract_genehub_error_context(arguments)
    ref = extract_instance_id_from_arguments(arguments)
    if ref:
        data["instance_ref"] = ref
    if isinstance(exc, BadRequestError) and exc.message_key == "errors.external_docker.instance_ambiguous":
        data["reason"] = "multiple_instances_matched"
    return data


async def _resolve_tool_instance_id(
    *,
    tool_name: str,
    arguments: dict[str, Any],
    org_id: str,
    user: Any,
    db: AsyncSession,
) -> tuple[str | None, dict | None]:
    if not is_hermes_docker_tool(tool_name) or tool_name == "hermes.instances.list":
        return None, None

    instance_ref = extract_instance_id_from_arguments(arguments)
    if not instance_ref:
        return None, mcp_error_v2(
            0,
            MCP_INVALID_ARGUMENTS,
            "Invalid params: missing instance_ref",
            data={"toolName": tool_name},
        )

    try:
        resolved = await resolve_instance_ref(instance_ref, org_id, user, db)
    except (NotFoundError, BadRequestError, ForbiddenError) as exc:
        return None, map_app_error(
            0,
            exc.message_key,
            exc.message,
            extra_data=_extra_error_data(exc, arguments),
        )
    return resolved.id, None


async def _enforce_tool_grant(
    *,
    jsonrpc_id: Any,
    tool_name: str,
    arguments: dict[str, Any],
    org_id: str,
    user_id: str,
    user: Any,
    db: AsyncSession,
) -> tuple[dict | None, Any]:
    tool_meta = get_tool(tool_name)
    if not tool_meta or not tool_meta.requires_approval:
        return None, None

    instance_id, resolve_error = await _resolve_tool_instance_id(
        tool_name=tool_name,
        arguments=arguments,
        org_id=org_id,
        user=user,
        db=db,
    )
    if resolve_error:
        resolve_error["id"] = jsonrpc_id
        return resolve_error, None

    grant_check = await check_tool_grant(
        db,
        org_id=org_id,
        user_id=user_id,
        tool=tool_meta,
        instance_id=instance_id,
        instance_ref=extract_instance_id_from_arguments(arguments),
        arguments=arguments,
    )
    if grant_check.allowed:
        return None, grant_check.grant

    return mcp_error_v2(
        jsonrpc_id,
        grant_check.error_code or MCP_INTERNAL_ERROR,
        grant_check.message,
        data=grant_check.data,
    ), None


async def _execute_gateway_tool_call(
    *,
    jsonrpc_id: Any,
    tool_name: str,
    arguments: dict[str, Any],
    org_id: str,
    user_id: str,
    user: Any,
    db: AsyncSession,
    provider: Any,
    summarize_fn: Any,
) -> dict:
    tool_meta = get_tool(tool_name)
    client_name = get_client_name(user_id, org_id)
    started = time.perf_counter()
    instance_id: str | None = None

    grant_error, active_grant = await _enforce_tool_grant(
        jsonrpc_id=jsonrpc_id,
        tool_name=tool_name,
        arguments=arguments,
        org_id=org_id,
        user_id=user_id,
        user=user,
        db=db,
    )
    if grant_error:
        duration_ms = int((time.perf_counter() - started) * 1000)
        error_data = grant_error.get("error", {}).get("data", {})
        ref = extract_instance_id_from_arguments(arguments)
        if ref and is_hermes_docker_tool(tool_name):
            try:
                resolved = await resolve_instance_ref(ref, org_id, user, db)
                instance_id = resolved.id
            except (NotFoundError, BadRequestError, ForbiddenError):
                instance_id = None
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
            error_message=grant_error.get("error", {}).get("message"),
            client_name=client_name,
            permission=tool_meta.permission if tool_meta else None,
            risk_level=tool_meta.risk_level if tool_meta else None,
        )
        _log_mcp_error(
            error_data.get("errorCode", MCP_INTERNAL_ERROR),
            "tools/call",
            user_id=user_id,
            org_id=org_id,
            reason=grant_error.get("error", {}).get("message", ""),
        )
        return grant_error

    try:
        call_kwargs: dict[str, Any] = {}
        if is_hermes_docker_tool(tool_name):
            call_kwargs["grant_constraints"] = (
                active_grant.constraints_json if active_grant else None
            )
        result = await provider.call_tool(
            tool_name,
            arguments,
            org_id,
            user_id,
            **call_kwargs,
        )
        if is_hermes_docker_tool(tool_name) and tool_name != "hermes.instances.list":
            ref = extract_instance_id_from_arguments(arguments)
            try:
                resolved = await resolve_instance_ref(ref or None, org_id, user, db)
                instance_id = resolved.id
            except (NotFoundError, BadRequestError, ForbiddenError):
                instance_id = None
        duration_ms = int((time.perf_counter() - started) * 1000)
        await log_mcp_call(
            db,
            org_id=org_id,
            user_id=user_id,
            tool_name=tool_name,
            status="success",
            duration_ms=duration_ms,
            instance_id=instance_id,
            arguments=arguments,
            result_summary=summarize_fn(tool_name, result),
            client_name=client_name,
            permission=tool_meta.permission if tool_meta else None,
            risk_level=tool_meta.risk_level if tool_meta else None,
        )
        return _tool_call_success(jsonrpc_id, result)
    except (NotFoundError, BadRequestError, ForbiddenError) as exc:
        error_response = map_app_error(
            jsonrpc_id,
            exc.message_key,
            exc.message,
            extra_data=_extra_error_data(exc, arguments),
        )
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
            client_name=client_name,
            permission=tool_meta.permission if tool_meta else None,
            risk_level=tool_meta.risk_level if tool_meta else None,
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
            client_name=client_name,
            permission=tool_meta.permission if tool_meta else None,
            risk_level=tool_meta.risk_level if tool_meta else None,
        )
        _log_mcp_error(
            MCP_INTERNAL_ERROR,
            "tools/call",
            user_id=user_id,
            org_id=org_id,
            reason=reason,
        )
        return mcp_error_v2(jsonrpc_id, MCP_INTERNAL_ERROR, reason)


async def dispatch(
    body: dict,
    authorization: str | None,
    db: AsyncSession,
) -> dict:
    jsonrpc_id = body.get("id", 1)
    method = body.get("method", "")

    if not isinstance(body.get("jsonrpc"), str) or body.get("jsonrpc") != "2.0":
        _log_mcp_error(MCP_INVALID_ARGUMENTS, method, reason="jsonrpc must be 2.0")
        return mcp_error_v2(jsonrpc_id, MCP_INVALID_ARGUMENTS, "jsonrpc must be '2.0'")

    auth_result = await resolve_mcp_user(authorization, db)
    if isinstance(auth_result, McpAuthFailure):
        _log_mcp_error(auth_result.error_code, method, reason=auth_result.reason)
        return mcp_error_v2(jsonrpc_id, auth_result.error_code, auth_result.reason)

    user = auth_result.user
    org = auth_result.org
    user_id = user.id

    if method == "initialize":
        return await _handle_initialize(body, jsonrpc_id, user_id, org.id)

    if method == "tools/list":
        return await _handle_tools_list(jsonrpc_id, user_id, org.id, db)

    if method == "tools/call":
        return await _handle_tools_call(body, jsonrpc_id, user_id, org.id, db, user)

    _log_mcp_error(
        MCP_METHOD_NOT_FOUND,
        method,
        user_id=user_id,
        org_id=org.id,
        reason=f"Unknown method: {method}",
    )
    return mcp_error_v2(jsonrpc_id, MCP_METHOD_NOT_FOUND, f"Method not found: {method}")


async def dispatch_authenticated(
    body: dict,
    user_org: tuple[Any, Any],
    db: AsyncSession,
) -> dict:
    user, org = user_org
    jsonrpc_id = body.get("id", 1)
    method = body.get("method", "")

    if not isinstance(body.get("jsonrpc"), str) or body.get("jsonrpc") != "2.0":
        _log_mcp_error(MCP_INVALID_ARGUMENTS, method, reason="jsonrpc must be 2.0")
        return mcp_error_v2(jsonrpc_id, MCP_INVALID_ARGUMENTS, "jsonrpc must be '2.0'")

    user_id = user.id if hasattr(user, "id") else ""

    if method == "initialize":
        return await _handle_initialize(body, jsonrpc_id, user_id, org.id)

    if method == "tools/list":
        return await _handle_tools_list(jsonrpc_id, user_id, org.id, db)

    if method == "tools/call":
        return await _handle_tools_call(body, jsonrpc_id, user_id, org.id, db, user)

    _log_mcp_error(
        MCP_METHOD_NOT_FOUND,
        method,
        user_id=user_id,
        org_id=org.id,
        reason=f"Unknown method: {method}",
    )
    return mcp_error_v2(jsonrpc_id, MCP_METHOD_NOT_FOUND, f"Method not found: {method}")


async def _handle_initialize(
    body: dict,
    jsonrpc_id: Any,
    user_id: str,
    org_id: str,
) -> dict:
    params = body.get("params") or {}
    client_info = params.get("clientInfo") or {}
    mark_initialized(
        user_id,
        org_id,
        client_name=str(client_info.get("name") or "") or None,
        client_version=str(client_info.get("version") or "") or None,
    )
    protocol_version = params.get("protocolVersion") or MCP_PROTOCOL_VERSION
    return mcp_success(
        jsonrpc_id,
        {
            "protocolVersion": protocol_version,
            "capabilities": {
                "tools": {},
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
    registry_tools: list[dict[str, Any]] = []
    for tool in list_enabled_tools():
        auth_annotations = None
        if tool.requires_approval:
            auth_annotations = await get_grant_annotation(
                db,
                org_id=org_id,
                user_id=user_id,
                instance_id=None,
                tool_name=tool.name,
            )
        registry_tools.append(build_tool_descriptor(tool, auth_annotations))
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for tool in registry_tools + skill_tools:
        name = tool.get("name")
        if not name or name in seen:
            continue
        seen.add(name)
        merged.append(tool)
    return merged


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
            exc.message_key or MCP_INTERNAL_ERROR,
            "tools/list",
            user_id=user_id,
            org_id=org_id,
            reason=exc.message,
        )
        return map_app_error(jsonrpc_id, exc.message_key, exc.message)
    except Exception as exc:
        reason = str(exc)[:256]
        _log_mcp_error(
            MCP_TOOLS_LIST_FAILED,
            "tools/list",
            user_id=user_id,
            org_id=org_id,
            reason=reason,
        )
        return mcp_error_v2(jsonrpc_id, MCP_TOOLS_LIST_FAILED, reason)


def _is_hermes_gateway_tool(tool_name: str) -> bool:
    return is_hermes_docker_tool(tool_name)


def _is_genehub_gateway_tool(tool_name: str) -> bool:
    return is_genehub_tool(tool_name)


async def _handle_tools_call(
    body: dict,
    jsonrpc_id: Any,
    user_id: str,
    org_id: str,
    db: AsyncSession,
    user: Any,
) -> dict:
    params = body.get("params", {})
    tool_name = params.get("name", "")
    if not tool_name:
        _log_mcp_error(
            MCP_INVALID_ARGUMENTS,
            "tools/call",
            user_id=user_id,
            org_id=org_id,
            reason="missing params.name",
        )
        return mcp_error_v2(jsonrpc_id, MCP_INVALID_ARGUMENTS, "Invalid params: missing params.name")

    arguments = params.get("arguments") or {}
    if not isinstance(arguments, dict):
        arguments = {}

    tool_meta = get_tool(tool_name)
    client_name = get_client_name(user_id, org_id)
    started = time.perf_counter()

    if _is_genehub_gateway_tool(tool_name):
        return await _execute_gateway_tool_call(
            jsonrpc_id=jsonrpc_id,
            tool_name=tool_name,
            arguments=arguments,
            org_id=org_id,
            user_id=user_id,
            user=user,
            db=db,
            provider=GeneHubMcpToolProvider(db),
            summarize_fn=summarize_genehub_result,
        )

    if _is_hermes_gateway_tool(tool_name):
        return await _execute_gateway_tool_call(
            jsonrpc_id=jsonrpc_id,
            tool_name=tool_name,
            arguments=arguments,
            org_id=org_id,
            user_id=user_id,
            user=user,
            db=db,
            provider=HermesDockerToolProvider(db),
            summarize_fn=summarize_tool_result,
        )

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
            status="success",
            duration_ms=duration_ms,
            arguments=arguments,
            result_summary={"task_id": result.get("task_id"), "status": result.get("status")},
            client_name=client_name,
        )
    except (NotFoundError, BadRequestError, ForbiddenError) as exc:
        error_response = map_app_error(jsonrpc_id, exc.message_key, exc.message)
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
            client_name=client_name,
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
            arguments=arguments,
            error_code=MCP_INTERNAL_ERROR,
            error_message=reason,
            client_name=client_name,
        )
        _log_mcp_error(
            MCP_INTERNAL_ERROR,
            "tools/call",
            user_id=user_id,
            org_id=org_id,
            reason=reason,
        )
        return mcp_error_v2(jsonrpc_id, MCP_INTERNAL_ERROR, reason)

    return _tool_call_success(jsonrpc_id, result)
