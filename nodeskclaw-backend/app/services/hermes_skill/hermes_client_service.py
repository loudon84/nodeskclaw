import logging
from dataclasses import dataclass

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import not_deleted
from app.models.hermes_skill.skill import HermesSkill
from app.models.hermes_skill.skill_installation import HermesSkillInstallation
from app.services.hermes_skill.agent_alias_resolver import AgentAliasResolver
from app.services.hermes_skill.hermes_agent_runtime_service import HermesAgentRuntimeService
from app.services.hermes_skill.hermes_queue_policy_service import HermesQueuePolicyService
from app.services.hermes_skill.hermes_skill_authorization_service import HermesSkillAuthorizationService
from app.services.hermes_skill.mcp_tool_mapper import McpToolMapper
from app.services.hermes_skill.permission_checker import PermissionChecker
from app.services.hermes_skill.skill_audit_logger import SkillAuditLogger
from app.services.hermes_skill.skill_routing_service import SkillRoutingService
from app.services.mcp_skill_gateway.constants import (
    MCP_ENDPOINT,
    MCP_HEALTH_ENDPOINT,
    MCP_PROTOCOL_VERSION,
)

logger = logging.getLogger(__name__)

HEADER_DEVICE_ID = "X-NoDeskClaw-Desktop-Device-Id"
HEADER_HERMES_PROFILE = "X-NoDeskClaw-Hermes-Profile"
HEADER_CLIENT = "X-NoDeskClaw-Client"
HEADER_PROXY_VERSION = "X-NoDeskClaw-MCP-Proxy-Version"


@dataclass
class DesktopContext:
    device_id: str | None = None
    profile_name: str | None = None
    client: str | None = None
    proxy_version: str | None = None

    @property
    def is_present(self) -> bool:
        return bool(self.device_id or self.profile_name or self.client)


