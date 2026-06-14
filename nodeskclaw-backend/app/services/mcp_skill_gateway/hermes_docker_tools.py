"""Hermes external Docker MCP tools for MCP Skill Gateway."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.models.base import not_deleted
from app.models.user import User
from app.services.hermes_external import lifecycle_service, skill_service, status_service
from app.services.hermes_external._common import get_lifecycle_config, resolve_paths
from app.services.hermes_expert.expert_filesystem import RESOURCES_ROOT
from app.services.mcp_skill_gateway.approval_service import get_protected_skills
from app.services.mcp_skill_gateway.errors import (
    HERMES_SKILLS_LIST_FAILED,
    MCP_INVALID_ARGUMENTS,
    MCP_TOOL_CONSTRAINT_VIOLATION,
    MCP_TOOL_DISABLED,
    MCP_TOOL_NOT_FOUND,
    MCP_TOOL_PROTECTED_RESOURCE,
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
        *,
        grant_constraints: dict | None = None,
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

        user = await _load_user(user_id, self.db)

        if tool_name == "hermes.instances.list":
            return await self._instances_list(org_id, user)

        if tool_name == "hermes.instance.status":
            return await self._instance_status(arguments, org_id, user)

        if tool_name == "hermes.skills.list":
            return await self._skills_list(arguments, org_id, user)

        if tool_name == "hermes.skills.install_builtin":
            return await self._skills_install_builtin(arguments, org_id, user)

        if tool_name == "hermes.skills.uninstall":
            return await self._skills_uninstall(arguments, org_id, user, grant_constraints)

        if tool_name == "hermes.instance.restart":
            return await self._instance_restart(arguments, org_id, user)

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

    def _list_builtin_bundle_whitelist(self) -> set[str]:
        bundles_root = RESOURCES_ROOT / "skill-bundles"
        if not bundles_root.is_dir():
            return set()
        return {item.name for item in bundles_root.iterdir() if item.is_dir()}

    async def _skills_install_builtin(
        self,
        arguments: dict[str, Any],
        org_id: str,
        user: User,
    ) -> dict[str, Any]:
        instance_ref = str(arguments.get("instance_ref") or "")
        skill_slug = str(arguments.get("skill_slug") or "").strip()
        if not skill_slug:
            raise BadRequestError("skill_slug 不能为空", MCP_INVALID_ARGUMENTS)

        instance = await resolve_instance_ref(instance_ref or None, org_id, user, self.db)
        allowed = self._list_builtin_bundle_whitelist()
        if skill_slug not in allowed:
            raise BadRequestError(
                f"内置技能包不在白名单: {skill_slug}",
                MCP_TOOL_CONSTRAINT_VIOLATION,
            )

        response = skill_service.install_builtin_bundle(instance, skill_slug)
        return {
            "installed": True,
            "skill_slug": skill_slug,
            "instance_id": instance.id,
            "requires_restart": response.requires_restart,
        }

    async def _skills_uninstall(
        self,
        arguments: dict[str, Any],
        org_id: str,
        user: User,
        grant_constraints: dict | None,
    ) -> dict[str, Any]:
        instance_ref = str(arguments.get("instance_ref") or "")
        skill_name = str(arguments.get("skill_name") or "").strip()
        if not skill_name:
            raise BadRequestError("skill_name 不能为空", MCP_INVALID_ARGUMENTS)

        instance = await resolve_instance_ref(instance_ref or None, org_id, user, self.db)
        protected = get_protected_skills(grant_constraints)
        if skill_name in protected:
            raise ForbiddenError(
                f"技能 {skill_name} 受保护，禁止卸载",
                MCP_TOOL_PROTECTED_RESOURCE,
            )

        existing = skill_service.list_skills(instance)
        skill_names = {item.slug or item.name for item in existing.items if item.category == "skills"}
        if skill_name not in skill_names:
            raise NotFoundError(
                f"技能不存在: {skill_name}",
                "errors.skill.tool_not_found",
            )

        skill_service.delete_skill(instance, skill_name)
        return {
            "uninstalled": True,
            "skill_name": skill_name,
            "instance_id": instance.id,
        }

    async def _instance_restart(
        self,
        arguments: dict[str, Any],
        org_id: str,
        user: User,
    ) -> dict[str, Any]:
        instance_ref = str(arguments.get("instance_ref") or "")
        instance = await resolve_instance_ref(instance_ref or None, org_id, user, self.db)

        lifecycle = get_lifecycle_config(instance)
        if lifecycle.get("lifecycle_mode") == "linked_only":
            raise BadRequestError(
                "当前实例为仅关联模式，不支持重启",
                "errors.docker_attach.lifecycle_not_allowed",
            )

        await lifecycle_service.restart(instance)
        status = await status_service.get_status(instance)
        return {
            "restarted": True,
            "instance_id": instance.id,
            "status": status.display_status or status.docker_status,
        }

