from __future__ import annotations

import time
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.base import not_deleted
from app.models.expert import Expert
from app.models.expert_skill import ExpertSkill
from app.models.expert_team import ExpertTeam
from app.schemas.expert_mcp import ExpertHealthResponse, ExpertHealthRuntimeItem
from app.services.expert_gateway.expert_catalog_service import ExpertCatalogService

_cache: dict[str, tuple[float, ExpertHealthResponse]] = {}


class ExpertHealthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.catalog = ExpertCatalogService(db)

    async def get_health(self, org_id: str) -> ExpertHealthResponse:
        cache_key = org_id
        now = time.time()
        cached = _cache.get(cache_key)
        if cached and now - cached[0] < settings.EXPERT_HEALTH_CACHE_TTL:
            return cached[1]

        experts = await self.catalog.list_published_experts(org_id)
        public_skills = 0
        callable_skills = 0
        runtimes: list[ExpertHealthRuntimeItem] = []

        for expert in experts:
            public_count = await self.catalog._count_public_skills(org_id, expert.id)
            callable_count = await self.catalog._count_callable_skills(org_id, expert.id)
            public_skills += public_count
            callable_skills += callable_count
            ready = await self.catalog.runtime_ready(org_id, expert)
            agent_profile = await self.catalog.resolve_agent_profile(org_id, expert)
            runtimes.append(
                ExpertHealthRuntimeItem(
                    expert_slug=expert.expert_slug,
                    display_name=expert.display_name,
                    status="ready" if ready else "offline",
                    agent_alias=agent_profile,
                    api_server="online" if ready else "offline",
                    agent_callable=ready,
                    runtime_ready=ready,
                )
            )

        team_count_stmt = select(func.count()).select_from(ExpertTeam).where(
            ExpertTeam.org_id == org_id,
            ExpertTeam.published.is_(True),
            ExpertTeam.enabled.is_(True),
            not_deleted(ExpertTeam),
        )
        published_teams = int((await self.db.execute(team_count_stmt)).scalar_one())

        response = ExpertHealthResponse(
            ok=True,
            status="healthy" if runtimes else "degraded",
            gateway={"name": "expert-mcp-gateway", "version": "v6.0"},
            catalog={
                "publishedExperts": len(experts) + published_teams,
                "publicSkills": public_skills,
                "callableSkills": callable_skills,
            },
            runtimes=runtimes,
        )
        _cache[cache_key] = (now, response)
        return response
