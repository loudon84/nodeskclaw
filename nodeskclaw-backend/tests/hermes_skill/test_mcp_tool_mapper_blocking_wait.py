from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.models.hermes_skill.hermes_task import TaskStatus
from app.services.hermes_skill.mcp_tool_mapper import McpToolMapper


@pytest.mark.asyncio
async def test_finalize_wait_response_commits_wait_result():
    db = AsyncMock()
    mapper = McpToolMapper(db)
    task = SimpleNamespace(
        id="task-1",
        task_no="TASK-001",
        status=TaskStatus.RUNNING,
    )
    installation = SimpleNamespace(
        id="inst-1",
        agent_id="agent-1",
        profile_id="default",
        workspace_id="default",
    )
    wait_payload = {
        "task_id": "task-1",
        "task_no": "TASK-001",
        "status": "completed",
        "ready": True,
        "server_artifacts": [{"artifact_id": "a1"}],
    }

    with patch(
        "app.services.hermes_skill.mcp_tool_mapper.McpTaskWaitService.wait_for_task_result",
        new=AsyncMock(return_value=wait_payload),
    ):
        result = await mapper._finalize_wait_response(
            "task-1",
            "org-1",
            tool_name="tool.a",
            agent_alias="writer",
            installation=installation,
            deduped=True,
            existing_task=task,
        )

    assert result["committed"] is True
    assert result["deduped"] is True
    assert result["ready"] is True
    assert result["installation_id"] == "inst-1"


@pytest.mark.asyncio
async def test_finalize_wait_response_completed_dedup_skips_wait():
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
        "app.services.hermes_skill.mcp_tool_mapper.McpTaskWaitService.wait_for_task_result",
        new=AsyncMock(),
    ) as mock_wait:
        result = await mapper._finalize_wait_response(
            "task-1",
            "org-1",
            tool_name="tool.a",
            agent_alias="writer",
            installation=installation,
            deduped=True,
            existing_task=task,
        )

    mock_build.assert_awaited_once()
    mock_wait.assert_not_awaited()
    assert result["ready"] is True
