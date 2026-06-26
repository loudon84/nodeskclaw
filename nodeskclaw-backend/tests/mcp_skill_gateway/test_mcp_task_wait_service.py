from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.models.hermes_skill.hermes_task import TaskStatus
from app.services.mcp_skill_gateway.mcp_task_wait_service import McpTaskWaitService


def _task(status: TaskStatus, **kwargs):
    defaults = {
        "id": "task-1",
        "task_no": "TASK-001",
        "org_id": "org-1",
        "status": status,
        "error_code": None,
        "error_message": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


@pytest.mark.asyncio
async def test_wait_returns_completed_result():
    completed = _task(TaskStatus.COMPLETED)
    service = McpTaskWaitService()
    full_result = {
        "result_summary": "完成",
        "artifact_mode": "pull_only",
        "artifact_status": "stored",
        "kb_status": "pending_review",
        "server_artifacts": [{"artifact_id": "a1", "name": "report.md"}],
        "timeline": [{"event_type": "task.completed", "created_at": "t", "payload": {}}],
        "primary_artifact": None,
    }
    with patch.object(service, "_load_task", new=AsyncMock(return_value=completed)), patch(
        "app.services.mcp_skill_gateway.mcp_task_wait_service.TaskResultService.get_result",
        new=AsyncMock(return_value=full_result),
    ):
        result = await service.wait_for_task_result("task-1", "org-1", timeout_seconds=5)

    assert result["ready"] is True
    assert result["status"] == "completed"
    assert result["server_artifacts"][0]["artifact_id"] == "a1"


@pytest.mark.asyncio
async def test_wait_returns_failed_result():
    failed = _task(TaskStatus.FAILED, error_code="ERR", error_message="boom")
    service = McpTaskWaitService()
    with patch.object(service, "_load_task", new=AsyncMock(return_value=failed)):
        result = await service.wait_for_task_result("task-1", "org-1", timeout_seconds=1)
    assert result["ready"] is False
    assert result["isError"] is True
    assert result["status"] == "failed"


@pytest.mark.asyncio
async def test_wait_timeout_returns_next_tool(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "MCP_TASK_WAIT_RETURN_TIMELINE", False)

    running = _task(TaskStatus.RUNNING)
    service = McpTaskWaitService()

    async def always_running(task_id, org_id):
        return running

    with patch.object(service, "_load_task", new=AsyncMock(side_effect=always_running)), patch(
        "app.services.hermes_skill.event_bus.EventBus.get_instance"
    ) as mock_bus:
        mock_bus.return_value.wait = AsyncMock(return_value=False)
        result = await service.wait_for_task_result(
            "task-1",
            "org-1",
            timeout_seconds=1,
            poll_interval_seconds=1,
        )

    assert result["ready"] is False
    assert result["wait_timeout"] is True
    assert result["next_tool"] == "nodeskclaw_task_wait"
