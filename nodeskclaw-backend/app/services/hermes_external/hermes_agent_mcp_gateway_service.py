"""Per-agent Hermes MCP Gateway: tools/list and tools/call over API_SERVER skills."""

from __future__ import annotations

import logging
import time
from typing import Any

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException, BadRequestError, ForbiddenError, NotFoundError
from app.schemas.hermes_instance_skill import HermesMcpGatewayStatusResponse, HermesMcpToolItem
from app.services.hermes_external import hermes_instance_skill_service as instance_skill_service
from app.services.hermes_external.hermes_api_server_client import HermesApiServerClient
from app.services.hermes_external.hermes_docker_binding_service import HermesDockerBindingService
from app.services.hermes_external.hermes_env_parser import parse_env_file
from app.services.hermes_skill.hermes_skill_authorization_service import HermesSkillAuthorizationService
from app.services.mcp_skill_gateway.audit_service import log_mcp_call
from app.services.mcp_skill_gateway.errors import map_app_error, mcp_error_v2, mcp_success

logger = logging.getLogger(__name__)

MCP_SKILL_PERMISSION_DENIED = "skill_permission_denied"
MCP_TOOL_NAME_INVALID = "mcp_tool_name_invalid"

_TOOL_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "prompt": {
            "type": "string",
            "description": "User task or instruction for this Hermes skill.",
        },
        "context": {
            "type": "object",
            "description": "Optional structured context.",
        },
    },
    "required": ["prompt"],
}


def mcp_endpoint_for_agent(agent_profile: str) -> str:
    return f"/api/v1/hermes/mcp/{agent_profile}"


def _gateway_status_from_error(exc: Exception) -> str:
    if isinstance(exc, ForbiddenError):
        return "unauthorized"
    if isinstance(exc, AppException) and exc.status_code == 503:
        return "offline"
    if isinstance(exc, AppException) and exc.status_code == 409:
        return "unconfigured"
    return "offline"


async def get_gateway_status(
    db: AsyncSession,
    org_id: str,
    agent_profile: str,
    *,
    force_refresh: bool = False,
) -> HermesMcpGatewayStatusResponse:
    binding = HermesDockerBindingService(db)
    record = await binding.get_by_profile(org_id, agent_profile)
    if not record:
        raise NotFoundError(
            message="Hermes Agent 实例不存在",
            message_key="errors.hermes.agent_instance_not_found",
        )

    enabled = instance_skill_service.is_gateway_configured(record.gateway_url, record.env_file)
    endpoint = mcp_endpoint_for_agent(agent_profile)
    if not enabled:
        return HermesMcpGatewayStatusResponse(
            agent_profile=agent_profile,
            enabled=False,
            status="unconfigured",
            endpoint=endpoint,
            skills_count=0,
            tools_count=0,
            warnings=["API_SERVER is not configured for this agent."],
        )

    try:
        skill_list = await instance_skill_service.list_instance_skills(
            db,
            org_id,
            agent_profile,
            force_refresh=force_refresh,
        )
        return HermesMcpGatewayStatusResponse(
            agent_profile=agent_profile,
            enabled=True,
            status="online",
            endpoint=endpoint,
            skills_count=skill_list.total,
            tools_count=skill_list.total,
            last_refreshed_at=skill_list.last_refreshed_at,
            warnings=skill_list.warnings,
        )
    except Exception as exc:
        return HermesMcpGatewayStatusResponse(
            agent_profile=agent_profile,
            enabled=True,
            status=_gateway_status_from_error(exc),
            endpoint=endpoint,
            skills_count=0,
            tools_count=0,
            warnings=[getattr(exc, "message", str(exc))],
        )


def _find_skill_by_slug(skills: list, skill_slug: str):
    for skill in skills:
        if instance_skill_service.skill_name_to_slug(skill.name) == skill_slug:
            return skill
        if skill.name.strip().lower() == skill_slug.replace("-", "_"):
            return skill
        if skill.name.strip().lower() == skill_slug:
            return skill
    return None


def _skill_matches_agent_profile(agent_profile: str, agent_slug: str) -> bool:
    return instance_skill_service.agent_profile_to_slug(agent_profile) == agent_slug


def _build_tool_descriptor(agent_profile: str, skill) -> dict[str, Any]:
    tool_name = instance_skill_service.build_tool_name(agent_profile, skill.name)
    return {
        "name": tool_name,
        "description": skill.description or f"Hermes skill {skill.name}",
        "inputSchema": _TOOL_INPUT_SCHEMA,
        "metadata": {
            "agent_profile": agent_profile,
            "skill_id": skill.name,
            "category": skill.category,
            "source": "api_server_default",
        },
    }


