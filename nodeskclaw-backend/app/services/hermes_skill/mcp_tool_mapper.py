import logging
from typing import Any

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, BadRequestError, ForbiddenError
from app.models.base import not_deleted
from app.models.hermes_skill.skill import HermesSkill
from app.models.hermes_skill.skill_installation import HermesSkillInstallation
from app.services.hermes_skill.agent_alias_resolver import AgentAliasResolver
from app.services.hermes_skill.hermes_skill_authorization_service import HermesSkillAuthorizationService
from app.services.hermes_skill.permission_checker import PermissionChecker
from app.services.hermes_skill.skill_routing_service import SkillRoutingService
from app.services.hermes_skill.task_service import TaskService
from app.services.mcp_skill_gateway.output_policy_service import OutputPolicyService

logger = logging.getLogger(__name__)


class McpToolMapper:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _has_explicit_runtime_route_override(raw_args: dict) -> bool:
        return (
            "_routing" in raw_args
            or "_execution" in raw_args
            or "route_config" in raw_args
        )

    async def list_tools(
        self,
        org_id: str,
        user_id: str = "",
        *,
        agent_id: str | None = None,
        agent_alias: str | None = None,
        profile: str | None = None,
        workspace_id: str | None = None,
        category: str | None = None,
        keyword: str | None = None,
    ) -> list[dict[str, Any]]:
        has_view = True
        has_invoke = True
        if user_id:
            has_view = await PermissionChecker.has_permission(self.db, user_id, org_id, "skill:view")
            has_invoke = await PermissionChecker.has_permission(self.db, user_id, org_id, "skill:invoke")
        if not has_view or not has_invoke:
            return []

        if agent_alias and not agent_id:
            resolution = await AgentAliasResolver(self.db).resolve(org_id, agent_alias)
            if resolution:
                agent_id = resolution.agent_id
                profile = profile or resolution.profile_id
                workspace_id = workspace_id or resolution.workspace_id

        installed_subq = (
            select(HermesSkillInstallation.skill_id)
            .where(
                not_deleted(HermesSkillInstallation),
                HermesSkillInstallation.org_id == org_id,
                HermesSkillInstallation.status == "installed",
            )
            .correlate(HermesSkill)
        )
        if agent_id:
            installed_subq = installed_subq.where(HermesSkillInstallation.agent_id == agent_id)
        if profile:
            installed_subq = installed_subq.where(HermesSkillInstallation.profile_id == profile)
        if workspace_id:
            installed_subq = installed_subq.where(HermesSkillInstallation.workspace_id == workspace_id)

        conditions = [
            not_deleted(HermesSkill),
            HermesSkill.org_id == org_id,
            HermesSkill.is_active.is_(True),
            HermesSkill.is_mcp_exposed.is_(True),
            HermesSkill.tool_name.isnot(None),
            HermesSkill.tool_name != "",
            exists(installed_subq.where(HermesSkillInstallation.skill_id == HermesSkill.skill_id)),
        ]
        if category:
            conditions.append(HermesSkill.category == category)
        if keyword:
            conditions.append(
                HermesSkill.tool_name.ilike(f"%{keyword}%")
                | HermesSkill.name.ilike(f"%{keyword}%")
                | HermesSkill.title.ilike(f"%{keyword}%")
            )

        result = await self.db.execute(select(HermesSkill).where(*conditions))
        skills = list(result.scalars().all())

        if user_id:
            role = await PermissionChecker.get_user_role(self.db, user_id, org_id)
            if role not in PermissionChecker.ADMIN_OPERATOR_ROLES:
                authz = HermesSkillAuthorizationService(self.db)
                skills = [
                    s for s in skills
                    if await authz.can_list(org_id, user_id, s.id, s.skill_id)
                ]

        alias_resolver = AgentAliasResolver(self.db)
        tools = []
        for skill in skills:
            tools.append(await self._skill_to_tool_dict(skill, org_id, agent_id, agent_alias, alias_resolver, user_id))
        return tools

    async def _skill_to_tool_dict(
        self,
        skill: HermesSkill,
        org_id: str,
        agent_id: str | None,
        agent_alias: str | None,
        alias_resolver: AgentAliasResolver,
        user_id: str,
    ) -> dict[str, Any]:
        extra = skill.extra_metadata or {}
        resolved_alias = agent_alias
        resolved_agent_id = agent_id
        profile_id = None
        workspace_id = None
        if not resolved_agent_id:
            inst_result = await self.db.execute(
                select(HermesSkillInstallation).where(
                    not_deleted(HermesSkillInstallation),
                    HermesSkillInstallation.org_id == org_id,
                    HermesSkillInstallation.skill_id == skill.skill_id,
                    HermesSkillInstallation.status == "installed",
                ).limit(1)
            )
            inst = inst_result.scalar_one_or_none()
            if inst:
                resolved_agent_id = inst.agent_id
                profile_id = inst.profile_id
                workspace_id = inst.workspace_id
        if resolved_agent_id and not resolved_alias:
            resolution = await alias_resolver.resolve(org_id, resolved_agent_id)
            if resolution:
                resolved_alias = resolution.agent_alias
                profile_id = profile_id or resolution.profile_id
                workspace_id = workspace_id or resolution.workspace_id

        authorized = True
        grant_status = "active"
        if user_id:
            authz = HermesSkillAuthorizationService(self.db)
            authorized = await authz.can_invoke(org_id, user_id, skill.id, skill.skill_id)
            if not authorized:
                grant_status = "denied"

        tool: dict[str, Any] = {
            "name": skill.tool_name,
            "title": skill.title or skill.name,
            "description": skill.description or "",
            "inputSchema": skill.input_schema or {},
            "version": skill.version,
            "category": skill.category,
            "agentAlias": resolved_alias,
            "agentId": resolved_agent_id,
            "profileId": profile_id,
            "workspaceId": workspace_id,
            "approvalMode": "server",
            "requiresApproval": False,
            "authorized": authorized,
            "grantStatus": grant_status,
        }
        if extra.get("ui_schema"):
            tool["uiSchema"] = extra["ui_schema"]
        if extra.get("examples"):
            tool["examples"] = extra["examples"]
        if extra.get("primary_artifact_policy"):
            tool["primaryArtifactPolicy"] = extra["primary_artifact_policy"]
        return tool

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict,
        org_id: str,
        user_id: str = "",
        jsonrpc_id: Any = None,
        *,
        client_context: dict | None = None,
        profile_name: str | None = None,
    ) -> dict[str, Any]:
        if user_id:
            await PermissionChecker.require_permission(self.db, user_id, org_id, "skill:view")
            await PermissionChecker.require_permission(self.db, user_id, org_id, "skill:invoke")

        raw_args = arguments or {}
        agent_arguments, explicit_routing = SkillRoutingService.extract_routing(raw_args)
        alias_resolver = AgentAliasResolver(self.db)
        routing_service = SkillRoutingService(self.db)
        routing: dict = {}

        skill = await routing_service.get_exposed_skill(tool_name, org_id)
        if not skill:
            from app.services.hermes_skill.skill_audit_logger import SkillAuditLogger
            audit_logger = SkillAuditLogger(self.db)
            await audit_logger.log(
                action="hermes.skill.routing.failed",
                target_id=tool_name,
                org_id=org_id,
                actor_id=user_id or "",
                details={"tool_name": tool_name, "error": "errors.skill.tool_not_found"},
            )
            raise NotFoundError(
                f"MCP Tool {tool_name} 不存在",
                "errors.skill.tool_not_found",
            )

        try:
            if skill.source_type == "hermes_api_server":
                if self._has_explicit_runtime_route_override(raw_args):
                    override_keys = [
                        key for key in ("_routing", "_execution", "route_config")
                        if key in raw_args
                    ]
                    logger.warning(
                        "MCP runtime skill route override denied tool=%s user=%s keys=%s",
                        tool_name,
                        user_id or "",
                        override_keys,
                    )
                    raise BadRequestError(
                        "组织级 MCP 不允许覆盖 Hermes 实例路由",
                        "errors.skill.route_override_not_allowed",
                    )

                routing_result = await routing_service.resolve_runtime_skill_fixed_route(
                    tool_name=tool_name,
                    org_id=org_id,
                )
                routing = {}
                logger.debug(
                    "MCP runtime skill fixed route selected tool=%s installation=%s profile_from_token_ignored=%s",
                    tool_name,
                    routing_result.installation.id if routing_result.installation else "",
                    bool(profile_name),
                )
            else:
                routing = await alias_resolver.enrich_routing(
                    org_id,
                    explicit_routing,
                    profile_name=profile_name,
                )
                routing_result = await routing_service.resolve_by_tool_name(
                    tool_name=tool_name,
                    org_id=org_id,
                    routing=routing,
                )

            installation = routing_result.installation
            if not installation:
                raise NotFoundError(
                    f"Skill {tool_name} 未安装到任何 Agent",
                    "errors.skill.installation_not_found",
                )
        except (NotFoundError, BadRequestError) as exc:
            from app.services.hermes_skill.skill_audit_logger import SkillAuditLogger
            audit_logger = SkillAuditLogger(self.db)
            await audit_logger.log(
                action="hermes.skill.routing.failed",
                target_id=tool_name,
                org_id=org_id,
                actor_id=user_id or "",
                details={"tool_name": tool_name, "error": exc.message_key},
            )
            if routing.get("agent_alias"):
                await audit_logger.log(
                    action="hermes.skill.routing.alias_failed",
                    target_id=str(routing.get("agent_alias")),
                    org_id=org_id,
                    actor_id=user_id or "",
                    details={"tool_name": tool_name, "agent_alias": routing.get("agent_alias")},
                )
            raise

        if user_id:
            authz_service = HermesSkillAuthorizationService(self.db)
            if not await authz_service.can_invoke(org_id, user_id, skill.id, skill.skill_id):
                from app.core import hooks
                await hooks.emit(
                    "operation_audit",
                    action="mcp.skill_call_denied",
                    target_type="hermes_skill",
                    target_id=skill.id,
                    actor_id=user_id,
                    org_id=org_id,
                    details={"skill_id": skill.skill_id, "tool_name": tool_name},
                )
                raise ForbiddenError(
                    "无权调用该 Skill",
                    "errors.skill.permission_denied",
                )

        if skill.input_schema:
            try:
                import jsonschema
                jsonschema.validate(instance=agent_arguments, schema=skill.input_schema)
            except ImportError:
                pass
            except jsonschema.ValidationError as exc:
                raise BadRequestError(
                    f"arguments 不符合 input_schema: {exc.message}",
                    "errors.skill.input_schema_validation_failed",
                )

        agent_alias = routing.get("agent_alias")
        if not agent_alias:
            resolution = await alias_resolver.resolve(org_id, installation.agent_id)
            if resolution:
                agent_alias = resolution.agent_alias

        routing_metadata = {
            "agent_alias": agent_alias,
            "agent_id": installation.agent_id,
            "profile_id": installation.profile_id,
            "workspace_id": installation.workspace_id,
            "installation_id": installation.id,
            "routing_reason": routing_result.reason,
        }
        output_policy = OutputPolicyService.resolve(
            skill=skill,
            installation=installation,
            tool_name=tool_name,
        )
        routing_metadata["output_policy"] = output_policy
        if installation.routing_metadata:
            routing_metadata["route_snapshot"] = dict(installation.routing_metadata)
            if skill.source_type == "hermes_api_server":
                routing_metadata["task_source"] = "org_mcp"

        task = await TaskService(self.db).create_task(
            org_id=org_id,
            skill_id=skill.skill_id,
            tool_name=tool_name,
            agent_id=installation.agent_id,
            profile_id=installation.profile_id,
            workspace_id=installation.workspace_id,
            installation_id=installation.id,
            user_id=user_id or None,
            arguments=agent_arguments,
            client_context=client_context,
            routing_metadata=routing_metadata,
        )

        from app.services.hermes_skill.skill_audit_logger import SkillAuditLogger
        audit_logger = SkillAuditLogger(self.db)
        await audit_logger.log(
            action="hermes.skill.routing.resolved",
            target_id=task.id,
            org_id=org_id,
            actor_id=user_id or "",
            details={
                "task_id": task.id,
                "installation_id": installation.id,
                "routing_reason": routing_result.reason,
                "agent_id": installation.agent_id,
                "profile_id": installation.profile_id,
                "workspace_id": installation.workspace_id,
            },
        )
        if agent_alias:
            await audit_logger.log(
                action="hermes.skill.routing.alias_resolved",
                target_id=task.id,
                org_id=org_id,
                actor_id=user_id or "",
                details={"agent_alias": agent_alias, "agent_id": installation.agent_id},
            )
        await audit_logger.log(
            action="hermes.skill.invoked",
            target_id=task.id,
            org_id=org_id,
            actor_id=user_id or "",
            details={
                "task_id": task.id,
                "task_no": task.task_no,
                "skill_id": skill.skill_id,
                "tool_name": tool_name,
                "agent_id": installation.agent_id,
            },
        )

        return {
            "tool_name": tool_name,
            "agent_alias": agent_alias,
            "agent_id": installation.agent_id,
            "profile_id": installation.profile_id,
            "workspace_id": installation.workspace_id,
            "status": task.status.value,
            "task_id": task.id,
            "task_no": task.task_no,
            "event_url": task.event_url,
            "event_token_url": f"/api/v1/hermes/tasks/{task.id}/events-token",
            "artifact_url": task.artifact_url,
            "result_url": f"/api/v1/hermes/tasks/{task.id}/result",
            "artifact_mode": output_policy.get("artifact_mode", "pull_only"),
            "server_artifacts": [],
            "routing_reason": routing_result.reason,
            "installation_id": installation.id,
        }
