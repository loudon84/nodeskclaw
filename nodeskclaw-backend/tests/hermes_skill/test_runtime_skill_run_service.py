from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.hermes_skill.hermes_task import TaskStatus
from app.schemas.hermes_skill.runtime_skill_run import StartRuntimeSkillRunRequest
from app.services.hermes_skill.runtime_skill_run_service import RuntimeSkillRunService


def _task():
    return SimpleNamespace(
        id="task-1",
        task_no="TASK-org1-abcd1234",
        event_url="/api/v1/hermes/tasks/task-1/events",
        artifact_url="/api/v1/hermes/tasks/task-1/artifacts",
        status=TaskStatus.QUEUED,
        server_artifacts=[],
    )


@pytest.mark.asyncio
async def test_resolve_placement_freezes_executable_connector_bindings():
    db = AsyncMock()
    rows = [
        {
            "binding_id": "binding-edge",
            "connector_instance_id": "instance-edge",
            "connector_kind": "rest",
            "connector_config": {"url": "https://edge.example.com", "network_policy": {"allowlist": ["edge.example.com:443"]}},
            "connector_secret_ref_id": "secret-edge",
            "placement": "edge",
            "edge_node_id": "node-1",
        },
        {
            "binding_id": "binding-central",
            "connector_instance_id": "instance-central",
            "connector_kind": "db",
            "connector_config": {"db_url": "postgresql://analytics"},
            "connector_secret_ref_id": None,
            "placement": "central",
            "edge_node_id": None,
        },
    ]
    result = MagicMock()
    result.mappings.return_value.all.return_value = rows
    db.execute = AsyncMock(return_value=result)

    placement = await RuntimeSkillRunService(db)._resolve_placement(
        org_id="org-1",
        requirements={"connector_binding_ids": ["binding-edge", "binding-central"]},
    )

    assert placement["role"] == "hybrid"
    assert placement["engine"] == "hybrid"
    assert placement["connector_bindings"][0]["network_policy"] == {"allowlist": ["edge.example.com:443"]}
    assert placement["connector_bindings"][1]["network_policy"] == {}


@pytest.mark.asyncio
async def test_connector_route_skips_hermes_gateway_enrichment():
    db = AsyncMock()
    service = RuntimeSkillRunService(db)

    route = await service._enrich_route_snapshot(
        SimpleNamespace(catalog_kind="connector", hermes_agent_instance_id="connector-central", agent_profile="connector", org_id="org-1", runtime_skill_id="tool-1"),
        {"route_type": "connector", "connector_kind": "rest"},
    )

    assert route == {"route_type": "connector", "connector_kind": "rest"}
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_builds_hermes_api_server_route_and_contract():
    db = AsyncMock()
    task = _task()
    request = StartRuntimeSkillRunRequest(
        org_id="org-1",
        user_id="user-1",
        tool_name="hermes_writer__customer-profiling",
        runtime_skill_id="customer-profiling",
        agent_profile="writer",
        hermes_agent_instance_id="binding-1",
        agent_id="inst-1",
        arguments={"prompt": "hello"},
        client_context={"source": "mcp_skill_gateway"},
        output_policy={"artifact_mode": "pull_only"},
        task_source="org_mcp",
        skill_id="customer-profiling",
        installation_id="install-1",
        execution_mode="async_event",
        entrypoint="mcp_skill_gateway",
    )

    with patch(
        "app.services.hermes_skill.runtime_skill_run_service.TaskService"
    ) as task_svc_cls, patch(
        "app.services.hermes_skill.runtime_skill_run_service.TaskEventTokenService"
    ) as token_svc_cls, patch.object(
        RuntimeSkillRunService,
        "_resolve_release_meta",
        AsyncMock(return_value={"skill_version": "1.0.0", "snapshot_hash": "hash-1"}),
    ), patch.object(
        RuntimeSkillRunService,
        "_enrich_route_snapshot",
        AsyncMock(return_value={"gateway_url": "http://example.com"}),
    ):
        task_svc = AsyncMock()
        task_svc.create_task.return_value = task
        task_svc_cls.return_value = task_svc
        token_svc_cls.return_value.create_token = AsyncMock(
            return_value={"event_url": "/api/v1/hermes/tasks/task-1/events?token=sse_test"}
        )

        result = await RuntimeSkillRunService(db).start(request)

    routing_metadata = task_svc.create_task.await_args.kwargs["routing_metadata"]
    route_snapshot = routing_metadata["route_snapshot"]
    contract = routing_metadata["execution_contract"]

    assert route_snapshot["route_type"] == "hermes_api_server"
    assert route_snapshot["force_instance"] is True
    assert route_snapshot["runtime_skill_id"] == "customer-profiling"
    assert contract["runtime_invocation"] == "chat_completions"
    assert contract["mode"] == "async_event"
    assert routing_metadata["task_source"] == "org_mcp"

    content = result.structured_content
    assert content["run_id"] == "task-1"
    assert content["event_stream"].endswith("token=sse_test")
    assert content["result_url"] == "/api/v1/runs/task-1/result"
    assert content["committed"] is True
    assert "taskId" not in content
    assert "eventSseUrl" not in content


@pytest.mark.asyncio
async def test_start_expert_mcp_includes_catalog_fields():
    db = AsyncMock()
    task = _task()
    request = StartRuntimeSkillRunRequest(
        org_id="org-1",
        user_id="user-1",
        tool_name="hermes_writer__customer-profiling",
        runtime_skill_id="customer-profiling",
        agent_profile="writer",
        hermes_agent_instance_id="binding-1",
        agent_id="inst-1",
        arguments={"prompt": "hello"},
        client_context={"source": "expert_mcp_gateway"},
        output_policy={"artifact_mode": "pull_only"},
        task_source="expert_mcp",
        skill_id="customer-profiling",
        execution_mode="async_event",
        entrypoint="expert_mcp_gateway",
        catalog_kind="expert",
        catalog_slug="call-prep",
        skill_name="customer-profiling",
        invocation_id="log-1",
    )

    with patch(
        "app.services.hermes_skill.runtime_skill_run_service.TaskService"
    ) as task_svc_cls, patch(
        "app.services.hermes_skill.runtime_skill_run_service.TaskEventTokenService"
    ) as token_svc_cls, patch.object(
        RuntimeSkillRunService,
        "_resolve_release_meta",
        AsyncMock(return_value={"skill_version": "1.0.0", "snapshot_hash": "hash-1"}),
    ), patch.object(
        RuntimeSkillRunService,
        "_enrich_route_snapshot",
        AsyncMock(return_value={"gateway_url": "http://example.com"}),
    ):
        task_svc = AsyncMock()
        task_svc.create_task.return_value = task
        task_svc_cls.return_value = task_svc
        token_svc_cls.return_value.create_token = AsyncMock(
            return_value={"event_url": "/api/v1/hermes/tasks/task-1/events?token=sse_test"}
        )

        result = await RuntimeSkillRunService(db).start(request)

    content = result.structured_content
    assert content["entrypoint"] == "expert_mcp_gateway"
    assert content["task_source"] == "expert_mcp"
    assert content["catalog_kind"] == "expert"
    assert content["catalog_slug"] == "call-prep"
    assert content["skill_name"] == "customer-profiling"
    assert content["invocation_id"] == "log-1"