class HermesClientService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.alias_resolver = AgentAliasResolver(db)
        self.runtime_svc = HermesAgentRuntimeService(db)
        self.audit = SkillAuditLogger(db)

    def parse_desktop_headers(self, request: Request) -> DesktopContext:
        return DesktopContext(
            device_id=request.headers.get(HEADER_DEVICE_ID),
            profile_name=request.headers.get(HEADER_HERMES_PROFILE),
            client=request.headers.get(HEADER_CLIENT),
            proxy_version=request.headers.get(HEADER_PROXY_VERSION),
        )

    async def build_bootstrap(
        self,
        user,
        org,
        desktop_ctx: DesktopContext,
    ) -> dict:
        await self.audit.log(
            action="hermes.client.bootstrap.viewed",
            target_id=org.id,
            org_id=org.id,
            actor_id=user.id,
            details={
                "client": desktop_ctx.client,
                "desktop_device_id": desktop_ctx.device_id,
                "profile": desktop_ctx.profile_name,
            },
        )
        return {
            "user": {
                "id": user.id,
                "display_name": getattr(user, "display_name", None) or user.username,
            },
            "org": {
                "id": org.id,
                "name": org.name,
            },
            "desktop": {
                "device_id": desktop_ctx.device_id,
                "profile_name": desktop_ctx.profile_name,
                "client": desktop_ctx.client,
                "proxy_version": desktop_ctx.proxy_version,
            },
            "mcp": {
                "server_url": MCP_ENDPOINT,
                "health_url": MCP_HEALTH_ENDPOINT,
                "protocol_version": MCP_PROTOCOL_VERSION,
                "transport": "streamable_http",
                "requires_initialize": True,
            },
            "events": {
                "auth_mode": "bearer_or_sse_token",
                "sse_token_supported": True,
            },
            "artifacts": {
                "preview_url_template": "/api/v1/hermes/artifacts/{artifact_id}/preview",
                "download_url_template": "/api/v1/hermes/artifacts/{artifact_id}/download",
            },
            "features": {
                "agent_alias_routing": True,
                "client_tools_api": True,
                "task_result_api": True,
                "readiness_check": True,
                "ui_schema": True,
            },
        }

    async def list_client_agents(self, org_id: str, user_id: str) -> list[dict]:
        agents = await self.alias_resolver.list_available_agents(org_id)
        authz = HermesSkillAuthorizationService(self.db)
        filtered: list[dict] = []
        for agent in agents:
            if not await self._user_can_access_agent(org_id, user_id, agent.agent_id, authz):
                continue
            filtered.append(agent.to_dict())
        return filtered

    async def get_client_agent(self, org_id: str, user_id: str, alias: str) -> dict | None:
        resolution = await self.alias_resolver.resolve(org_id, alias)
        if resolution is None:
            await self.audit.log(
                action="hermes.skill.routing.alias_failed",
                target_id=alias,
                org_id=org_id,
                actor_id=user_id,
                details={"agent_alias": alias},
            )
            return None
        authz = HermesSkillAuthorizationService(self.db)
        if not await self._user_can_access_agent(org_id, user_id, resolution.agent_id, authz):
            return None
        await self.audit.log(
            action="hermes.client.agent.resolved",
            target_id=resolution.agent_id,
            org_id=org_id,
            actor_id=user_id,
            details={"agent_alias": alias, "reason": resolution.reason},
        )
        return resolution.to_dict()

    async def list_client_tools(
        self,
        org_id: str,
        user_id: str,
        *,
        agent_alias: str | None = None,
        agent_id: str | None = None,
        profile: str | None = None,
        workspace_id: str | None = None,
        category: str | None = None,
        keyword: str | None = None,
    ) -> dict:
        if agent_alias and not agent_id:
            resolution = await self.alias_resolver.resolve(org_id, agent_alias)
            if resolution:
                agent_id = resolution.agent_id
                profile = profile or resolution.profile_id
                workspace_id = workspace_id or resolution.workspace_id

        mapper = McpToolMapper(self.db)
        tools = await mapper.list_tools(
            org_id,
            user_id=user_id,
            agent_id=agent_id,
            profile=profile,
            workspace_id=workspace_id,
            category=category,
            keyword=keyword,
        )
        await self.audit.log(
            action="hermes.client.tools.listed",
            target_id=org_id,
            org_id=org_id,
            actor_id=user_id,
            details={
                "agent_alias": agent_alias,
                "agent_id": agent_id,
                "profile": profile,
                "count": len(tools),
            },
        )
        return {"items": tools, "total": len(tools)}

    async def run_readiness_check(
        self,
        org_id: str,
        user_id: str,
        *,
        agent_alias: str | None = None,
        tool_name: str | None = None,
        profile: str | None = None,
        workspace_id: str | None = None,
        desktop_ctx: DesktopContext | None = None,
    ) -> dict:
        checks: dict[str, bool] = {
            "user_authenticated": bool(user_id),
            "org_member": True,
            "desktop_context": bool(desktop_ctx and desktop_ctx.is_present),
            "agent_exists": False,
            "agent_enabled": False,
            "agent_healthy": False,
            "profile_root_path_exists": False,
            "workspace_root_path_exists": False,
            "skill_exists": False,
            "skill_active": False,
            "skill_mcp_exposed": False,
            "installation_installed": False,
            "user_can_list": False,
            "user_can_invoke": False,
            "queue_accepting": False,
        }
        errors: list[dict] = []
        routing: dict | None = None
        tool_info: dict | None = None

        resolution = None
        if agent_alias:
            resolution = await self.alias_resolver.resolve(org_id, agent_alias)
            if resolution:
                checks["agent_exists"] = True
                routing = {
                    "agent_alias": resolution.agent_alias,
                    "agent_id": resolution.agent_id,
                    "profile_id": resolution.profile_id,
                    "workspace_id": resolution.workspace_id,
                    "reason": resolution.reason,
                }
                checks["agent_enabled"] = resolution.runtime_status in ("enabled", "maintenance")
                checks["agent_healthy"] = resolution.health in ("ok", "degraded")
                runtime = await self.runtime_svc.get_runtime_state(org_id, resolution.agent_id)
                checks["profile_root_path_exists"] = bool(runtime.get("profile_root_path_exists"))
                checks["workspace_root_path_exists"] = bool(runtime.get("workspace_root_path_exists"))
            else:
                errors.append({"code": "agent_not_found", "message": f"Agent alias {agent_alias} 未找到"})

        if tool_name:
            skill_result = await self.db.execute(
                select(HermesSkill).where(
                    not_deleted(HermesSkill),
                    HermesSkill.org_id == org_id,
                    HermesSkill.tool_name == tool_name,
                ).limit(1)
            )
            skill = skill_result.scalar_one_or_none()
            if skill:
                checks["skill_exists"] = True
                checks["skill_active"] = skill.is_active
                checks["skill_mcp_exposed"] = skill.is_mcp_exposed
                authz = HermesSkillAuthorizationService(self.db)
                checks["user_can_list"] = await authz.can_list(org_id, user_id, skill.id, skill.skill_id)
                checks["user_can_invoke"] = await authz.can_invoke(org_id, user_id, skill.id, skill.skill_id)
                extra = skill.extra_metadata or {}
                tool_info = {
                    "name": skill.tool_name,
                    "title": skill.title or skill.name,
                    "inputSchema": skill.input_schema or {},
                    "uiSchema": extra.get("ui_schema") or {},
                }

                inst_conditions = [
                    not_deleted(HermesSkillInstallation),
                    HermesSkillInstallation.org_id == org_id,
                    HermesSkillInstallation.skill_id == skill.skill_id,
                    HermesSkillInstallation.status == "installed",
                ]
                if resolution:
                    inst_conditions.append(HermesSkillInstallation.agent_id == resolution.agent_id)
                if profile:
                    inst_conditions.append(HermesSkillInstallation.profile_id == profile)
                if workspace_id:
                    inst_conditions.append(HermesSkillInstallation.workspace_id == workspace_id)
                inst_result = await self.db.execute(
                    select(HermesSkillInstallation).where(*inst_conditions).limit(1)
                )
                installation = inst_result.scalar_one_or_none()
                if installation:
                    checks["installation_installed"] = True
                    if routing is None:
                        routing = {
                            "agent_alias": agent_alias,
                            "agent_id": installation.agent_id,
                            "profile_id": installation.profile_id,
                            "workspace_id": installation.workspace_id,
                            "installation_id": installation.id,
                            "reason": "matched_by_installation",
                        }
                    elif routing:
                        routing["installation_id"] = installation.id

                queue_policy = HermesQueuePolicyService(self.db)
                can_enqueue, _ = await queue_policy.can_enqueue(
                    org_id, user_id,
                    resolution.agent_id if resolution else (installation.agent_id if installation else None),
                    skill.skill_id,
                )
                checks["queue_accepting"] = can_enqueue
            else:
                errors.append({"code": "skill_not_found", "message": f"Tool {tool_name} 未找到"})

        ready = all(checks.values())
        await self.audit.log(
            action="hermes.client.readiness_checked",
            target_id=agent_alias or tool_name or org_id,
            org_id=org_id,
            actor_id=user_id,
            details={"ready": ready, "checks": checks},
        )
        return {
            "ready": ready,
            "checks": checks,
            "routing": routing,
            "tool": tool_info,
            "errors": errors,
        }

    async def _user_can_access_agent(
        self,
        org_id: str,
        user_id: str,
        agent_id: str,
        authz: HermesSkillAuthorizationService,
    ) -> bool:
        role = await PermissionChecker.get_user_role(self.db, user_id, org_id)
        if role in PermissionChecker.ADMIN_OPERATOR_ROLES:
            return True
        inst_subq = (
            select(HermesSkillInstallation.skill_id)
            .where(
                not_deleted(HermesSkillInstallation),
                HermesSkillInstallation.org_id == org_id,
                HermesSkillInstallation.agent_id == agent_id,
                HermesSkillInstallation.status == "installed",
            )
        )
        skill_result = await self.db.execute(
            select(HermesSkill).where(
                not_deleted(HermesSkill),
                HermesSkill.org_id == org_id,
                HermesSkill.skill_id.in_(inst_subq),
                HermesSkill.is_mcp_exposed.is_(True),
            )
        )
        skills = list(skill_result.scalars().all())
        if not skills:
            return False
        for skill in skills:
            if await authz.can_invoke(org_id, user_id, skill.id, skill.skill_id):
                return True
            if await authz.can_list(org_id, user_id, skill.id, skill.skill_id):
                return True
        return False
