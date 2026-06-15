"""GeneHub MCP tools for MCP Skill Gateway."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.base import not_deleted
from app.models.user import User
from app.services import genehub_service
from app.services.mcp_skill_gateway.errors import MCP_INVALID_ARGUMENTS, MCP_TOOL_NOT_FOUND
from app.services.mcp_skill_gateway.genehub_profile_resolver import resolve_desktop_profile
from app.services.mcp_skill_gateway.mcp_tool_registry import (
    get_tool,
    is_genehub_registry_tool,
)


async def _load_user(user_id: str, db: AsyncSession) -> User:
    from app.core.exceptions import ForbiddenError

    result = await db.execute(
        select(User).where(User.id == user_id, not_deleted(User))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise ForbiddenError("用户不存在", "errors.auth.user_not_found")
    return user


def is_genehub_tool(tool_name: str) -> bool:
    return is_genehub_registry_tool(tool_name)


def summarize_genehub_result(tool_name: str, result: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    if tool_name == "genehub.skills.search":
        summary["skills_count"] = len(result.get("skills") or [])
        return summary
    if tool_name == "genehub.skill.detail":
        skill = result.get("skill") or {}
        if skill.get("gene_slug"):
            summary["gene_slug"] = skill["gene_slug"]
        return summary
    if tool_name == "genehub.skill.register_to_hermes":
        if result.get("gene_slug"):
            summary["gene_slug"] = result["gene_slug"]
        if result.get("job_id"):
            summary["job_id"] = result["job_id"]
        if result.get("status"):
            summary["job_status"] = result["status"]
        if result.get("source"):
            summary["source"] = result["source"]
        if result.get("desktop_confirmation_required"):
            summary["desktop_confirmation_required"] = result["desktop_confirmation_required"]
        return summary
    if tool_name == "genehub.registration.status":
        registration = result.get("registration") or {}
        if registration.get("gene_slug"):
            summary["gene_slug"] = registration["gene_slug"]
        if registration.get("job_id"):
            summary["job_id"] = registration["job_id"]
        if registration.get("status"):
            summary["job_status"] = registration["status"]
        return summary
    return {"keys": list(result.keys())}


def extract_genehub_error_context(arguments: dict[str, Any]) -> dict[str, Any]:
    data: dict[str, Any] = {}
    if arguments.get("gene_slug"):
        data["gene_slug"] = arguments["gene_slug"]
    if arguments.get("profile_id"):
        data["profile_id"] = arguments["profile_id"]
    if arguments.get("job_id"):
        data["job_id"] = arguments["job_id"]
    return data


class GeneHubMcpToolProvider:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        org_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        tool = get_tool(tool_name)
        if not tool or not tool.enabled or tool.category != "genehub":
            raise NotFoundError(
                f"MCP 工具不存在: {tool_name}",
                "errors.skill.tool_not_found",
            )

        user = await _load_user(user_id, self.db)

        if tool_name == "genehub.skills.search":
            return await self._skills_search(arguments, org_id, user)
        if tool_name == "genehub.skill.detail":
            return await self._skill_detail(arguments, org_id, user)
        if tool_name == "genehub.skill.register_to_hermes":
            return await self._register_to_hermes(arguments, org_id, user)
        if tool_name == "genehub.registration.status":
            return await self._registration_status(arguments, org_id, user)

        raise NotFoundError(
            f"MCP 工具不存在: {tool_name}",
            MCP_TOOL_NOT_FOUND,
        )

    async def _skills_search(
        self,
        arguments: dict[str, Any],
        org_id: str,
        user: User,
    ) -> dict[str, Any]:
        profile = await resolve_desktop_profile(
            arguments.get("profile_id"), org_id, user, self.db
        )
        skills = await genehub_service.search_mcp_genehub_skills(
            self.db,
            org_id=org_id,
            user_id=user.id,
            profile_id=profile.id,
            query=arguments.get("query"),
            category=arguments.get("category"),
            tag=arguments.get("tag"),
        )
        return {"skills": [skill.model_dump() for skill in skills]}

    async def _skill_detail(
        self,
        arguments: dict[str, Any],
        org_id: str,
        user: User,
    ) -> dict[str, Any]:
        gene_slug = str(arguments.get("gene_slug") or "").strip()
        if not gene_slug:
            raise BadRequestError(
                "gene_slug 必填",
                MCP_INVALID_ARGUMENTS,
            )
        profile = await resolve_desktop_profile(
            arguments.get("profile_id"), org_id, user, self.db
        )
        detail = await genehub_service.get_desktop_skill_detail(
            self.db,
            org_id=org_id,
            user_id=user.id,
            profile_id=profile.id,
            gene_slug=gene_slug,
        )
        return {"skill": detail.model_dump()}

    async def _register_to_hermes(
        self,
        arguments: dict[str, Any],
        org_id: str,
        user: User,
    ) -> dict[str, Any]:
        gene_slug = str(arguments.get("gene_slug") or "").strip()
        if not gene_slug:
            raise BadRequestError(
                "gene_slug 必填",
                MCP_INVALID_ARGUMENTS,
            )
        profile = await resolve_desktop_profile(
            arguments.get("profile_id"), org_id, user, self.db
        )
        action = str(arguments.get("action") or "install")
        version = str(arguments.get("version") or "latest")
        result = await genehub_service.create_mcp_registration_job(
            self.db,
            org_id=org_id,
            user_id=user.id,
            profile_id=profile.id,
            gene_slug=gene_slug,
            version=version,
            action=action,
        )
        return result.model_dump()

    async def _registration_status(
        self,
        arguments: dict[str, Any],
        org_id: str,
        user: User,
    ) -> dict[str, Any]:
        job_id = arguments.get("job_id")
        gene_slug = arguments.get("gene_slug")
        profile_ref = arguments.get("profile_id")
        if not job_id and not (gene_slug and profile_ref):
            raise BadRequestError(
                "job_id 或 gene_slug+profile_id 必填其一",
                MCP_INVALID_ARGUMENTS,
            )
        profile_id = None
        if profile_ref:
            profile = await resolve_desktop_profile(profile_ref, org_id, user, self.db)
            profile_id = profile.id
        registration = await genehub_service.get_registration_status(
            self.db,
            org_id=org_id,
            user_id=user.id,
            job_id=str(job_id) if job_id else None,
            profile_id=profile_id,
            gene_slug=str(gene_slug) if gene_slug else None,
        )
        return {"registration": registration.model_dump()}
