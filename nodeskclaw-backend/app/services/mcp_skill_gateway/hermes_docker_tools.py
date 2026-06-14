"""Hermes external Docker MCP tools for MCP Skill Gateway."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.models.base import not_deleted
from app.models.user import User
from app.services.hermes_external import skill_service, status_service
from app.services.hermes_external._common import get_lifecycle_config, resolve_paths
from app.services.mcp_skill_gateway.errors import (
    HERMES_SKILLS_LIST_FAILED,
    MCP_TOOL_DISABLED,
    MCP_TOOL_NOT_FOUND,
)
from app.services.mcp_skill_gateway.hermes_instance_resolver import (
    list_external_docker_instances,
    require_instance_viewer_access,
    resolve_instance_ref,
)
from app.services.mcp_skill_gateway.mcp_tool_registry import (
    get_tool,
    is_hermes_registry_tool,
)

logger = logging.getLogger(__name__)


async def _load_user(user_id: str, db: AsyncSession) -> User:
    result = await db.execute(
        select(User).where(User.id == user_id, not_deleted(User))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise ForbiddenError("用户不存在", "errors.auth.user_not_found")
    return user


def list_tools() -> list[dict[str, Any]]:
    from app.services.mcp_skill_gateway.mcp_tool_registry import build_tool_descriptor, list_enabled_tools

    return [
        build_tool_descriptor(tool)
        for tool in list_enabled_tools()
        if tool.category == "hermes"
    ]


def is_hermes_docker_tool(tool_name: str) -> bool:
    return is_hermes_registry_tool(tool_name)


def extract_instance_id_from_arguments(arguments: dict[str, Any] | None) -> str | None:
    if not arguments:
        return None
    ref = arguments.get("instance_ref")
    return str(ref) if ref else None


def summarize_tool_result(tool_name: str, result: dict[str, Any]) -> dict[str, Any]:
    if tool_name == "hermes.instances.list":
        return {"instances_count": len(result.get("instances") or [])}
    if tool_name == "hermes.instance.status":
        return {"has_instance": bool(result.get("instance"))}
    if tool_name == "hermes.skills.list":
        return {"skills_count": len(result.get("skills") or [])}
    return {"keys": list(result.keys())}


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
        tool = get_tool(tool_name)
        if not tool:
            raise NotFoundError(
                f"MCP 工具不存在: {tool_name}",
                "errors.skill.tool_not_found",
            )

        if not tool.enabled:
            raise ForbiddenError(
                f"工具 {tool_name} 尚未开放",
                MCP_TOOL_DISABLED,
            )

        if tool.permission != "read":
            raise ForbiddenError(
                f"工具 {tool_name} 尚未开放",
                MCP_TOOL_DISABLED,
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
            MCP_TOOL_NOT_FOUND,
        )

    async def _instances_list(self, org_id: str, user: User) -> dict[str, Any]:
        instances = await list_external_docker_instances(org_id, self.db)
        summaries: list[dict[str, Any]] = []
        for instance in instances:
            try:
                await require_instance_viewer_access(instance, user, self.db)
            except ForbiddenError:
                continue

            status = await status_service.get_status(instance)
            paths = resolve_paths(instance)
            lifecycle = get_lifecycle_config(instance)
            summaries.append({
                "instance_id": instance.id,
                "profile": paths.profile,
                "container_name": paths.container_name,
                "binding_type": "external",
                "management_mode": lifecycle.get("lifecycle_mode") or "managed_container",
                "docker_status": status.docker_status,
                "docker_health": status.docker_health,
                "webui_health": status.webui_health,
                "webui_url": status.public_url,
            })
        return {"instances": summaries}

    async def _instance_status(
        self,
        arguments: dict[str, Any],
        org_id: str,
        user: User,
    ) -> dict[str, Any]:
        instance_ref = str(arguments.get("instance_ref") or "")
        instance = await resolve_instance_ref(instance_ref or None, org_id, user, self.db)

        status = await status_service.get_status(instance)
        if status.docker_status in ("missing", "unknown") and status.webui_health == "unhealthy":
            raise BadRequestError(
                "Hermes 实例运行时不可用",
                "errors.external_docker.runtime_unavailable",
            )

        paths = resolve_paths(instance)
        return {
            "instance": {
                "instance_id": instance.id,
                "profile": paths.profile,
                "container_name": paths.container_name,
                "docker_status": status.docker_status,
                "docker_health": status.docker_health,
                "webui_health": status.webui_health,
                "status": status.display_status,
                "webui_url": status.public_url,
                "image": status.image,
            }
        }

    async def _skills_list(
        self,
        arguments: dict[str, Any],
        org_id: str,
        user: User,
    ) -> dict[str, Any]:
        instance_ref = str(arguments.get("instance_ref") or "")
        instance = await resolve_instance_ref(instance_ref or None, org_id, user, self.db)

        try:
            response = skill_service.list_skills(instance)
        except Exception as exc:
            logger.warning("skills list failed instance=%s", instance.id, exc_info=True)
            raise BadRequestError(
                "读取 skills 列表失败",
                HERMES_SKILLS_LIST_FAILED,
            ) from exc

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
