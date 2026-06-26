from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.hermes_skill.hermes_task import TaskStatus
from app.services.mcp_skill_gateway.auth import McpAuthContext
from app.services.mcp_skill_gateway.mcp_task_access_service import McpTaskAccessService


def _auth_ctx(**kwargs):
    defaults = {
        "user": SimpleNamespace(id="user-a"),
        "org": SimpleNamespace(id="org-1"),
        "auth_type": "mcp_client_token",
        "mcp_client_token_id": "tok-a",
        "mcp_client_token_prefix": "ndsk_mcp_writer_abcd",
        "allowed_skills": ["skill.a"],
        "hermes_agent_id": "agent-a",
        "profile": "default",
    }
    defaults.update(kwargs)
    return McpAuthContext(**defaults)


@pytest.mark.asyncio
async def test_assert_can_access_task_by_token_id():
    task = SimpleNamespace(
        id="task-1",
        org_id="org-1",
        tool_name="skill.a",
        user_id="user-b",
        profile_id="other",
        client_context={"mcp_client_token_id": "tok-a"},
    )
    db = AsyncMock()
    with patch(
        "app.services.mcp_skill_gateway.mcp_task_access_service.TaskService.get_task",
        new=AsyncMock(return_value=task),
    ):
        result = await McpTaskAccessService(db).assert_can_access_task("task-1", _auth_ctx())
    assert result is task


@pytest.mark.asyncio
async def test_assert_can_access_task_forbidden_for_other_token():
    task = SimpleNamespace(
        id="task-1",
        org_id="org-1",
        tool_name="skill.a",
        user_id="user-b",
        profile_id="other",
        client_context={"mcp_client_token_id": "tok-b"},
    )
    db = AsyncMock()
    with patch(
        "app.services.mcp_skill_gateway.mcp_task_access_service.TaskService.get_task",
        new=AsyncMock(return_value=task),
    ):
        with pytest.raises(ForbiddenError) as exc:
            await McpTaskAccessService(db).assert_can_access_task("task-1", _auth_ctx())
    assert exc.value.message_key == "errors.task.forbidden"


@pytest.mark.asyncio
async def test_assert_can_access_task_not_found():
    db = AsyncMock()
    with patch(
        "app.services.mcp_skill_gateway.mcp_task_access_service.TaskService.get_task",
        new=AsyncMock(side_effect=NotFoundError("任务不存在", "errors.task.not_found")),
    ):
        with pytest.raises(NotFoundError) as exc:
            await McpTaskAccessService(db).assert_can_access_task("missing", _auth_ctx())
    assert exc.value.message_key == "errors.task.not_found"


@pytest.mark.asyncio
async def test_assert_can_access_task_allowed_skills_gate():
    task = SimpleNamespace(
        id="task-1",
        org_id="org-1",
        tool_name="skill.b",
        user_id="user-a",
        profile_id="default",
        client_context={"mcp_client_token_id": "tok-a"},
    )
    db = AsyncMock()
    with patch(
        "app.services.mcp_skill_gateway.mcp_task_access_service.TaskService.get_task",
        new=AsyncMock(return_value=task),
    ):
        with pytest.raises(ForbiddenError):
            await McpTaskAccessService(db).assert_can_access_task(
                "task-1",
                _auth_ctx(allowed_skills=["skill.a"]),
            )


@pytest.mark.asyncio
async def test_assert_can_access_task_historical_fallback_user_id():
    task = SimpleNamespace(
        id="task-1",
        org_id="org-1",
        tool_name="skill.a",
        user_id="user-a",
        profile_id="other",
        client_context={},
    )
    db = AsyncMock()
    with patch(
        "app.services.mcp_skill_gateway.mcp_task_access_service.TaskService.get_task",
        new=AsyncMock(return_value=task),
    ):
        result = await McpTaskAccessService(db).assert_can_access_task(
            "task-1",
            _auth_ctx(mcp_client_token_id="tok-other"),
        )
    assert result is task
