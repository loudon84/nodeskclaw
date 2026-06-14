"""Hermes external Docker MCP tools for MCP Skill Gateway."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.models.base import not_deleted
from app.models.instance import Instance
from app.models.instance_member import InstanceRole
from app.models.user import User
from app.services.hermes_external import skill_service, status_service
from app.services.hermes_external._common import load_advanced_config, resolve_paths
from app.services.hermes_external.binding_type import get_instance_binding_type
from app.services import instance_member_service
from app.services.mcp_skill_gateway.errors import MCP_FORBIDDEN, MCP_NOT_IMPLEMENTED

logger = logging.getLogger(__name__)

PermissionLevel = str

TOOL_PERMISSION_LEVEL: dict[str, PermissionLevel] = {
    "hermes.instances.list": "read",
    "hermes.instance.status": "read",
    "hermes.skills.list": "read",
    "hermes.skills.install_builtin": "write",
    "hermes.skills.install_zip": "write",
    "hermes.skills.install_git": "write",
    "hermes.skills.uninstall": "write",
    "hermes.instance.restart": "admin",
    "hermes.instance.rebind": "admin",
}

READ_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "hermes.instances.list",
        "description": "List bound Hermes Docker instances",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "hermes.instance.status",
        "description": "Get runtime status of a bound Hermes instance",
        "inputSchema": {
            "type": "object",
            "properties": {"instance_ref": {"type": "string"}},
            "required": ["instance_ref"],
        },
    },
    {
        "name": "hermes.skills.list",
        "description": "List installed skills of a bound Hermes instance",
        "inputSchema": {
            "type": "object",
            "properties": {"instance_ref": {"type": "string"}},
            "required": ["instance_ref"],
        },
    },
]

GENEHUB_TOOL_DEFINITIONS_PHASE3: list[dict[str, Any]] = [
    {
        "name": "genehub.skills.search",
        "description": "Search GeneHub skills (Phase 3)",
        "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}},
    },
    {
        "name": "genehub.skill.detail",
        "description": "Get GeneHub skill detail (Phase 3)",
        "inputSchema": {
            "type": "object",
            "properties": {"gene_slug": {"type": "string"}},
            "required": ["gene_slug"],
        },
    },
    {
        "name": "genehub.skill.register_to_hermes",
        "description": "Create GeneHub skill registration job (Phase 3)",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "genehub.registration.status",
        "description": "Get GeneHub registration job status (Phase 3)",
        "inputSchema": {
            "type": "object",
            "properties": {"registration_id": {"type": "string"}},
            "required": ["registration_id"],
        },
    },
]


def list_tools() -> list[dict[str, Any]]:
    return [dict(tool) for tool in READ_TOOL_DEFINITIONS]


def is_hermes_docker_tool(tool_name: str) -> bool:
    return tool_name.startswith("hermes.") and tool_name in TOOL_PERMISSION_LEVEL


def is_genehub_tool(tool_name: str) -> bool:
    return tool_name.startswith("genehub.")


def _instance_profile(instance: Instance) -> str:
    advanced = load_advanced_config(instance)
    return str(advanced.get("profile") or instance.slug or instance.name)


def _instance_container_name(instance: Instance) -> str:
    advanced = load_advanced_config(instance)
    profile = _instance_profile(instance)
    return str(advanced.get("external_container_name") or f"hermes-{profile}")


def _instance_aliases(instance: Instance) -> set[str]:
    advanced = load_advanced_config(instance)
    aliases = advanced.get("aliases") or []
    result = {instance.slug, instance.name, _instance_profile(instance)}
    if isinstance(aliases, list):
        result.update(str(a) for a in aliases if a)
    return {a for a in result if a}


async def _load_user(user_id: str, db: AsyncSession) -> User:
    result = await db.execute(
        select(User).where(User.id == user_id, not_deleted(User))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise ForbiddenError("用户不存在", "errors.auth.user_not_found")
    return user


async def _list_external_docker_instances(org_id: str, db: AsyncSession) -> list[Instance]:
    result = await db.execute(
        select(Instance).where(
            Instance.org_id == org_id,
            not_deleted(Instance),
        )
    )
    instances = result.scalars().all()
    return [inst for inst in instances if get_instance_binding_type(inst) == "external_docker"]


async def resolve_instance_ref(
    ref: str,
    org_id: str,
    db: AsyncSession,
) -> Instance:
    value = (ref or "").strip()
    if not value:
        raise BadRequestError(
            "instance_ref 不能为空",
            "errors.external_docker.instance_ref_required",
        )

    instances = await _list_external_docker_instances(org_id, db)

    for instance in instances:
        if instance.id == value:
            return instance

    for instance in instances:
        if _instance_container_name(instance) == value:
            return instance

    for instance in instances:
        if _instance_profile(instance) == value:
            return instance

    for instance in instances:
        if value in _instance_aliases(instance):
            return instance

    raise NotFoundError(
        f"Hermes 实例不存在: {value}",
        "errors.external_docker.instance_not_found",
    )


async def _require_instance_viewer_access(
    instance: Instance,
    user: User,
    db: AsyncSession,
) -> None:
    await instance_member_service.check_instance_access(
        instance.id,
        user,
        InstanceRole.viewer,
        db,
    )


async def _build_instance_summary(instance: Instance, db: AsyncSession, user: User) -> dict[str, Any] | None:
    try:
        await _require_instance_viewer_access(instance, user, db)
    except (ForbiddenError, NotFoundError):
        return None

    status = await status_service.get_status(instance)
    paths = resolve_paths(instance)
    return {
        "instance_id": instance.id,
        "profile": paths.profile,
        "container_name": paths.container_name,
        "webui_url": status.public_url,
        "docker_status": status.docker_status,
        "docker_health": status.docker_health,
        "webui_health": status.webui_health,
        "binding_type": "external",
    }


class HermesDockerToolProvider:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_tools(self) -> list[dict[str, Any]]:
        return list_tools()

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        org_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        if is_genehub_tool(tool_name):
            raise BadRequestError(
                "GeneHub MCP 工具尚未开放",
                MCP_NOT_IMPLEMENTED,
            )

        level = TOOL_PERMISSION_LEVEL.get(tool_name)
        if not level:
            raise NotFoundError(
                f"MCP 工具不存在: {tool_name}",
                "errors.skill.tool_not_found",
            )

        if level != "read":
            raise ForbiddenError(
                f"工具 {tool_name} 尚未开放",
                MCP_FORBIDDEN,
            )

        user = await _load_user(user_id, self.db)

        if tool_name == "hermes.instances.list":
            return await self._instances_list(org_id, user)

        if tool_name == "hermes.instance.status":
            return await self._instance_status(arguments, org_id, user)

        if tool_name == "hermes.skills.list":
            return await self._skills_list(arguments, org_id, user)

        raise NotFoundError(
            f"MCP 工具不存在: {tool_name}",
            "errors.skill.tool_not_found",
        )

    async def _instances_list(self, org_id: str, user: User) -> dict[str, Any]:
        instances = await _list_external_docker_instances(org_id, self.db)
        summaries: list[dict[str, Any]] = []
        for instance in instances:
            summary = await _build_instance_summary(instance, self.db, user)
            if summary:
                summaries.append(summary)
        return {"instances": summaries}

    async def _instance_status(
        self,
        arguments: dict[str, Any],
        org_id: str,
        user: User,
    ) -> dict[str, Any]:
        instance_ref = str(arguments.get("instance_ref") or "")
        instance = await resolve_instance_ref(instance_ref, org_id, self.db)
        await _require_instance_viewer_access(instance, user, self.db)

        status = await status_service.get_status(instance)
        paths = resolve_paths(instance)
        return {
            "instance": {
                "instance_id": instance.id,
                "profile": paths.profile,
                "container_name": paths.container_name,
                "docker_status": status.docker_status,
                "docker_health": status.docker_health,
                "webui_health": status.webui_health,
                "webui_url": status.public_url,
            }
        }

    async def _skills_list(
        self,
        arguments: dict[str, Any],
        org_id: str,
        user: User,
    ) -> dict[str, Any]:
        instance_ref = str(arguments.get("instance_ref") or "")
        instance = await resolve_instance_ref(instance_ref, org_id, self.db)
        await _require_instance_viewer_access(instance, user, self.db)

        response = skill_service.list_skills(instance)
        skills = []
        for item in response.items:
            if item.category != "skills":
                continue
            skills.append({
                "slug": item.slug or item.name,
                "name": item.name,
                "version": item.version,
                "status": item.status or "installed",
                "source": item.source or "manual",
            })
        return {"skills": skills}


def extract_instance_id_from_arguments(arguments: dict[str, Any] | None) -> str | None:
    if not arguments:
        return None
    ref = arguments.get("instance_ref")
    return str(ref) if ref else None
