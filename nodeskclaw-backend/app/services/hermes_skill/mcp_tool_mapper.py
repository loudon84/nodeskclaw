import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import or_, select, exists
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, BadRequestError, ForbiddenError
from app.models.base import not_deleted
from app.models.hermes_skill.skill import HermesSkill
from app.models.hermes_skill.skill_installation import HermesSkillInstallation
from app.models.org_member_skill_grant import OrgMemberSkillGrant
from app.services.hermes_skill.permission_checker import PermissionChecker
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

        if user_id:
            now = datetime.now(timezone.utc)
            grant_subq = (
                select(OrgMemberSkillGrant.skill_db_id)
                .where(
                    not_deleted(OrgMemberSkillGrant),
                    OrgMemberSkillGrant.org_id == org_id,
                    OrgMemberSkillGrant.user_id == user_id,
                    OrgMemberSkillGrant.can_list.is_(True),
                    OrgMemberSkillGrant.can_invoke.is_(True),
                    or_(
                        OrgMemberSkillGrant.expires_at.is_(None),
                        OrgMemberSkillGrant.expires_at > now,
                    ),
                    OrgMemberSkillGrant.skill_db_id == HermesSkill.id,
                )
                .correlate(HermesSkill)
            )
            conditions.append(exists(grant_subq))

        result = await self.db.execute(select(HermesSkill).where(*conditions))
        tools = []
        for skill in result.scalars().all():
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

        result = await self.db.execute(
            select(HermesSkill).where(
                not_deleted(HermesSkill),
                HermesSkill.org_id == org_id,
                HermesSkill.tool_name == tool_name,
                HermesSkill.is_mcp_exposed.is_(True),
                HermesSkill.is_active.is_(True),
            )
        )
        skill = result.scalar_one_or_none()
        if not skill:
            raise NotFoundError(f"MCP Tool {tool_name} 不存在", "errors.skill.tool_not_found")

        install_result = await self.db.execute(
            select(HermesSkillInstallation).where(
                not_deleted(HermesSkillInstallation),
                HermesSkillInstallation.skill_id == skill.skill_id,
                HermesSkillInstallation.org_id == org_id,
                HermesSkillInstallation.status == "installed",
            )
        )
        installation = install_result.scalar_one_or_none()
        if not installation:
            raise NotFoundError(
                f"Skill {tool_name} 未安装到任何 Agent",
                "errors.skill.tool_not_installed",
            )

        if user_id:
            from app.services.member_skill_service import require_invoke_skill
            try:
                await require_invoke_skill(self.db, org_id, user_id, skill.id)
            except ForbiddenError:
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
                raise

        if skill.input_schema:
            try:
                import jsonschema
                jsonschema.validate(instance=arguments, schema=skill.input_schema)
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
            arguments=arguments,
        )

        from app.services.hermes_skill.skill_audit_logger import SkillAuditLogger
        audit_logger = SkillAuditLogger(self.db)
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
        }
