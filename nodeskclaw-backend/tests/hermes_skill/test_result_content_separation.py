import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.hermes_skill.hermes_task import TaskStatus
from app.services.hermes_skill.task_result_service import TaskResultService


@pytest.mark.asyncio
async def test_get_result_uses_result_content_not_summary():
    db = AsyncMock()
    svc = TaskResultService(db)
    task = MagicMock()
    task.id = "task-1"
    task.task_no = "TASK-1"
    task.status = TaskStatus.COMPLETED
    task.tool_name = "tool.a"
    task.agent_id = "agent-1"
    task.profile_id = "writer"
    task.workspace_id = "ws-1"
    task.routing_metadata = {"agent_alias": "writer"}
    task.result_summary = "short"
    task.result_content = "x" * 600
    task.created_at = None
    task.completed_at = None
    task.skill_id = "skill.a"
    task.org_id = "org-1"
    task.server_artifacts = []
    task.artifact_status = "none"
    task.kb_status = "none"

    with patch.object(svc, "_get_task", AsyncMock(return_value=task)):
        with patch.object(svc, "_list_task_artifacts", AsyncMock(return_value=[])):
            with patch.object(svc, "_get_skill", AsyncMock(return_value=None)):
                with patch.object(svc, "_build_timeline", AsyncMock(return_value=[])):
                    result = await svc.get_result("task-1", "org-1")

    assert result["result_summary"] == "short"
    assert result["result_content"] == "x" * 600
    assert result["content"] == "x" * 600
    assert result["content"] != result["result_summary"]
