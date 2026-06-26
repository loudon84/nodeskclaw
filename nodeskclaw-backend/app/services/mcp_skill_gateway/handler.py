import json
import logging
import time
from types import SimpleNamespace
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.services.hermes_skill.mcp_tool_mapper import McpToolMapper
from app.services.mcp_skill_gateway.builtin_task_tool_executor import BuiltinTaskToolExecutor
from app.services.mcp_skill_gateway.builtin_task_tools import (
    is_builtin_task_tool,
    list_builtin_task_tool_descriptors,
)
from app.services.mcp_skill_gateway.mcp_task_dedup_service import build_mcp_task_dedup_key
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
    resolve_approval_mode,
)
from app.services.hermes_skill.hermes_client_service import (
    HEADER_CLIENT,
    HEADER_DEVICE_ID,
    HEADER_HERMES_PROFILE,
    HEADER_PROXY_VERSION,
)
from app.services.mcp_skill_gateway.session import get_client_name, mark_initialized

logger = logging.getLogger(__name__)


def _normalize_headers(headers: dict | None) -> dict[str, str]:
    if not headers:
        return {}
    return {str(k).lower(): str(v) for k, v in headers.items()}


def _build_client_context(
    headers: dict | None,
    auth_ctx: McpAuthContext | None = None,
) -> dict | None:
    normalized = _normalize_headers(headers)
    context: dict[str, Any] = {
        "desktop_device_id": normalized.get(HEADER_DEVICE_ID.lower()),
        "profile": normalized.get(HEADER_HERMES_PROFILE.lower()),
        "client": normalized.get(HEADER_CLIENT.lower()),
        "proxy_version": normalized.get(HEADER_PROXY_VERSION.lower()),
    }
    if auth_ctx and auth_ctx.auth_type == "mcp_client_token":
        context.update({
            "source": "mcp_skill_gateway",
            "auth_type": "mcp_client_token",
            "mcp_client_token_id": auth_ctx.mcp_client_token_id,
            "mcp_client_token_prefix": auth_ctx.mcp_client_token_prefix,
            "hermes_agent_id": auth_ctx.hermes_agent_id,
            "mcp_profile": auth_ctx.profile,
            "mcp_workspace_id": auth_ctx.workspace_id,
            "mcp_client_name": get_client_name(auth_ctx.user.id, auth_ctx.org.id),
        })
    cleaned = {key: value for key, value in context.items() if value}
    return cleaned or None


def _inject_request_fingerprint(
    client_context: dict | None,
    *,
    org_id: str,
    auth_ctx: McpAuthContext | None,
    tool_name: str,
    arguments: dict[str, Any],
) -> dict | None:
    if not settings.MCP_TASK_DEDUP_ENABLED or not auth_ctx:
        return client_context
    fingerprint = build_mcp_task_dedup_key(org_id, auth_ctx, tool_name, arguments)
    merged = dict(client_context or {})
    merged["request_fingerprint"] = fingerprint
    return merged


def _tool_approval_mode(tool_name: str) -> str | None:
    tool_meta = get_tool(tool_name)
    if not tool_meta:
        return None
    return resolve_approval_mode(tool_meta)


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


