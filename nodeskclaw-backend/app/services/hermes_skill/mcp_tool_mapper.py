import logging
from typing import Any

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, BadRequestError, ForbiddenError
from app.models.base import not_deleted
from app.models.hermes_skill.skill import HermesSkill
from app.models.hermes_skill.skill_installation import HermesSkillInstallation
from app.services.hermes_skill.hermes_skill_authorization_service import HermesSkillAuthorizationService
from app.services.hermes_skill.permission_checker import PermissionChecker
from app.services.hermes_skill.skill_routing_service import SkillRoutingService
from app.services.hermes_skill.task_service import TaskService

logger = logging.getLogger(__name__)


class McpToolMapper:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_tools(self, org_id: str, user_id: str = "") -> list[dict[str, Any]]:
        has_view = True
        has_invoke = True
        if user_id:
            has_view = await PermissionChecker.has_permission(self.db, user_id, org_id, "skill:view")
            has_invoke = await PermissionChecker.has_permission(self.db, user_id, org_id, "skill:invoke")
        if not has_view or not has_invoke:
            return []

        installed_subq = (
            select(HermesSkillInstallation.skill_id)
            .where(
                not_deleted(HermesSkillInstallation),
                HermesSkillInstallation.org_id == org_id,
                HermesSkillInstallation.status == "installed",
            )
            .correlate(HermesSkill)
        )

        conditions = [
            not_deleted(HermesSkill),
            HermesSkill.org_id == org_id,
            HermesSkill.is_active.is_(True),
            HermesSkill.is_mcp_exposed.is_(True),
            HermesSkill.tool_name.isnot(None),
            HermesSkill.tool_name != "",
            exists(installed_subq.where(HermesSkillInstallation.skill_id == HermesSkill.skill_id)),
        ]

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

        tools = []
        for skill in skills:
            tools.append({
                "name": skill.tool_name,
                "title": skill.title or skill.name,
                "description": skill.description or "",
                "inputSchema": skill.input_schema or {},
                "version": skill.version,
            })
        return tools

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict,
        org_id: str,
        user_id: str = "",
        jsonrpc_id: Any = None,
    ) -> dict[str, Any]:
        if user_id:
            await PermissionChecker.require_permission(self.db, user_id, org_id, "skill:view")
            await PermissionChecker.require_permission(self.db, user_id, org_id, "skill:invoke")

        agent_arguments, routing = SkillRoutingService.extract_routing(arguments or {})

        routing_service = SkillRoutingService(self.db)
        try:
            routing_result = await routing_service.resolve_by_tool_name(
                tool_name=tool_name,
                org_id=org_id,
                routing=routing,
            )
            skill = routing_result.skill
            installation = routing_result.installation
            if not skill or not installation:
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
            "agent_id": installation.agent_id,
            "status": task.status.value,
            "task_id": task.id,
            "task_no": task.task_no,
            "event_url": task.event_url,
            "artifact_url": task.artifact_url,
            "routing_reason": routing_result.reason,
            "installation_id": installation.id,
        }
