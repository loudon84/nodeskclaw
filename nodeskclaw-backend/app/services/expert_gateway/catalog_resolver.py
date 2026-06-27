from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expert import Expert
from app.models.expert_team import ExpertTeam
from app.services.expert_gateway.expert_catalog_service import ExpertCatalogService
from app.services.expert_gateway.expert_team_service import ExpertTeamService

CatalogKind = Literal["expert", "expert_team"]


@dataclass
class CatalogItem:
    id: str
    org_id: str
    kind: CatalogKind
    slug: str
    display_name: str
    description: str | None
    hermes_agent_id: str | None
    published: bool
    enabled: bool
    orchestration_mode: str
    source_record: Expert | ExpertTeam


class CatalogResolver:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.catalog = ExpertCatalogService(db)
        self.teams = ExpertTeamService(db)

    async def resolve(self, org_id: str, slug: str) -> CatalogItem | None:
        expert = await self.catalog.get_by_slug(org_id, slug)
        if expert is not None:
            return self._from_expert(expert)
        team = await self.teams.get_by_slug(org_id, slug)
        if team is not None:
            return self._from_team(team)
        return None

    @staticmethod
    def _from_expert(expert: Expert) -> CatalogItem:
        return CatalogItem(
            id=expert.id,
            org_id=expert.org_id,
            kind="expert",
            slug=expert.expert_slug,
            display_name=expert.display_name,
            description=expert.description,
            hermes_agent_id=expert.hermes_agent_id,
            published=expert.published,
            enabled=expert.enabled,
            orchestration_mode="upstream_skill",
            source_record=expert,
        )

    @staticmethod
    def _from_team(team: ExpertTeam) -> CatalogItem:
        mode = team.orchestration_mode or "upstream_skill"
        if mode == "sequential_gateway":
            mode = "gateway_sequential"
        return CatalogItem(
            id=team.id,
            org_id=team.org_id,
            kind="expert_team",
            slug=team.team_slug,
            display_name=team.display_name,
            description=team.description,
            hermes_agent_id=team.hermes_agent_id,
            published=team.published,
            enabled=team.enabled,
            orchestration_mode=mode,
            source_record=team,
        )
