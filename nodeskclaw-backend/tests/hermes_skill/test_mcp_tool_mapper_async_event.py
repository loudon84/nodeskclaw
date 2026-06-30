from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.models.hermes_skill.hermes_task import EventType, TaskStatus
from app.services.hermes_skill.mcp_tool_mapper import McpToolMapper


@pytest.mark.asyncio
async def test_build_async_event_response_includes_event_stream():
    db = AsyncMock()
    mapper = McpToolMapper(db)
    task = SimpleNamespace(
        id="task-1",
        task_no="TASK-001",
        status=TaskStatus.QUEUED,
        event_url="/api/v1/hermes/tasks/task-1/events",
        artifact_url=None,
        server_artifacts=[],
    )
    installation = SimpleNamespace(
        id="inst-1",
        agent_id="agent-1",
        profile_id="default",
        workspace_id="default",
    )
    routing_result = SimpleNamespace(reason="matched")
    token_data = {
        "event_url": "/api/v1/hermes/tasks/task-1/events?token=sse_test",
        "expires_in": 900,
    }

    with patch(
        "app.services.hermes_skill.mcp_tool_mapper.TaskEventTokenService.create_token",
        new=AsyncMock(return_value=token_data),
    ):
        result = await mapper._build_async_event_response(
            task=task,
            tool_name="tool.a",
            agent_alias="writer",
            installation=installation,
            routing_result=routing_result,
            output_policy={"artifact_mode": "pull_only"},
            org_id="org-1",
            user_id="user-1",
            deduped=False,
        )

    assert result["execution_mode"] == "async_event"
    assert result["event_stream"] == token_data["event_url"]
    assert result["wait_strategy"]["type"] == "sse"
    assert result["wait_strategy"]["poll_url"] == "/api/v1/hermes/tasks/task-1"
    assert result["wait_strategy"]["result_url"] == "/api/v1/hermes/tasks/task-1/result"
    assert result["retryable"] is False
    assert result["committed"] is True
    assert result["status"] == "running"


@pytest.mark.asyncio
async def test_finalize_async_event_completed_skips_sse():
    db = AsyncMock()
    mapper = McpToolMapper(db)
    task = SimpleNamespace(
        id="task-1",
        task_no="TASK-001",
        status=TaskStatus.COMPLETED,
    )
    installation = SimpleNamespace(
        id="inst-1",
        agent_id="agent-1",
        profile_id="default",
        workspace_id="default",
    )
    completed_payload = {
        "task_id": "task-1",
        "task_no": "TASK-001",
        "status": "completed",
        "ready": True,
    }

    with patch(
        "app.services.hermes_skill.mcp_tool_mapper.McpTaskWaitService.build_result_for_task",
        new=AsyncMock(return_value=completed_payload),
    ) as mock_build, patch(
        "app.services.hermes_skill.mcp_tool_mapper.TaskEventTokenService.create_token",
        new=AsyncMock(),
    ) as mock_token:
        result = await mapper._finalize_async_event_response(
            task,
            "org-1",
            tool_name="tool.a",
            agent_alias="writer",
            installation=installation,
            routing_result=SimpleNamespace(reason="matched"),
            output_policy={},
            user_id="user-1",
            deduped=True,
        )

    mock_build.assert_awaited_once()
    mock_token.assert_not_awaited()
    assert result["ready"] is True
