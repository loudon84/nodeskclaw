from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.hermes_skill.mcp_skill_router_router import (
    get_mcp_skill_router_status,
    sync_mcp_skill_router,
)
from app.core.exceptions import ForbiddenError
from app.schemas.hermes_skill.mcp_skill_router import McpSkillRouterSyncRequest
from app.services.hermes_agents.mcp_skill_router_service import McpSkillRouterService


def _user_org():
    user = MagicMock()
    user.id = "user-1"
    org = MagicMock()
    org.id = "org-1"
    return user, org


@pytest.mark.asyncio
async def test_sync_mcp_skill_router_returns_result():
    user, org = _user_org()
    db = AsyncMock()
    result = {
        "ok": True,
        "agent_id": "agent-1",
        "instance_name": "common-writer",
        "profile": "default",
        "mcp_name": "common-skills",
        "router_skill_name": "nodeskclaw-skill-router",
        "router_skill_path": "/tmp/skills/nodeskclaw-skill-router/SKILL.md",
        "tool_count": 2,
        "tool_names": ["a", "b"],
        "synced_at": "2026-06-25T10:00:00+00:00",
    }

    with patch("app.api.hermes_skill.mcp_skill_router_router.PermissionChecker.require_permission", AsyncMock()):
        with patch.object(McpSkillRouterService, "sync", AsyncMock(return_value=result)):
            response = await sync_mcp_skill_router(
                "agent-1",
                McpSkillRouterSyncRequest(),
                user_org=(user, org),
                db=db,
            )

    assert response["code"] == 0
    assert response["data"]["tool_count"] == 2
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_sync_mcp_skill_router_member_forbidden():
    user, org = _user_org()
    db = AsyncMock()

    with patch(
        "app.api.hermes_skill.mcp_skill_router_router.PermissionChecker.require_permission",
        AsyncMock(side_effect=ForbiddenError()),
    ):
        with pytest.raises(ForbiddenError):
            await sync_mcp_skill_router(
                "agent-1",
                McpSkillRouterSyncRequest(),
                user_org=(user, org),
                db=db,
            )


@pytest.mark.asyncio
async def test_get_mcp_skill_router_status():
    user, org = _user_org()
    db = AsyncMock()
    status = {
        "status": "synced",
        "enabled": True,
        "router_skill_name": "nodeskclaw-skill-router",
        "router_skill_path": "/tmp/SKILL.md",
        "exists": True,
        "tool_count": 3,
        "last_synced_at": "2026-06-25T10:00:00+00:00",
        "last_error": None,
    }

    with patch("app.api.hermes_skill.mcp_skill_router_router.PermissionChecker.require_permission", AsyncMock()):
        with patch.object(McpSkillRouterService, "get_status", AsyncMock(return_value=status)):
            response = await get_mcp_skill_router_status(
                "agent-1",
                profile="default",
                user_org=(user, org),
                db=db,
            )

    assert response["code"] == 0
    assert response["data"]["status"] == "synced"
