from __future__ import annotations

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.base import not_deleted
from app.models.expert import Expert
from app.models.expert_team import ExpertTeam
from app.models.expert_team_member import ExpertTeamMember
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
        if body.orchestration_mode is not None:
            team.orchestration_mode = body.orchestration_mode
        if body.sort_order is not None:
            team.sort_order = body.sort_order
        if body.published is not None:
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

    async def _to_item(self, team: ExpertTeam) -> ExpertTeamItem:
        count_stmt = select(func.count()).select_from(ExpertTeamMember).where(
            ExpertTeamMember.org_id == team.org_id,
            ExpertTeamMember.team_id == team.id,
            not_deleted(ExpertTeamMember),
        )
        member_count = int((await self.db.execute(count_stmt)).scalar_one())
        return ExpertTeamItem(
            id=team.id,
            org_id=team.org_id,
            team_slug=team.team_slug,
            display_name=team.display_name,
            description=team.description,
            category=team.category,
            tags=list(team.tags or []),
            avatar=team.avatar,
            orchestration_mode=team.orchestration_mode,
            published=team.published,
            enabled=team.enabled,
            sort_order=team.sort_order,
            member_count=member_count,
            created_at=team.created_at,
            updated_at=team.updated_at,
        )
