from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

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
async def test_tools_list_excludes_builtin_task_tools():
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    db = AsyncMock()
    auth_ctx = _auth_ctx()

    with patch(
        "app.services.mcp_skill_gateway.handler.resolve_mcp_user",
        new=AsyncMock(return_value=auth_ctx),
    ), patch(
        "app.services.mcp_skill_gateway.handler.McpToolMapper.list_tools",
        new=AsyncMock(return_value=[{"name": "skill.a"}]),
    ):
        result = await dispatch(body, "Bearer ndsk_mcp_x.test", db)

    tool_names = {tool["name"] for tool in result["result"]["tools"]}
    assert "skill.a" in tool_names
    assert "nodeskclaw_task_result" not in tool_names
    assert "nodeskclaw_task_timeline" not in tool_names


@pytest.mark.asyncio
async def test_tools_call_task_tools_rejected_from_employee_catalog():
    db = AsyncMock()
    auth_ctx = _auth_ctx()
    for tool_name in (
        "nodeskclaw_task_result",
        "nodeskclaw_task_timeline",
        "nodeskclaw_task_wait",
    ):
        body = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": {"task_id": "task-1"}},
        }
        with patch(
            "app.services.mcp_skill_gateway.handler.resolve_mcp_user",
            new=AsyncMock(return_value=auth_ctx),
        ):
            result = await dispatch(body, "Bearer ndsk_mcp_x.test", db)
        assert "error" in result
        assert "not available on employee MCP catalog" in result["error"]["message"]


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
async def test_builtin_task_wait_executor_still_works_for_rest_compat():
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