def _hermes_skill_tool_call_success(jsonrpc_id: Any, result: dict[str, Any]) -> dict:
    return mcp_success(
        jsonrpc_id,
        {
            "content": [{"type": "text", "text": "任务已创建"}],
            "structuredContent": result,
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
    if not tool_meta:
        return None, None
    mode = resolve_approval_mode(tool_meta)
    if mode in ("none", "desktop"):
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
            approval_mode=_tool_approval_mode(tool_name),
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
            approval_mode=_tool_approval_mode(tool_name),
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
            approval_mode=_tool_approval_mode(tool_name),
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
            approval_mode=_tool_approval_mode(tool_name),
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
    request_headers: dict | None = None,
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
        params = body.get("params") or {}
        return await _handle_tools_list(
            jsonrpc_id, user_id, org.id, db,
            params=params, request_headers=request_headers, auth_ctx=auth_result,
        )

    if method == "tools/call":
        return await _handle_tools_call(
            body, jsonrpc_id, user_id, org.id, db, user,
            request_headers=request_headers, auth_ctx=auth_result,
        )

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
    request_headers: dict | None = None,
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
        params = body.get("params") or {}
        return await _handle_tools_list(
            jsonrpc_id, user_id, org.id, db, params=params, request_headers=request_headers,
        )

    if method == "tools/call":
        return await _handle_tools_call(
            body, jsonrpc_id, user_id, org.id, db, user, request_headers=request_headers,
        )

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


async def _collect_tools(
    user_id: str,
    org_id: str,
    db: AsyncSession,
    *,
    agent_alias: str | None = None,
    profile: str | None = None,
    workspace_id: str | None = None,
    allowed_skills: list[str] | None = None,
) -> list[dict[str, Any]]:
    mapper = McpToolMapper(db)
    skill_tools = await mapper.list_tools(
        org_id,
        user_id=user_id,
        agent_alias=agent_alias,
        profile=profile,
        workspace_id=workspace_id,
    )
    if allowed_skills:
        allowed_set = set(allowed_skills)
        skill_tools = [t for t in skill_tools if t.get("name") in allowed_set]
    registry_tools: list[dict[str, Any]] = []
    if allowed_skills is None:
        for tool in list_enabled_tools():
            auth_annotations = None
            mode = resolve_approval_mode(tool)
            if mode in ("server", "hybrid"):
                auth_annotations = await get_grant_annotation(
                    db,
                    org_id=org_id,
                    user_id=user_id,
                    instance_id=None,
                    tool_name=tool.name,
                    tool=tool,
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
    for tool in list_builtin_task_tool_descriptors():
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
    *,
    params: dict | None = None,
    request_headers: dict | None = None,
    auth_ctx: McpAuthContext | None = None,
) -> dict:
    try:
        params = params or {}
        normalized = _normalize_headers(request_headers)
        agent_alias = params.get("agent_alias")
        profile = params.get("profile")
        workspace_id = params.get("workspace_id")
        if not profile and auth_ctx and auth_ctx.profile:
            profile = auth_ctx.profile
        if not profile:
            profile = normalized.get(HEADER_HERMES_PROFILE.lower())
        if not workspace_id and auth_ctx and auth_ctx.workspace_id:
            workspace_id = auth_ctx.workspace_id
        allowed_skills = auth_ctx.allowed_skills if auth_ctx and auth_ctx.auth_type == "mcp_client_token" else None
        tools = await _collect_tools(
            user_id,
            org_id,
            db,
            agent_alias=agent_alias,
            profile=profile,
            workspace_id=workspace_id,
            allowed_skills=allowed_skills,
        )
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
    *,
    request_headers: dict | None = None,
    auth_ctx: McpAuthContext | None = None,
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

    if auth_ctx and auth_ctx.auth_type == "mcp_client_token":
        if _is_genehub_gateway_tool(tool_name) or _is_hermes_gateway_tool(tool_name):
            return mcp_error_v2(jsonrpc_id, MCP_INTERNAL_ERROR, "Tool not allowed for MCP client token")
        if not is_builtin_task_tool(tool_name):
            if auth_ctx.allowed_skills and tool_name not in set(auth_ctx.allowed_skills):
                return mcp_error_v2(jsonrpc_id, MCP_INTERNAL_ERROR, "Tool not allowed for MCP client token")

    tool_meta = get_tool(tool_name)
    client_name = get_client_name(user_id, org_id)
    started = time.perf_counter()

    if is_builtin_task_tool(tool_name):
        effective_ctx = auth_ctx or McpAuthContext(
            user=user,
            org=SimpleNamespace(id=org_id),
            auth_type="user_jwt",
        )
        try:
            result = await BuiltinTaskToolExecutor(db).call(
                tool_name=tool_name,
                arguments=arguments,
                auth_ctx=effective_ctx,
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
                result_summary={"tool": tool_name},
                client_name=client_name,
            )
            return mcp_success(jsonrpc_id, result)
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
    normalized = _normalize_headers(request_headers)
    profile_name = auth_ctx.profile if auth_ctx and auth_ctx.profile else normalized.get(HEADER_HERMES_PROFILE.lower())
    client_context = _build_client_context(request_headers, auth_ctx)
    client_context = _inject_request_fingerprint(
        client_context,
        org_id=org_id,
        auth_ctx=auth_ctx,
        tool_name=tool_name,
        arguments=arguments,
    )
    try:
        result = await mapper.call_tool(
            tool_name,
            arguments,
            org_id,
            user_id=user_id,
            jsonrpc_id=jsonrpc_id,
            client_context=client_context,
            profile_name=profile_name,
            auth_ctx=auth_ctx,
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
        await db.commit()
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

    return _hermes_skill_tool_call_success(jsonrpc_id, result)
