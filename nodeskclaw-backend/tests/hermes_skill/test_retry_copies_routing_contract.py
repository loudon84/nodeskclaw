from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models.hermes_skill.hermes_task import TaskStatus
from app.services.hermes_skill.task_service import TaskService


@pytest.mark.asyncio
async def test_retry_create_task_copies_routing_contract():
    db = AsyncMock()
    service = TaskService(db)
    service.create_task = AsyncMock(
        return_value=SimpleNamespace(id="task-new", task_no="TASK-new")
    )

    original = SimpleNamespace(
        id="task-old",
        skill_id="skill.a",
        tool_name="tool.a",
        agent_id="agent-1",
        profile_id="writer",
        workspace_id="ws-1",
        installation_id=None,
        user_id="owner-1",
        arguments={"prompt": "hello"},
        client_context={"source": "expert_mcp_gateway"},
        routing_metadata={"route_snapshot": {"route_type": "hermes_api_server"}},
        output_policy={"artifact_mode": "pull_only"},
        request_snapshot={"tool_name": "tool.a"},
        request_trace_id="trace-1",
        route_diagnostics={"ok": True},
        catalog_slug="call-prep",
        task_no="TASK-old",
        status=TaskStatus.FAILED,
    )

    new_task = await service.create_task(
        org_id="org-1",
        skill_id=original.skill_id,
        tool_name=original.tool_name,
        agent_id=original.agent_id,
        profile_id=original.profile_id,
        workspace_id=original.workspace_id,
        installation_id=original.installation_id,
        user_id="owner-1",
        arguments=original.arguments,
        client_context=original.client_context,
        routing_metadata=original.routing_metadata,
        output_policy=original.output_policy,
        request_snapshot=original.request_snapshot,
        request_trace_id=original.request_trace_id,
        route_diagnostics=original.route_diagnostics,
        parent_task_id=original.id,
        catalog_slug=original.catalog_slug,
    )

    kwargs = service.create_task.await_args.kwargs
    assert kwargs["routing_metadata"] == original.routing_metadata
    assert kwargs["client_context"] == original.client_context
    assert kwargs["output_policy"] == original.output_policy
    assert kwargs["parent_task_id"] == original.id
    assert new_task.id == "task-new"