async def list_mcp_tools_for_user(
    db: AsyncSession,
    org_id: str,
    user_id: str,
    agent_profile: str,
    *,
    force_refresh: bool = False,
) -> list[HermesMcpToolItem]:
    skill_list = await instance_skill_service.list_instance_skills(
        db,
        org_id,
        agent_profile,
        force_refresh=force_refresh,
    )
    authz = HermesSkillAuthorizationService(db)
    binding = HermesDockerBindingService(db)
    record = await binding.get_by_profile(org_id, agent_profile)
    agent_id = record.id if record else None

    items: list[HermesMcpToolItem] = []
    for skill in skill_list.skills:
        can_list = await authz.can_list(org_id, user_id, "", skill.name, agent_id=agent_id)
        can_invoke = await authz.can_invoke(org_id, user_id, "", skill.name, agent_id=agent_id)
        if not can_list:
            continue
        items.append(
            HermesMcpToolItem(
                tool_name=instance_skill_service.build_tool_name(agent_profile, skill.name),
                skill_id=skill.name,
                category=skill.category,
                description=skill.description,
                can_list=can_list,
                can_invoke=can_invoke,
            )
        )
    return items


async def list_tools_jsonrpc(
    db: AsyncSession,
    org_id: str,
    user_id: str,
    agent_profile: str,
    *,
    params: dict | None = None,
    force_refresh: bool = False,
) -> dict[str, Any]:
    params = params or {}
    if params.get("profile"):
        raise BadRequestError(
            message="Hermes MCP Gateway 仅暴露实例级 default skills，不支持 profile 参数",
            message_key="errors.hermes.profile_not_supported",
        )

    skill_list = await instance_skill_service.list_instance_skills(
        db,
        org_id,
        agent_profile,
        force_refresh=force_refresh,
    )
    authz = HermesSkillAuthorizationService(db)
    binding = HermesDockerBindingService(db)
    record = await binding.get_by_profile(org_id, agent_profile)
    agent_id = record.id if record else None

    tools: list[dict[str, Any]] = []
    for skill in skill_list.skills:
        if not await authz.can_list(org_id, user_id, "", skill.name, agent_id=agent_id):
            continue
        tools.append(_build_tool_descriptor(agent_profile, skill))
    return {"tools": tools}


