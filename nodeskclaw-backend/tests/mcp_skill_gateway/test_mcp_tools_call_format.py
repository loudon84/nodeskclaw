import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.mcp_skill_gateway.handler import dispatch_authenticated


@pytest.mark.asyncio
async def test_tools_call_success_returns_json_content():
    user = MagicMock()
    user.id = "user-1"
    org = MagicMock()
    org.id = "org-1"
    body = {
        "jsonrpc": "2.0",
        "id": "call-1",
        "method": "tools/call",
        "params": {
            "name": "writer_article_generate",
            "arguments": {"prompt": "hello"},
        },
    }
    db = AsyncMock()
    payload = {
        "task_id": "task-1",
        "status": "queued",
        "ready": False,
        "content": [{"type": "text", "text": "accepted"}],
        "structuredContent": {"task_id": "task-1", "status": "queued"},
    }

    with patch(
        "app.services.mcp_skill_gateway.handler.McpToolMapper",
    ) as mapper_cls, patch(
        "app.services.mcp_skill_gateway.handler.log_mcp_call",
        new=AsyncMock(),
    ):
        mapper = AsyncMock()
        mapper.call_tool.return_value = payload
        mapper_cls.return_value = mapper

        result = await dispatch_authenticated(body, (user, org), db)

    assert result["result"]["isError"] is False
    assert result["result"]["structuredContent"]["task_id"] == "task-1"


def test_build_structured_content_optional_contract_version():
    from app.services.hermes_skill.runtime_skill_run_service import RuntimeSkillRunService
    from app.schemas.hermes_skill.runtime_skill_run import StartRuntimeSkillRunRequest

    task = MagicMock()
    task.id = "task-123"
    task.status = "running"
    task.server_artifacts = []

    req = StartRuntimeSkillRunRequest(
        org_id="org-1",
        user_id="user-1",
        tool_name="test_tool",
        runtime_skill_id="test_tool",
        agent_profile="agent",
        hermes_agent_instance_id="inst-1",
        agent_id="agent-1",
        arguments={},
        client_context={},
        output_policy={"artifact_mode": "pull_only"},
        task_source="org_mcp",
        skill_id="test_tool",
    )

    with patch("app.services.hermes_skill.runtime_skill_run_service.settings.SKILL_AGENT_ENABLED", True):
        content_v11 = RuntimeSkillRunService.build_structured_content(
            task=task,
            request=req,
            event_sse_url="/events",
            output_policy={"artifact_mode": "pull_only"},
            contract_version="1.1.0",
        )
        assert content_v11["run_id"] == "task-123"
        assert content_v11["contract_version"] == "1.1.0"
        assert content_v11["committed"] is True

        content_default = RuntimeSkillRunService.build_structured_content(
            task=task,
            request=req,
            event_sse_url="/events",
            output_policy={"artifact_mode": "pull_only"},
        )
        assert "contract_version" not in content_default


