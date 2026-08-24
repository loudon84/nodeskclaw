from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.expert import Expert
from app.services.expert_gateway import expert_health_service
from app.services.expert_gateway.expert_health_service import ExpertHealthService


def _expert() -> Expert:
    return Expert(
        id="exp-1",
        org_id="org-1",
        hermes_agent_id="agent-1",
        expert_slug="call-prep",
        display_name="客户研究员",
        published=True,
        enabled=True,
    )


@pytest.mark.asyncio
async def test_get_health_includes_runtime_item_for_published_expert():
    # @lat: [[architecture/backend#Hermes And MCP]]
    expert_health_service._cache.clear()
    db = AsyncMock()
    empty_teams = MagicMock()
    empty_teams.scalars.return_value.all.return_value = []
    team_count = MagicMock()
    team_count.scalar_one.return_value = 0
    db.execute = AsyncMock(side_effect=[empty_teams, team_count])

    svc = ExpertHealthService(db)
    svc.catalog.list_published_experts = AsyncMock(return_value=[_expert()])
    svc.catalog._count_public_skills = AsyncMock(return_value=1)
    svc.catalog._count_callable_skills = AsyncMock(return_value=1)
    svc.catalog.runtime_ready = AsyncMock(return_value=True)
    svc.catalog.resolve_agent_profile = AsyncMock(return_value="writer")

    health = await svc.get_health("org-1")

    assert health.ok is True
    assert len(health.runtimes) == 1
    assert health.runtimes[0].expert_slug == "call-prep"
    assert health.runtimes[0].display_name == "客户研究员"
    assert health.runtimes[0].status == "ready"
    assert health.runtimes[0].agent_alias == "writer"
    assert health.runtimes[0].runtime_ready is True
