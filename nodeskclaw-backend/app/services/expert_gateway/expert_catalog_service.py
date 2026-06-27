from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.base import not_deleted
from app.models.expert import Expert
from app.models.expert_skill import ExpertSkill
from app.models.hermes_skill.hermes_agent_instance import HermesAgentInstance
from app.schemas.expert import ExpertCreateBody, ExpertItem, ExpertUpdateBody
from app.services.expert_gateway.expert_invocation_log_service import ExpertInvocationLogService
from app.services.hermes_external.hermes_docker_binding_service import HermesDockerBindingService


def _slugify_skill_name(upstream_tool_name: str) -> str:
    name = upstream_tool_name
    if "__" in name:
        name = name.split("__", 1)[-1]
    name = name.replace("_", "-").strip("-")
    return re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-") or upstream_tool_name


class ExpertCatalogService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, org_id: str, expert_id: str) -> Expert | None:
        stmt = select(Expert).where(
            Expert.org_id == org_id,
            Expert.id == expert_id,
            not_deleted(Expert),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_slug(self, org_id: str, expert_slug: str) -> Expert | None:
        stmt = select(Expert).where(
            Expert.org_id == org_id,
            Expert.expert_slug == expert_slug,
            not_deleted(Expert),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_agent_id(self, org_id: str, hermes_agent_id: str) -> Expert | None:
        stmt = select(Expert).where(
            Expert.org_id == org_id,
            Expert.hermes_agent_id == hermes_agent_id,
            not_deleted(Expert),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_experts(self, org_id: str) -> list[ExpertItem]:
        stmt = (
            select(Expert)
            .where(Expert.org_id == org_id, not_deleted(Expert))
            .order_by(Expert.sort_order.asc(), Expert.created_at.asc())
        )
        experts = (await self.db.execute(stmt)).scalars().all()
        log_svc = ExpertInvocationLogService(self.db)
        items: list[ExpertItem] = []
        for expert in experts:
            items.append(await self._to_item(expert, log_svc))
        return items

    async def list_published_experts(self, org_id: str) -> list[Expert]:
        stmt = (
            select(Expert)
            .where(
                Expert.org_id == org_id,
                Expert.published.is_(True),
                Expert.enabled.is_(True),
                not_deleted(Expert),
            )
            .order_by(Expert.sort_order.asc(), Expert.created_at.asc())
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def create_expert(
        self,
        org_id: str,
        user_id: str,
        body: ExpertCreateBody,
    ) -> ExpertItem:
        existing = await self.get_by_slug(org_id, body.expert_slug)
        if existing:
            raise BadRequestError(
                message="专家 slug 已存在",
                message_key="errors.expert.slug_exists",
            )
        agent = await self._get_agent(org_id, body.hermes_agent_id)
        expert = Expert(
            org_id=org_id,
            hermes_agent_id=agent.id,
            expert_slug=body.expert_slug.strip(),
            display_name=body.display_name.strip(),
            description=body.description,
            category=body.category,
            tags=body.tags or [],
            avatar=body.avatar,
            published=body.published,
            enabled=body.enabled,
            sort_order=body.sort_order,
            created_by=user_id,
            updated_by=user_id,
        )
        self.db.add(expert)
        agent.expert_enabled = True
        await self.db.flush()
        return await self._to_item(expert, ExpertInvocationLogService(self.db))

    async def update_expert(
        self,
        org_id: str,
        user_id: str,
        expert_id: str,
        body: ExpertUpdateBody,
    ) -> ExpertItem:
        expert = await self.get_by_id(org_id, expert_id)
        if expert is None:
            raise NotFoundError(message="专家不存在", message_key="errors.expert.not_found")
        if body.expert_slug and body.expert_slug != expert.expert_slug:
            conflict = await self.get_by_slug(org_id, body.expert_slug)
            if conflict and conflict.id != expert.id:
                raise BadRequestError(
                    message="专家 slug 已存在",
                    message_key="errors.expert.slug_exists",
                )
            expert.expert_slug = body.expert_slug.strip()
        if body.display_name is not None:
            expert.display_name = body.display_name.strip()
        if body.description is not None:
            expert.description = body.description
        if body.category is not None:
            expert.category = body.category
        if body.tags is not None:
            expert.tags = body.tags
        if body.avatar is not None:
            expert.avatar = body.avatar
        if body.sort_order is not None:
            expert.sort_order = body.sort_order
        if body.published is not None:
            if body.published:
                await self.validate_publish(org_id, expert)
            expert.published = body.published
        if body.enabled is not None:
            expert.enabled = body.enabled
        expert.updated_by = user_id
        agent = await self._get_agent(org_id, expert.hermes_agent_id)
        agent.expert_enabled = True
        await self.db.flush()
        return await self._to_item(expert, ExpertInvocationLogService(self.db))

    async def publish_expert(self, org_id: str, user_id: str, expert_id: str) -> ExpertItem:
        expert = await self.get_by_id(org_id, expert_id)
        if expert is None:
            raise NotFoundError(message="专家不存在", message_key="errors.expert.not_found")
        await self.validate_publish(org_id, expert)
        expert.published = True
        expert.updated_by = user_id
        await self.db.flush()
        return await self._to_item(expert, ExpertInvocationLogService(self.db))

    async def unpublish_expert(self, org_id: str, user_id: str, expert_id: str) -> ExpertItem:
        expert = await self.get_by_id(org_id, expert_id)
        if expert is None:
            raise NotFoundError(message="专家不存在", message_key="errors.expert.not_found")
        expert.published = False
        expert.updated_by = user_id
        await self.db.flush()
        return await self._to_item(expert, ExpertInvocationLogService(self.db))

    async def validate_publish(self, org_id: str, expert: Expert) -> None:
        if not expert.expert_slug or not expert.display_name:
            raise BadRequestError(
                message="发布专家前必须配置 slug 和名称",
                message_key="errors.expert.publish_missing_meta",
            )
        agent = await self._get_agent(org_id, expert.hermes_agent_id)
        issues: list[str] = []
        if agent.docker_status not in {"running", "online"}:
            issues.append("docker_not_running")
        if agent.gateway_status not in {"online", "ready"}:
            issues.append("api_server_offline")
        if agent.mcp_status not in {"online", "ready", "callable"}:
            issues.append("agent_not_callable")
        if agent.gateway_runtime_status not in {"online", "ready"}:
            issues.append("runtime_not_ready")
        if not agent.mcp_gateway_env_synced:
            issues.append("mcp_env_not_synced")
        if not agent.mcp_router_enabled or not agent.mcp_router_last_synced_at:
            issues.append("router_not_synced")
        public_count = await self._count_public_skills(org_id, expert.id)
        if public_count <= 0:
            issues.append("no_public_skill")
        if issues:
            raise BadRequestError(
                message=f"专家发布前置条件未满足: {', '.join(issues)}",
                message_key="errors.expert.publish_precondition_failed",
                message_params={"issues": issues},
            )

    async def resolve_agent_profile(self, org_id: str, expert: Expert) -> str:
        agent = await self._get_agent(org_id, expert.hermes_agent_id)
        return agent.profile_name

    async def runtime_ready(self, org_id: str, expert: Expert) -> bool:
        agent = await self._get_agent(org_id, expert.hermes_agent_id)
        return (
            agent.docker_status in {"running", "online"}
            and agent.gateway_status in {"online", "ready"}
            and agent.gateway_runtime_status in {"online", "ready"}
        )

    async def _get_agent(self, org_id: str, agent_id: str) -> HermesAgentInstance:
        binding = HermesDockerBindingService(self.db)
        stmt = select(HermesAgentInstance).where(
            HermesAgentInstance.org_id == org_id,
            HermesAgentInstance.id == agent_id,
            not_deleted(HermesAgentInstance),
        )
        agent = (await self.db.execute(stmt)).scalar_one_or_none()
        if agent is None:
            raise NotFoundError(
                message="Hermes Agent 实例不存在",
                message_key="errors.hermes.agent_instance_not_found",
            )
        return agent

    async def _count_public_skills(self, org_id: str, expert_id: str) -> int:
        stmt = select(func.count()).select_from(ExpertSkill).where(
            ExpertSkill.org_id == org_id,
            ExpertSkill.expert_id == expert_id,
            ExpertSkill.is_public.is_(True),
            not_deleted(ExpertSkill),
        )
        return int((await self.db.execute(stmt)).scalar_one())

    async def _count_callable_skills(self, org_id: str, expert_id: str) -> int:
        stmt = select(func.count()).select_from(ExpertSkill).where(
            ExpertSkill.org_id == org_id,
            ExpertSkill.expert_id == expert_id,
            ExpertSkill.is_public.is_(True),
            ExpertSkill.call_enabled.is_(True),
            not_deleted(ExpertSkill),
        )
        return int((await self.db.execute(stmt)).scalar_one())

    async def _count_total_skills(self, org_id: str, expert_id: str) -> int:
        stmt = select(func.count()).select_from(ExpertSkill).where(
            ExpertSkill.org_id == org_id,
            ExpertSkill.expert_id == expert_id,
            not_deleted(ExpertSkill),
        )
        return int((await self.db.execute(stmt)).scalar_one())

    async def _to_item(self, expert: Expert, log_svc: ExpertInvocationLogService) -> ExpertItem:
        agent = await self._get_agent(expert.org_id, expert.hermes_agent_id)
        return ExpertItem(
            id=expert.id,
            org_id=expert.org_id,
            hermes_agent_id=expert.hermes_agent_id,
            expert_slug=expert.expert_slug,
            display_name=expert.display_name,
            description=expert.description,
            category=expert.category,
            tags=list(expert.tags or []),
            avatar=expert.avatar,
            published=expert.published,
            enabled=expert.enabled,
            sort_order=expert.sort_order,
            agent_profile=agent.profile_name,
            public_skill_count=await self._count_public_skills(expert.org_id, expert.id),
            callable_skill_count=await self._count_callable_skills(expert.org_id, expert.id),
            total_skill_count=await self._count_total_skills(expert.org_id, expert.id),
            recent_invocation_count_24h=await log_svc.count_recent_by_expert(expert.org_id, expert.id),
            created_at=expert.created_at,
            updated_at=expert.updated_at,
        )

    @staticmethod
    def default_skill_name_from_upstream(upstream_tool_name: str) -> str:
        return _slugify_skill_name(upstream_tool_name)
