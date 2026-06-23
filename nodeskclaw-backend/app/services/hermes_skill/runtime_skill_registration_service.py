import logging
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import hooks
from app.core.exceptions import (
    AppException,
    BadRequestError,
    ConflictError,
    NotFoundError,
)
from app.models.base import not_deleted
from app.models.hermes_skill.hermes_agent_instance import HermesAgentInstance
from app.models.hermes_skill.hermes_skill_authorization_grant import HermesSkillAuthorizationGrant
from app.models.hermes_skill.skill import HermesSkill
from app.models.hermes_skill.skill_installation import HermesSkillInstallation
from app.schemas.hermes_skill.runtime_skill_registration import (
    RuntimeSkillRegisterGrant,
    RuntimeSkillRegisterRequest,
    RuntimeSkillRegisterResponse,
)
from app.services.hermes_external import hermes_instance_skill_service as instance_skill_service
from app.services.hermes_external.hermes_docker_binding_service import HermesDockerBindingService
from app.services.hermes_external.hermes_env_parser import parse_env_file
from app.services.hermes_external.hermes_runtime_skill_executor import DEFAULT_INPUT_SCHEMA
from app.services.hermes_skill.hermes_skill_authorization_service import HermesSkillAuthorizationService

logger = logging.getLogger(__name__)


def _find_runtime_skill(skills: list, runtime_skill_id: str):
    target = runtime_skill_id.strip()
    target_slug = instance_skill_service.skill_name_to_slug(target)
    for skill in skills:
        if instance_skill_service.skill_name_to_slug(skill.name) == target_slug:
            return skill
        if skill.name.strip().lower() == target.replace("-", "_"):
            return skill
        if skill.name.strip().lower() == target.lower():
            return skill
    return None


class RuntimeSkillRegistrationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register_to_org_mcp(
        self,
        org_id: str,
        operator_user_id: str,
        agent_profile: str,
        runtime_skill_id: str,
        request: RuntimeSkillRegisterRequest,
    ) -> RuntimeSkillRegisterResponse:
        binding = HermesDockerBindingService(self.db)
        record = await binding.get_by_profile(org_id, agent_profile)
        if not record:
            raise NotFoundError(
                "Hermes Agent 实例不存在",
                "errors.hermes.agent_instance_not_found",
            )
        if not record.instance_id:
            raise BadRequestError(
                "注册失败：该 Hermes 实例未绑定运行实例，无法确定执行目标",
                "errors.skill.route_config_invalid",
            )

        try:
            skill_list = await instance_skill_service.list_instance_skills(
                self.db, org_id, agent_profile,
            )
        except AppException as exc:
            if exc.status_code in (409, 503):
                raise ConflictError(
                    f"Hermes 实例不可用：{exc.message}",
                    "errors.hermes.instance_unavailable",
                ) from exc
            raise

        runtime_skill = _find_runtime_skill(skill_list.skills, runtime_skill_id)
        if not runtime_skill:
            raise NotFoundError(
                f"当前 Hermes 实例未找到 runtime skill: {runtime_skill_id}",
                "errors.hermes.runtime_skill_not_found",
            )

        tool_name = (request.tool_name or "").strip() or instance_skill_service.build_tool_name(
            agent_profile, runtime_skill_id,
        )
        if not instance_skill_service.parse_tool_name(tool_name):
            raise BadRequestError(
                f"组织级 Tool Name 格式无效: {tool_name}",
                "errors.skill.tool_name_conflict",
                message_params={"tool_name": tool_name},
            )

        skill_id = tool_name
        existing_skill = await self._get_skill_by_skill_id(org_id, skill_id)
        if request.tool_name and existing_skill:
            meta = existing_skill.extra_metadata or {}
            if meta.get("runtime_skill_id") != runtime_skill_id or meta.get("agent_profile") != agent_profile:
                raise ConflictError(
                    f"组织级 Tool Name 已存在: {tool_name}",
                    "errors.skill.tool_name_conflict",
                    message_params={"tool_name": tool_name},
                )

        api_server_model_name = agent_profile
        if record.env_file:
            try:
                env = parse_env_file(Path(record.env_file), require_gateway_port=False)
                api_server_model_name = (env.api_server_model_name or agent_profile).strip() or agent_profile
            except Exception:
                logger.debug("Failed to read api_server_model_name for %s", agent_profile)

        route_config = {
            "route_type": "hermes_api_server",
            "force_instance": True,
            "hermes_instance_name": record.profile_name,
            "hermes_agent_instance_id": record.id,
            "agent_profile": agent_profile,
            "profile_id": request.profile_id,
            "workspace_id": request.workspace_id,
            "runtime_skill_id": runtime_skill.name,
            "api_server_model_name": api_server_model_name,
            "default_execution_mode": request.default_execution_mode,
            "timeout_seconds": request.timeout_seconds,
        }

        skill_created = existing_skill is None
        skill = await self._upsert_skill(
            org_id=org_id,
            skill_id=skill_id,
            tool_name=tool_name,
            runtime_skill=runtime_skill,
            agent_profile=agent_profile,
            profile_id=request.profile_id,
            runtime_skill_id=runtime_skill.name,
            record=record,
            is_mcp_exposed=request.is_mcp_exposed,
            operator_user_id=operator_user_id,
            existing=existing_skill,
        )

        installation_created, installation = await self._upsert_installation(
            org_id=org_id,
            skill_id=skill_id,
            instance_id=record.instance_id,
            profile_id=request.profile_id,
            workspace_id=request.workspace_id,
            route_config=route_config,
            operator_user_id=operator_user_id,
        )

        grant_spec = request.grant or RuntimeSkillRegisterGrant()
        subject_id = grant_spec.subject_id or org_id
        if grant_spec.subject_type == "org" and not grant_spec.subject_id:
            subject_id = org_id

        grant_created, _grant = await self._upsert_grant(
            org_id=org_id,
            skill_id=skill_id,
            skill_db_id=skill.id,
            workspace_id=request.workspace_id,
            grant_spec=grant_spec,
            subject_id=subject_id,
            operator_user_id=operator_user_id,
        )

        status = "created" if (skill_created or installation_created) else "updated"
        audit_action = (
            "hermes.runtime_skill.registered_to_org_mcp"
            if status == "created"
            else "hermes.runtime_skill.registration_updated"
        )
        await hooks.emit(
            "operation_audit",
            action=audit_action,
            target_type="hermes_skill",
            target_id=skill.id,
            actor_id=operator_user_id,
            org_id=org_id,
            details={
                "skill_id": skill_id,
                "tool_name": tool_name,
                "runtime_skill_id": runtime_skill.name,
                "hermes_instance_name": record.profile_name,
                "hermes_agent_instance_id": record.id,
                "installation_id": installation.id,
                "status": status,
            },
        )
        if grant_created:
            await hooks.emit(
                "operation_audit",
                action="hermes.runtime_skill.org_grant_created",
                target_type="hermes_skill_authorization",
                target_id=skill.id,
                actor_id=operator_user_id,
                org_id=org_id,
                details={
                    "skill_id": skill_id,
                    "subject_type": grant_spec.subject_type,
                    "subject_id": subject_id,
                },
            )

        await self.db.flush()

        return RuntimeSkillRegisterResponse(
            skill_db_id=skill.id,
            skill_id=skill_id,
            tool_name=tool_name,
            runtime_skill_id=runtime_skill.name,
            hermes_instance_name=record.profile_name,
            hermes_agent_instance_id=record.id,
            agent_profile=agent_profile,
            profile_id=request.profile_id,
            workspace_id=request.workspace_id,
            installation_id=installation.id,
            is_mcp_exposed=request.is_mcp_exposed,
            grant_created=grant_created,
            status=status,
        )

    async def _get_skill_by_skill_id(self, org_id: str, skill_id: str) -> HermesSkill | None:
        result = await self.db.execute(
            select(HermesSkill).where(
                not_deleted(HermesSkill),
                HermesSkill.org_id == org_id,
                HermesSkill.skill_id == skill_id,
            )
        )
        return result.scalar_one_or_none()

    async def _upsert_skill(
        self,
        *,
        org_id: str,
        skill_id: str,
        tool_name: str,
        runtime_skill,
        agent_profile: str,
        profile_id: str,
        runtime_skill_id: str,
        record: HermesAgentInstance,
        is_mcp_exposed: bool,
        operator_user_id: str,
        existing: HermesSkill | None,
    ) -> HermesSkill:
        category = (runtime_skill.category or "uncategorized").strip().lower() or "uncategorized"
        extra_metadata = {
            "registered_from": "runtime_skill",
            "hermes_instance_name": record.profile_name,
            "hermes_agent_instance_id": record.id,
            "agent_profile": agent_profile,
            "profile_id": profile_id,
            "runtime_skill_id": runtime_skill_id,
        }
        if existing:
            existing.tool_name = tool_name
            existing.name = runtime_skill_id
            existing.title = runtime_skill_id
            existing.description = runtime_skill.description
            existing.category = category
            existing.source_type = "hermes_api_server"
            existing.source_ref = f"hermes://{agent_profile}/{profile_id}/{runtime_skill_id}"
            existing.is_active = True
            existing.is_mcp_exposed = is_mcp_exposed
            existing.input_schema = DEFAULT_INPUT_SCHEMA
            existing.extra_metadata = {**(existing.extra_metadata or {}), **extra_metadata}
            await self.db.flush()
            return existing

        skill = HermesSkill(
            id=str(uuid.uuid4()),
            org_id=org_id,
            skill_id=skill_id,
            tool_name=tool_name,
            name=runtime_skill_id,
            title=runtime_skill_id,
            description=runtime_skill.description,
            category=category,
            source_type="hermes_api_server",
            source_ref=f"hermes://{agent_profile}/{profile_id}/{runtime_skill_id}",
            is_active=True,
            is_mcp_exposed=is_mcp_exposed,
            input_schema=DEFAULT_INPUT_SCHEMA,
            extra_metadata=extra_metadata,
            created_by=operator_user_id,
        )
        self.db.add(skill)
        await self.db.flush()
        return skill

    async def _upsert_installation(
        self,
        *,
        org_id: str,
        skill_id: str,
        instance_id: str,
        profile_id: str,
        workspace_id: str,
        route_config: dict,
        operator_user_id: str,
    ) -> tuple[bool, HermesSkillInstallation]:
        result = await self.db.execute(
            select(HermesSkillInstallation).where(
                not_deleted(HermesSkillInstallation),
                HermesSkillInstallation.org_id == org_id,
                HermesSkillInstallation.skill_id == skill_id,
                HermesSkillInstallation.agent_id == instance_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.profile_id = profile_id
            existing.workspace_id = workspace_id
            existing.status = "installed"
            existing.is_default = True
            existing.routing_metadata = route_config
            existing.installed_by = operator_user_id
            await self.db.flush()
            return False, existing

        installation = HermesSkillInstallation(
            id=str(uuid.uuid4()),
            org_id=org_id,
            skill_id=skill_id,
            agent_id=instance_id,
            profile_id=profile_id,
            workspace_id=workspace_id,
            status="installed",
            is_default=True,
            routing_metadata=route_config,
            installed_by=operator_user_id,
        )
        self.db.add(installation)
        await self.db.flush()
        return True, installation

    async def _upsert_grant(
        self,
        *,
        org_id: str,
        skill_id: str,
        skill_db_id: str,
        workspace_id: str,
        grant_spec: RuntimeSkillRegisterGrant,
        subject_id: str,
        operator_user_id: str,
    ) -> tuple[bool, HermesSkillAuthorizationGrant]:
        result = await self.db.execute(
            select(HermesSkillAuthorizationGrant).where(
                not_deleted(HermesSkillAuthorizationGrant),
                HermesSkillAuthorizationGrant.org_id == org_id,
                HermesSkillAuthorizationGrant.skill_id == skill_id,
                HermesSkillAuthorizationGrant.subject_type == grant_spec.subject_type,
                HermesSkillAuthorizationGrant.subject_id == subject_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.skill_db_id = skill_db_id
            existing.workspace_id = workspace_id
            existing.can_list = grant_spec.can_list
            existing.can_invoke = grant_spec.can_invoke
            existing.can_install = grant_spec.can_install
            existing.can_manage = grant_spec.can_manage
            existing.granted_by = operator_user_id
            await self.db.flush()
            return False, existing

        authz = HermesSkillAuthorizationService(self.db)
        grant = await authz.create_grant(
            org_id=org_id,
            skill_id=skill_id,
            subject_type=grant_spec.subject_type,
            subject_id=subject_id,
            skill_db_id=skill_db_id,
            workspace_id=workspace_id,
            can_list=grant_spec.can_list,
            can_invoke=grant_spec.can_invoke,
            can_install=grant_spec.can_install,
            can_manage=grant_spec.can_manage,
            granted_by=operator_user_id,
        )
        return True, grant