async def call_tool_jsonrpc(
    db: AsyncSession,
    org_id: str,
    user_id: str,
    agent_profile: str,
    *,
    params: dict | None = None,
) -> dict[str, Any]:
    params = params or {}
    if params.get("profile"):
        raise BadRequestError(
            message="Hermes MCP Gateway 仅暴露实例级 default skills，不支持 profile 参数",
            message_key="errors.hermes.profile_not_supported",
        )

    tool_name = str(params.get("name") or "").strip()
    arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
    parsed = instance_skill_service.parse_tool_name(tool_name)
    if not parsed:
        raise BadRequestError(
            message=f"无效的 MCP tool 名称: {tool_name}",
            message_key="errors.hermes.mcp_tool_name_invalid",
            message_params={"tool_name": tool_name},
        )

    agent_slug, skill_slug = parsed
    if not _skill_matches_agent_profile(agent_profile, agent_slug):
        raise BadRequestError(
            message=f"tool 名称与 agent_profile 不匹配: {tool_name}",
            message_key="errors.hermes.mcp_tool_name_invalid",
            message_params={"tool_name": tool_name},
        )

    skill_list = await instance_skill_service.list_instance_skills(db, org_id, agent_profile)
    skill = _find_skill_by_slug(skill_list.skills, skill_slug)
    if not skill:
        raise NotFoundError(
            message=f"Skill {skill_slug} 不存在于实例 default skills",
            message_key="errors.hermes.skill_not_found",
            message_params={"skill_id": skill_slug},
        )

    binding = HermesDockerBindingService(db)
    record = await binding.get_by_profile(org_id, agent_profile)
    if not record:
        raise NotFoundError(
            message="Hermes Agent 实例不存在",
            message_key="errors.hermes.agent_instance_not_found",
        )

    authz = HermesSkillAuthorizationService(db)
    if not await authz.can_invoke(org_id, user_id, "", skill.name, agent_id=record.id):
        raise ForbiddenError(
            message=f"无权调用 skill: {skill.name}",
            message_key="errors.hermes.skill_permission_denied",
        )

    prompt = str(arguments.get("prompt") or "").strip()
    if not prompt:
        raise BadRequestError(
            message="tools/call 缺少 prompt 参数",
            message_key="errors.hermes.mcp_tool_name_invalid",
        )

    env = parse_env_file(Path(record.env_file), require_gateway_port=False) if record.env_file else None
    model_name = (env.api_server_model_name if env else None) or agent_profile
    client = instance_skill_service.resolve_api_server_client(record.gateway_url, record.env_file)

    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "system",
                "content": (
                    f"You are a Hermes Agent. Use the requested skill when it is relevant. "
                    f"Requested skill: {skill.name}."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "metadata": {
            "requested_skill": skill.name,
            "source": "nodeskclaw_mcp_gateway",
        },
    }

    started = time.perf_counter()
    status = "success"
    error_code: str | None = None
    error_message: str | None = None
    content_text = ""
    try:
        result = await client.chat_completions(payload)
        if not result.ok:
            status = "error"
            error_code = result.error or "chat_completion_failed"
            error_message = f"POST /v1/chat/completions failed ({error_code})"
            raise AppException(
                code=50201,
                error_code=50201,
                message="Hermes chat/completions 调用失败",
                message_key="errors.hermes.chat_completion_failed",
                status_code=502,
                message_params={"detail": error_code or ""},
            )
        data = result.data if isinstance(result.data, dict) else {}
        choices = data.get("choices") if isinstance(data.get("choices"), list) else []
        if choices and isinstance(choices[0], dict):
            message = choices[0].get("message") if isinstance(choices[0].get("message"), dict) else {}
            content_text = str(message.get("content") or "")
        if not content_text:
            content_text = str(data)
    except Exception as exc:
        status = "error"
        if error_code is None:
            error_code = getattr(exc, "message_key", "chat_completion_failed")
            error_message = getattr(exc, "message", str(exc))
        duration_ms = int((time.perf_counter() - started) * 1000)
        await log_mcp_call(
            db,
            org_id=org_id,
            user_id=user_id,
            tool_name=tool_name,
            status=status,
            duration_ms=duration_ms,
            instance_id=record.instance_id,
            arguments=arguments,
            error_code=str(error_code) if error_code else None,
            error_message=error_message,
            client_name="hermes_agent_mcp_gateway",
            permission="can_invoke",
        )
        raise

    duration_ms = int((time.perf_counter() - started) * 1000)
    await log_mcp_call(
        db,
        org_id=org_id,
        user_id=user_id,
        tool_name=tool_name,
        status=status,
        duration_ms=duration_ms,
        instance_id=record.instance_id,
        arguments=arguments,
        client_name="hermes_agent_mcp_gateway",
        permission="can_invoke",
    )

    return {
        "content": [{"type": "text", "text": content_text}],
        "isError": False,
    }


async def dispatch_agent_mcp(
    db: AsyncSession,
    org_id: str,
    user_id: str,
    agent_profile: str,
    body: dict,
) -> dict:
    jsonrpc_id = body.get("id", 1)
    method = body.get("method", "")

    if body.get("jsonrpc") != "2.0":
        return mcp_error_v2(jsonrpc_id, "MCP_INVALID_ARGUMENTS", "jsonrpc must be '2.0'")

    if method == "initialize":
        return mcp_success(
            jsonrpc_id,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": f"hermes-mcp-{agent_profile}",
                    "version": settings.APP_VERSION,
                },
            },
        )

    if method == "ping":
        return mcp_success(jsonrpc_id, {})

    if method == "tools/list":
        try:
            params = body.get("params") if isinstance(body.get("params"), dict) else {}
            force_refresh = bool(params.get("force_refresh"))
            result = await list_tools_jsonrpc(
                db,
                org_id,
                user_id,
                agent_profile,
                params=params,
                force_refresh=force_refresh,
            )
            return mcp_success(jsonrpc_id, result)
        except (BadRequestError, ForbiddenError, NotFoundError, AppException) as exc:
            return map_app_error(jsonrpc_id, exc.message_key, exc.message)

    if method == "tools/call":
        try:
            params = body.get("params") if isinstance(body.get("params"), dict) else {}
            result = await call_tool_jsonrpc(
                db,
                org_id,
                user_id,
                agent_profile,
                params=params,
            )
            return mcp_success(jsonrpc_id, result)
        except ForbiddenError as exc:
            return mcp_error_v2(
                jsonrpc_id,
                MCP_SKILL_PERMISSION_DENIED,
                exc.message,
            )
        except (BadRequestError, NotFoundError, AppException) as exc:
            return map_app_error(jsonrpc_id, exc.message_key, exc.message)

    return mcp_error_v2(jsonrpc_id, "MCP_METHOD_NOT_FOUND", f"Method not found: {method}")
