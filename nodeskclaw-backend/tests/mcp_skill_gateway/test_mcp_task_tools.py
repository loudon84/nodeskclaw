from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.hermes_skill.hermes_task import TaskStatus
from app.services.mcp_skill_gateway.auth import McpAuthContext
from app.services.mcp_skill_gateway.handler import _build_hermes_skill_text, dispatch


def _auth_ctx():
    return McpAuthContext(
        user=SimpleNamespace(id="user-1"),
        org=SimpleNamespace(id="org-1"),
        auth_type="mcp_client_token",
        mcp_client_token_id="tok-1",
        allowed_skills=["skill.a"],
    )


@pytest.mark.asyncio
async def test_tools_list_includes_builtin_task_tools():
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    db = AsyncMock()
    auth_ctx = _auth_ctx()

    with patch(
        "app.services.mcp_skill_gateway.handler.resolve_mcp_user",
        new=AsyncMock(return_value=auth_ctx),
    ), patch(
        "app.services.mcp_skill_gateway.handler.McpToolMapper.list_tools",
        new=AsyncMock(return_value=[]),
    ):
        result = await dispatch(body, "Bearer ndsk_mcp_x.test", db)

    tool_names = {tool["name"] for tool in result["result"]["tools"]}
    assert "nodeskclaw_task_result" in tool_names
    assert "nodeskclaw_task_timeline" in tool_names


@pytest.mark.asyncio
async def test_tools_call_task_result_running():
    task = SimpleNamespace(
        id="task-1",
        task_no="TASK-001",
        org_id="org-1",
        tool_name="skill.a",
        status=TaskStatus.RUNNING,
        client_context={"mcp_client_token_id": "tok-1"},
    )
    db = AsyncMock()
    auth_ctx = _auth_ctx()
    body = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": "nodeskclaw_task_result", "arguments": {"task_id": "task-1"}},
    }

    with patch(
        "app.services.mcp_skill_gateway.handler.resolve_mcp_user",
        new=AsyncMock(return_value=auth_ctx),
    ), patch(
        "app.services.mcp_skill_gateway.mcp_task_access_service.TaskService.get_task",
        new=AsyncMock(return_value=task),
    ), patch(
        "app.services.mcp_skill_gateway.handler.log_mcp_call",
        new=AsyncMock(),
    ), patch(
        "app.services.mcp_skill_gateway.builtin_task_tool_executor.SkillAuditLogger.log",
        new=AsyncMock(),
    ):
        result = await dispatch(body, "Bearer ndsk_mcp_x.test", db)

    structured = result["result"]["structuredContent"]
    assert structured["ready"] is False
    assert structured["next_action"] == "poll_timeline_or_wait"


@pytest.mark.asyncio
async def test_tools_call_task_result_completed():
    task = SimpleNamespace(
        id="task-1",
        task_no="TASK-001",
        org_id="org-1",
        tool_name="skill.a",
        status=TaskStatus.COMPLETED,
        client_context={"mcp_client_token_id": "tok-1"},
    )
    db = AsyncMock()
    auth_ctx = _auth_ctx()
    body = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "nodeskclaw_task_result", "arguments": {"task_id": "task-1"}},
    }
    full_result = {
        "task": {"id": "task-1", "task_no": "TASK-001", "status": "completed"},
        "result_summary": "完成",
        "artifact_mode": "pull_only",
        "artifact_status": "stored",
        "kb_status": "pending_review",
        "server_artifacts": [{
            "artifact_id": "art-1",
            "name": "report.md",
        }],
        "timeline": [],
    }

    with patch(
        "app.services.mcp_skill_gateway.handler.resolve_mcp_user",
        new=AsyncMock(return_value=auth_ctx),
    ), patch(
        "app.services.mcp_skill_gateway.mcp_task_access_service.TaskService.get_task",
        new=AsyncMock(return_value=task),
    ), patch(
        "app.services.mcp_skill_gateway.builtin_task_tool_executor.TaskResultService.get_result",
        new=AsyncMock(return_value=full_result),
    ), patch(
        "app.services.mcp_skill_gateway.handler.log_mcp_call",
        new=AsyncMock(),
    ), patch(
        "app.services.mcp_skill_gateway.builtin_task_tool_executor.SkillAuditLogger.log",
        new=AsyncMock(),
    ):
        result = await dispatch(body, "Bearer ndsk_mcp_x.test", db)

    structured = result["result"]["structuredContent"]
    assert structured["ready"] is True
    assert structured["server_artifacts"][0]["artifact_id"] == "art-1"


def test_build_hermes_skill_text_completed():
    text = _build_hermes_skill_text({
        "task_no": "TASK-001",
        "status": "completed",
        "ready": True,
        "server_artifacts": [{"name": "report.md"}],
        "kb_status": "pending_review",
    })
    assert "TASK-001" in text
    assert "report.md" in text
    assert "pending_review" in text


def test_build_hermes_skill_text_wait_timeout():
    text = _build_hermes_skill_text({
        "task_no": "TASK-001",
        "status": "running",
        "wait_timeout": True,
    })
    assert "nodeskclaw_task_wait" in text


@pytest.mark.asyncio
async def test_tools_call_task_wait_delegates_to_wait_service():
    task = SimpleNamespace(
        id="task-1",
        task_no="TASK-001",
        org_id="org-1",
        tool_name="skill.a",
        status=TaskStatus.RUNNING,
        client_context={"mcp_client_token_id": "tok-1"},
    )
    db = AsyncMock()
    auth_ctx = _auth_ctx()
    wait_payload = {
        "task_id": "task-1",
        "task_no": "TASK-001",
        "status": "completed",
        "ready": True,
        "server_artifacts": [],
    }

    with patch(
        "app.services.mcp_skill_gateway.builtin_task_tool_executor.McpTaskWaitService.wait_for_task_result",
        new=AsyncMock(return_value=wait_payload),
    ), patch(
        "app.services.mcp_skill_gateway.mcp_task_access_service.TaskService.get_task",
        new=AsyncMock(return_value=task),
    ), patch(
        "app.services.mcp_skill_gateway.builtin_task_tool_executor.SkillAuditLogger.log",
        new=AsyncMock(),
    ):
        from app.services.mcp_skill_gateway.builtin_task_tool_executor import BuiltinTaskToolExecutor
        payload = await BuiltinTaskToolExecutor(db).call(
            "nodeskclaw_task_wait",
            {"task_id": "task-1", "timeout_seconds": 120},
            auth_ctx,
        )

    assert payload["structuredContent"]["ready"] is True
    assert "TASK-001" in payload["content"][0]["text"]
