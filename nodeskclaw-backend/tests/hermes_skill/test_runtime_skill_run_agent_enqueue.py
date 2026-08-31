import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.hermes_skill.runtime_skill_run_service import RuntimeSkillRunService
from app.schemas.hermes_skill.runtime_skill_run import StartRuntimeSkillRunRequest


def _request(**kwargs):
    base = dict(
        org_id="org-1",
        user_id="user-1",
        tool_name="writer_article_generate",
        runtime_skill_id="writer",
        agent_profile="writer",
        hermes_agent_instance_id="inst-1",
        agent_id="agent-1",
        arguments={"prompt": "hi"},
        client_context={},
        output_policy={"artifact_mode": "pull_only"},
        task_source="org_mcp",
        skill_id="skill-1",
        entrypoint="mcp_skill_gateway",
    )
    base.update(kwargs)
    return StartRuntimeSkillRunRequest(**base)


def _release_meta():
    return {
        "skill_release_id": "rel-1",
        "skill_version": "1.0.0",
        "skill_release_digest": "digest-abc",
        "snapshot_hash": "hash-abc",
        "connector_binding_refs": ["binding-1", "binding-2"],
        "knowledge_refs": ["kb://doc-1"],
        "placement": {"role": "central", "engine": "hermes"},
    }


@pytest.mark.asyncio
async def test_start_delegates_to_skill_agent_and_returns_run_id():
    db = AsyncMock()
    db.add = MagicMock()
    task = MagicMock()
    task.id = "run-abc"
    task.task_no = "TASK-0001"
    task.status = MagicMock(value="queued")
    task.event_url = "/api/v1/hermes/tasks/run-abc/events"
    task.artifact_url = "/api/v1/hermes/tasks/run-abc/artifacts"
    task.server_artifacts = []
    task.output_policy = {}

    with patch(
        "app.services.hermes_skill.runtime_skill_run_service.settings"
    ) as mock_settings, patch(
        "app.services.hermes_skill.runtime_skill_run_service.TaskService"
    ) as task_cls, patch(
        "app.services.hermes_skill.runtime_skill_run_service.TaskEventTokenService"
    ) as token_cls, patch.object(
        RuntimeSkillRunService,
        "_resolve_release_meta",
        new=AsyncMock(return_value=_release_meta()),
    ), patch.object(
        RuntimeSkillRunService,
        "_enrich_route_snapshot",
        new=AsyncMock(side_effect=lambda request, route: {**route, "gateway_url": "http://gw"}),
    ):
        mock_settings.SKILL_AGENT_ENABLED = True
        mock_settings.HERMES_TASK_DEFAULT_TIMEOUT_SECONDS = 900
        mock_settings.MCP_TASK_SSE_TOKEN_TTL_SECONDS = 900
        mock_settings.EXPERT_EVENT_TOKEN_TTL_SECONDS = 900

        task_svc = AsyncMock()
        task_svc.find_idempotent_task = AsyncMock(return_value=None)
        task_svc.create_task = AsyncMock(return_value=task)
        task_cls.return_value = task_svc

        token_svc = AsyncMock()
        token_svc.create_token = AsyncMock(
            return_value={"event_url": "/api/v1/hermes/tasks/run-abc/events?token=abc"}
        )
        token_cls.return_value = token_svc

        result = await RuntimeSkillRunService(db).start(_request())

    assert result.structured_content["run_id"] == "run-abc"
    assert "task_id" not in result.structured_content
    assert result.structured_content["result_url"] == "/api/v1/runs/run-abc/result"
    task_svc.create_task.assert_awaited()
    assert task_svc.create_task.await_args.kwargs["routing_metadata"]["execution_owner"] == "agent"
    db.add.assert_called_once()
    added_outbox = db.add.call_args[0][0]
    assert added_outbox.run_id == task.id
    assert added_outbox.tool_name == "writer_article_generate"
    assert added_outbox.status == "pending"
    payload = added_outbox.payload
    assert payload["skill_release_digest"] == "digest-abc"
    assert payload["skill_version"] == "1.0.0"
    assert payload["connector_binding_refs"] == ["binding-1", "binding-2"]
    assert payload["knowledge_refs"] == ["kb://doc-1"]
    assert payload["placement"] == {"role": "central", "engine": "hermes"}
    assert payload["route_snapshot"]["gateway_url"] == "http://gw"
    assert "credential_lease" not in payload["route_snapshot"]
    assert "token" not in str(payload["route_snapshot"].get("credential_lease_ref") or {})


