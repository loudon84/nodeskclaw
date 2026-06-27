from __future__ import annotations

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.base import not_deleted
from app.models.expert import Expert
from app.models.expert_skill import ExpertSkill
from app.models.expert_team import ExpertTeam
from app.models.expert_team_member import ExpertTeamMember
from app.models.expert_team_skill import ExpertTeamSkill
from app.models.hermes_skill.hermes_agent_instance import HermesAgentInstance
from app.schemas.expert import (
    ExpertTeamCreateBody,
    ExpertTeamItem,
    ExpertTeamMemberBody,
    ExpertTeamUpdateBody,
)


class ExpertTeamService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, org_id: str, team_id: str) -> ExpertTeam | None:
        stmt = select(ExpertTeam).where(
            ExpertTeam.org_id == org_id,
            ExpertTeam.id == team_id,
            not_deleted(ExpertTeam),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_slug(self, org_id: str, team_slug: str) -> ExpertTeam | None:
        stmt = select(ExpertTeam).where(
            ExpertTeam.org_id == org_id,
            ExpertTeam.team_slug == team_slug,
            not_deleted(ExpertTeam),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_teams(self, org_id: str) -> list[ExpertTeamItem]:
        stmt = (
            select(ExpertTeam)
            .where(ExpertTeam.org_id == org_id, not_deleted(ExpertTeam))
            .order_by(ExpertTeam.sort_order.asc(), ExpertTeam.created_at.asc())
        )
        teams = (await self.db.execute(stmt)).scalars().all()
        items: list[ExpertTeamItem] = []
        for team in teams:
            items.append(await self._to_item(team))
        return items

    async def list_published_teams(self, org_id: str) -> list[ExpertTeam]:
        stmt = (
            select(ExpertTeam)
            .where(
                ExpertTeam.org_id == org_id,
                ExpertTeam.published.is_(True),
                ExpertTeam.enabled.is_(True),
                not_deleted(ExpertTeam),
            )
            .order_by(ExpertTeam.sort_order.asc())
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def create_team(self, org_id: str, user_id: str, body: ExpertTeamCreateBody) -> ExpertTeamItem:
        if await self.get_by_slug(org_id, body.team_slug):
            raise BadRequestError(message="团队 slug 已存在", message_key="errors.expert.team_slug_exists")
        team = ExpertTeam(
            org_id=org_id,
            team_slug=body.team_slug.strip(),
            display_name=body.display_name.strip(),
            description=body.description,
            category=body.category,
            tags=body.tags or [],
            avatar=body.avatar,
            hermes_agent_id=body.hermes_agent_id,
            orchestration_mode=body.orchestration_mode,
            published=body.published,
            enabled=body.enabled,
            sort_order=body.sort_order,
            created_by=user_id,
            updated_by=user_id,
        )
        self.db.add(team)
        await self.db.flush()
        return await self._to_item(team)

    async def update_team(
        self,
        org_id: str,
        user_id: str,
        team_id: str,
        body: ExpertTeamUpdateBody,
    ) -> ExpertTeamItem:
        team = await self.get_by_id(org_id, team_id)
        if team is None:
            raise NotFoundError(message="专家团队不存在", message_key="errors.expert.team_not_found")
        if body.team_slug and body.team_slug != team.team_slug:
            conflict = await self.get_by_slug(org_id, body.team_slug)
            if conflict and conflict.id != team.id:
                raise BadRequestError(message="团队 slug 已存在", message_key="errors.expert.team_slug_exists")
            team.team_slug = body.team_slug.strip()
        if body.display_name is not None:
            team.display_name = body.display_name.strip()
        if body.description is not None:
            team.description = body.description
        if body.category is not None:
            team.category = body.category
        if body.tags is not None:
            team.tags = body.tags
        if body.avatar is not None:
            team.avatar = body.avatar
        if body.hermes_agent_id is not None:
            team.hermes_agent_id = body.hermes_agent_id
        if body.orchestration_mode is not None:
            team.orchestration_mode = body.orchestration_mode
        if body.sort_order is not None:
            team.sort_order = body.sort_order
        if body.published is not None:
            if body.published:
                await self.validate_publish(org_id, team)
            team.published = body.published
        if body.enabled is not None:
            team.enabled = body.enabled
        team.updated_by = user_id
        await self.db.flush()
        return await self._to_item(team)

    async def add_member(
        self,
        org_id: str,
        team_id: str,
        body: ExpertTeamMemberBody,
    ) -> None:
        team = await self.get_by_id(org_id, team_id)
        if team is None:
            raise NotFoundError(message="专家团队不存在", message_key="errors.expert.team_not_found")
        member = ExpertTeamMember(
            org_id=org_id,
            team_id=team_id,
            expert_id=body.expert_id,
            role=body.role,
            responsibility=body.responsibility,
            order_no=body.order_no,
            required=body.required,
        )
        self.db.add(member)
        await self.db.flush()

    async def list_members(self, org_id: str, team_id: str) -> list[ExpertTeamMember]:
        stmt = (
            select(ExpertTeamMember)
            .where(
                ExpertTeamMember.org_id == org_id,
                ExpertTeamMember.team_id == team_id,
                not_deleted(ExpertTeamMember),
            )
            .order_by(ExpertTeamMember.order_no.asc())
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def validate_publish(self, org_id: str, team: ExpertTeam) -> None:
        issues: list[str] = []
        if not team.team_slug:
            issues.append("missing_slug")
        if not team.display_name:
            issues.append("missing_display_name")
        mode = team.orchestration_mode or "upstream_skill"
        if mode == "sequential_gateway":
            mode = "gateway_sequential"
        if mode == "upstream_skill":
            if not team.hermes_agent_id:
                issues.append("agent_not_bound")
            else:
                agent = await self._get_agent(org_id, team.hermes_agent_id)
                if agent.docker_status not in {"running", "online"}:
                    issues.append("docker_not_running")
                if agent.gateway_status not in {"online", "ready"}:
                    issues.append("api_server_not_online")
                if agent.mcp_status not in {"online", "ready", "callable"}:
                    issues.append("agent_not_callable")
                if agent.gateway_runtime_status not in {"online", "ready"}:
                    issues.append("runtime_not_ready")
            public_count = await self._count_public_team_skills(org_id, team.id)
            if public_count <= 0:
                issues.append("no_public_skill")
        elif mode == "gateway_sequential":
            members = await self.list_members(org_id, team.id)
            if len(members) < 2:
                issues.append("expert_team_members_required")
            for member in members:
                expert = await self._get_expert(org_id, member.expert_id)
                if expert is None or not expert.enabled:
                    issues.append("expert_team_member_not_enabled")
                    break
                if not expert.published:
                    issues.append("expert_team_member_not_published")
                    break
                callable_count = await self._count_callable_expert_skills(org_id, expert.id)
                if callable_count <= 0:
                    issues.append("expert_team_member_skill_not_callable")
                    break
        else:
            issues.append("unsupported_orchestration_mode")
        if issues:
            raise BadRequestError(
                message=f"团队发布前置条件未满足: {', '.join(issues)}",
                message_key="errors.expert.team_publish_precondition_failed",
                message_params={"issues": issues},
            )

    async def _get_agent(self, org_id: str, agent_id: str) -> HermesAgentInstance:
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

    async def _get_expert(self, org_id: str, expert_id: str) -> Expert | None:
        stmt = select(Expert).where(
            Expert.org_id == org_id,
            Expert.id == expert_id,
            not_deleted(Expert),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def _count_public_team_skills(self, org_id: str, team_id: str) -> int:
        stmt = select(func.count()).select_from(ExpertTeamSkill).where(
            ExpertTeamSkill.org_id == org_id,
            ExpertTeamSkill.expert_team_id == team_id,
            ExpertTeamSkill.is_public.is_(True),
            not_deleted(ExpertTeamSkill),
        )
        return int((await self.db.execute(stmt)).scalar_one())

    async def _count_callable_expert_skills(self, org_id: str, expert_id: str) -> int:
        stmt = select(func.count()).select_from(ExpertSkill).where(
            ExpertSkill.org_id == org_id,
            ExpertSkill.expert_id == expert_id,
            ExpertSkill.is_public.is_(True),
            ExpertSkill.call_enabled.is_(True),
            not_deleted(ExpertSkill),
        )
        return int((await self.db.execute(stmt)).scalar_one())

    async def _to_item(self, team: ExpertTeam) -> ExpertTeamItem:
        count_stmt = select(func.count()).select_from(ExpertTeamMember).where(
            ExpertTeamMember.org_id == team.org_id,
            ExpertTeamMember.team_id == team.id,
            not_deleted(ExpertTeamMember),
        )
        member_count = int((await self.db.execute(count_stmt)).scalar_one())
        agent_profile = None
        if team.hermes_agent_id:
            agent_stmt = select(HermesAgentInstance).where(
                HermesAgentInstance.org_id == team.org_id,
                HermesAgentInstance.id == team.hermes_agent_id,
                not_deleted(HermesAgentInstance),
            )
            agent = (await self.db.execute(agent_stmt)).scalar_one_or_none()
            if agent is not None:
                agent_profile = agent.profile_name
        mode = team.orchestration_mode or "upstream_skill"
        if mode == "sequential_gateway":
            mode = "gateway_sequential"
        public_stmt = select(func.count()).select_from(ExpertTeamSkill).where(
            ExpertTeamSkill.org_id == team.org_id,
            ExpertTeamSkill.expert_team_id == team.id,
            ExpertTeamSkill.is_public.is_(True),
            not_deleted(ExpertTeamSkill),
        )
        callable_stmt = select(func.count()).select_from(ExpertTeamSkill).where(
            ExpertTeamSkill.org_id == team.org_id,
            ExpertTeamSkill.expert_team_id == team.id,
            ExpertTeamSkill.is_public.is_(True),
            ExpertTeamSkill.call_enabled.is_(True),
            not_deleted(ExpertTeamSkill),
        )
        public_skill_count = int((await self.db.execute(public_stmt)).scalar_one())
        callable_skill_count = int((await self.db.execute(callable_stmt)).scalar_one())
        return ExpertTeamItem(
            id=team.id,
            org_id=team.org_id,
            team_slug=team.team_slug,
            display_name=team.display_name,
            description=team.description,
            category=team.category,
            tags=list(team.tags or []),
            avatar=team.avatar,
            hermes_agent_id=team.hermes_agent_id,
            orchestration_mode=mode,
            published=team.published,
            enabled=team.enabled,
            sort_order=team.sort_order,
            agent_profile=agent_profile,
            public_skill_count=public_skill_count,
            callable_skill_count=callable_skill_count,
            member_count=member_count,
            created_at=team.created_at,
            updated_at=team.updated_at,
        )
