from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.models.expert import Expert
from app.models.expert_skill import ExpertSkill
from app.services.expert_gateway.expert_mcp_gateway_service import ExpertMcpGatewayService
from app.services.expert_gateway.expert_skill_service import ExpertSkillService
from app.services.expert_gateway.errors import EXPERT_ROUTE_OVERRIDE_FORBIDDEN


def test_resolve_run_mode_defaults_to_event_stream():
    assert ExpertMcpGatewayService._resolve_run_mode(None) == "event_stream"
    assert ExpertMcpGatewayService._resolve_run_mode({}) == "event_stream"


def test_resolve_run_mode_sync_legacy():
    headers = {"X-NoDeskClaw-Expert-Run-Mode": "sync_legacy"}
    assert ExpertMcpGatewayService._resolve_run_mode(headers) == "sync_legacy"


def test_build_tool_descriptor_includes_streaming_annotations():
    expert = Expert(
        id="exp-1",
        org_id="org-1",
        hermes_agent_id="agent-1",
        expert_slug="call-prep",
        display_name="客户研究员",
    )
    skill = ExpertSkill(
        org_id="org-1",
        expert_id="exp-1",
        skill_name="customer-profiling",
        upstream_tool_name="tool.a",
        is_public=True,
        call_enabled=True,
    )
    descriptor = ExpertSkillService.build_tool_descriptor(expert, skill, runtime_ready=True)
    assert descriptor["annotations"]["callMode"] == "async_sse"
    assert descriptor["annotations"]["streaming"] is True
    assert descriptor["annotations"]["artifactMode"] == "pull_only"


@pytest.mark.asyncio
async def test_call_expert_skill_event_stream_returns_task_info():
    db = AsyncMock()
    gateway = ExpertMcpGatewayService(db)
    expert = Expert(
        id="exp-1",
        org_id="org-1",
        hermes_agent_id="agent-1",
        expert_slug="call-prep",
        display_name="客户研究员",
        published=True,
        enabled=True,
    )
    skill = ExpertSkill(
        id="skill-1",
        org_id="org-1",
        expert_id="exp-1",
        skill_name="customer-profiling",
        upstream_tool_name="tool.a",
        is_public=True,
        call_enabled=True,
    )
    accepted = {
        "jsonrpc": "2.0",
        "id": "1",
        "result": {
            "structuredContent": {
                "taskId": "task-1",
                "eventSseUrl": "/api/v1/hermes/tasks/task-1/events?token=abc",
            }
        },
    }

    gateway.catalog.runtime_ready = AsyncMock(return_value=True)
    gateway.skills.get_skill_by_name = AsyncMock(return_value=skill)
    gateway.catalog.resolve_agent_profile = AsyncMock(return_value="writer")
    gateway.logs.create_started = AsyncMock(return_value=SimpleNamespace(id="log-1"))

    with patch(
        "app.services.expert_gateway.expert_mcp_gateway_service.ExpertRunService.start_expert_skill_run",
        new=AsyncMock(return_value=accepted),
    ) as mock_start:
        result = await gateway._call_expert_skill(
            "org-1",
            "user-1",
            expert,
            "customer-profiling",
            {"prompt": "hello"},
            jsonrpc_id="1",
            headers={"x-client": "copilot-desktop"},
        )

    mock_start.assert_awaited_once()
    assert result["result"]["structuredContent"]["taskId"] == "task-1"


@pytest.mark.asyncio
async def test_dispatch_tools_call_rejects_route_override():
    db = AsyncMock()
    gateway = ExpertMcpGatewayService(db)
    item = SimpleNamespace(
        kind="expert",
        slug="call-prep",
        published=True,
        enabled=True,
        orchestration_mode="upstream_skill",
        source_record=Expert(
            id="exp-1",
            org_id="org-1",
            hermes_agent_id="agent-1",
            expert_slug="call-prep",
            display_name="客户研究员",
            published=True,
            enabled=True,
        ),
    )

    with patch(
        "app.services.expert_gateway.expert_mcp_gateway_service.ExpertPermissionService.has",
        new=AsyncMock(return_value=True),
    ):
        result = await gateway._dispatch_tools_call(
            "org-1",
            "user-1",
            item,
            {
                "params": {
                    "name": "customer-profiling",
                    "arguments": {"prompt": "hi", "profile": "override"},
                }
            },
            jsonrpc_id="1",
        )

    assert result["error"]["data"]["errorCode"] == EXPERT_ROUTE_OVERRIDE_FORBIDDEN