@pytest.mark.asyncio
async def test_same_idempotency_key_from_two_clients_creates_one_run():
    db = AsyncMock()
    db.add = MagicMock()
    task = MagicMock()
    task.id = "run-abc"
    task.task_no = "TASK-0001"
    task.status = MagicMock(value="queued")
    task.event_url = "/api/v1/runs/run-abc/events"
    task.artifact_url = "/api/v1/runs/run-abc/artifacts"
    task.server_artifacts = []
    task.output_policy = {}

    with patch("app.services.hermes_skill.runtime_skill_run_service.settings") as mock_settings, \
         patch("app.services.hermes_skill.runtime_skill_run_service.TaskService") as task_cls, \
         patch("app.services.hermes_skill.runtime_skill_run_service.TaskEventTokenService") as token_cls, \
         patch.object(RuntimeSkillRunService, "_resolve_release_meta", new=AsyncMock(return_value=_release_meta())), \
         patch.object(RuntimeSkillRunService, "_enrich_route_snapshot", new=AsyncMock(side_effect=lambda request, route: dict(route))):
        mock_settings.SKILL_AGENT_ENABLED = True
        mock_settings.HERMES_TASK_DEFAULT_TIMEOUT_SECONDS = 900
        mock_settings.MCP_TASK_SSE_TOKEN_TTL_SECONDS = 900
        mock_settings.EXPERT_EVENT_TOKEN_TTL_SECONDS = 900

        task_svc = AsyncMock()
        task_svc.find_idempotent_task = AsyncMock(side_effect=[None, task])
        task_svc.create_task = AsyncMock(return_value=task)
        task_cls.return_value = task_svc
        token_cls.return_value.create_token = AsyncMock(return_value={"event_url": task.event_url})

        service = RuntimeSkillRunService(db)
        first = await service.start(_request(idempotency_key="cross-client-key", client_context={"client": "work"}))
        replay = await service.start(_request(idempotency_key="cross-client-key", client_context={"client": "portal"}))

    assert first.task.id == replay.task.id == "run-abc"
    task_svc.create_task.assert_awaited_once()
    assert db.add.call_count == 1


@pytest.mark.asyncio
async def test_expert_start_keeps_task_id_contract():
    db = AsyncMock()
    db.add = MagicMock()
    task = MagicMock()
    task.id = "run-abc"
    task.task_no = "TASK-0001"
    task.status = MagicMock(value="queued")
    task.event_url = "/api/v1/hermes/tasks/run-abc/events"
    task.artifact_url = "/api/v1/hermes/tasks/run-abc/artifacts"
    task.server_artifacts = []
    task.output_policy = {}

    with patch(
        "app.services.hermes_skill.runtime_skill_run_service.settings"
    ) as mock_settings, patch(
        "app.services.hermes_skill.runtime_skill_run_service.TaskService"
    ) as task_cls, patch(
        "app.services.hermes_skill.runtime_skill_run_service.TaskEventTokenService"
    ) as token_cls, patch.object(
        RuntimeSkillRunService,
        "_resolve_release_meta",
        new=AsyncMock(return_value=_release_meta()),
    ), patch.object(
        RuntimeSkillRunService,
        "_enrich_route_snapshot",
        new=AsyncMock(side_effect=lambda request, route: dict(route)),
    ):
        mock_settings.SKILL_AGENT_ENABLED = True
        mock_settings.HERMES_TASK_DEFAULT_TIMEOUT_SECONDS = 900
        mock_settings.MCP_TASK_SSE_TOKEN_TTL_SECONDS = 900
        mock_settings.EXPERT_EVENT_TOKEN_TTL_SECONDS = 900

        task_svc = AsyncMock()
        task_svc.find_idempotent_task = AsyncMock(return_value=None)
        task_svc.create_task = AsyncMock(return_value=task)
        task_cls.return_value = task_svc

        token_svc = AsyncMock()
        token_svc.create_token = AsyncMock(
            return_value={"event_url": "/api/v1/hermes/tasks/run-abc/events?token=abc"}
        )
        token_cls.return_value = token_svc

        result = await RuntimeSkillRunService(db).start(
            _request(task_source="expert_mcp", entrypoint="expert_mcp_gateway")
        )

    assert result.structured_content["task_id"] == "run-abc"
    assert "/api/v1/hermes/tasks/run-abc/result" in result.structured_content["result_url"]
    db.add.assert_called_once()
