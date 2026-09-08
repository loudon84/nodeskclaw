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
        "_build_authorized_execution_context",
        new=AsyncMock(return_value={"context_version": 42, "descriptors": [{"type": "knowledge", "stable_id": "kb://doc-1", "auth_version": "abc", "expires_at": None}]}),
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
    assert payload["execution_context"]["context_version"] == 42
    assert payload["context_version"] == 42
    assert payload["execution_context"]["descriptors"][0]["stable_id"] == "kb://doc-1"
    assert "credential_lease" not in payload["route_snapshot"]
    assert "token" not in str(payload["route_snapshot"].get("credential_lease_ref") or {})
    assert payload["request_trace_id"].startswith("req_")


@pytest.mark.asyncio
async def test_start_strips_invalid_trace_before_enqueue():
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
        "_build_authorized_execution_context",
        new=AsyncMock(return_value={"context_version": 42, "descriptors": []}),
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

        invalid_trace = "x" * 80
        await RuntimeSkillRunService(db).start(_request(request_trace_id=invalid_trace))

    added_outbox = db.add.call_args[0][0]
    payload = added_outbox.payload
    assert payload["request_trace_id"].startswith("req_")
    assert len(payload["request_trace_id"]) <= 64


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
    task.arguments = {"prompt": "hi"}

    with patch("app.services.hermes_skill.runtime_skill_run_service.settings") as mock_settings, \
         patch("app.services.hermes_skill.runtime_skill_run_service.TaskService") as task_cls, \
         patch("app.services.hermes_skill.runtime_skill_run_service.TaskEventTokenService") as token_cls, \
         patch.object(RuntimeSkillRunService, "_resolve_release_meta", new=AsyncMock(return_value=_release_meta())), \
         patch.object(RuntimeSkillRunService, "_build_authorized_execution_context", new=AsyncMock(return_value={"context_version": 42, "descriptors": []})), \
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
        "_build_authorized_execution_context",
        new=AsyncMock(return_value={"context_version": 42, "descriptors": []}),
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


@pytest.mark.asyncio
async def test_idempotency_conflict_raises_conflict_error_not_cannot_enqueue():
    from app.core.exceptions import ConflictError

    db = AsyncMock()
    existing = MagicMock()
    existing.id = "run-existing"
    existing.arguments = {"prompt": "original"}
    existing.status = MagicMock(value="queued")
    existing.event_url = "/api/v1/runs/run-existing/events"
    existing.artifact_url = "/api/v1/runs/run-existing/artifacts"
    existing.server_artifacts = []
    existing.output_policy = {}

    with patch("app.services.hermes_skill.runtime_skill_run_service.settings") as mock_settings, \
         patch("app.services.hermes_skill.runtime_skill_run_service.TaskService") as task_cls:
        mock_settings.SKILL_AGENT_ENABLED = True
        task_svc = AsyncMock()
        task_svc.find_idempotent_task = AsyncMock(return_value=existing)
        task_cls.return_value = task_svc

        with pytest.raises(ConflictError) as exc_info:
            await RuntimeSkillRunService(db).start(
                _request(idempotency_key="same-key", arguments={"prompt": "different"})
            )

    assert exc_info.value.message_key == "errors.run.idempotency_conflict"
    task_svc.create_task.assert_not_awaited()


@pytest.mark.asyncio
async def test_idempotency_integrity_error_replays_same_args():
    from sqlalchemy.exc import IntegrityError

    db = AsyncMock()
    db.rollback = AsyncMock()
    existing = MagicMock()
    existing.id = "run-winner"
    existing.arguments = {"prompt": "hi"}
    existing.status = MagicMock(value="queued")
    existing.event_url = "/api/v1/runs/run-winner/events"
    existing.artifact_url = "/api/v1/runs/run-winner/artifacts"
    existing.server_artifacts = []
    existing.output_policy = {}
    existing.task_no = "TASK-1"

    with patch("app.services.hermes_skill.runtime_skill_run_service.settings") as mock_settings, \
         patch("app.services.hermes_skill.runtime_skill_run_service.TaskService") as task_cls, \
         patch("app.services.hermes_skill.runtime_skill_run_service.TaskEventTokenService") as token_cls, \
         patch.object(RuntimeSkillRunService, "_resolve_release_meta", new=AsyncMock(return_value=_release_meta())), \
         patch.object(RuntimeSkillRunService, "_build_authorized_execution_context", new=AsyncMock(return_value={"context_version": 1, "descriptors": []})), \
         patch.object(RuntimeSkillRunService, "_enrich_route_snapshot", new=AsyncMock(side_effect=lambda request, route: dict(route))):
        mock_settings.SKILL_AGENT_ENABLED = True
        mock_settings.HERMES_TASK_DEFAULT_TIMEOUT_SECONDS = 900
        mock_settings.MCP_TASK_SSE_TOKEN_TTL_SECONDS = 900
        mock_settings.EXPERT_EVENT_TOKEN_TTL_SECONDS = 900

        task_svc = AsyncMock()
        task_svc.find_idempotent_task = AsyncMock(side_effect=[None, existing])
        task_svc.create_task = AsyncMock(side_effect=IntegrityError("INSERT", {}, Exception("uq")))
        task_cls.return_value = task_svc
        token_cls.return_value.create_token = AsyncMock(return_value={"event_url": existing.event_url})

        result = await RuntimeSkillRunService(db).start(_request(idempotency_key="race-key"))

    assert result.task.id == "run-winner"
    db.rollback.assert_awaited()
    assert task_svc.find_idempotent_task.await_count == 2
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_idempotency_integrity_error_conflict_not_cannot_enqueue():
    from app.core.exceptions import ConflictError
    from sqlalchemy.exc import IntegrityError

    db = AsyncMock()
    db.rollback = AsyncMock()
    existing = MagicMock()
    existing.id = "run-winner"
    existing.arguments = {"prompt": "original"}

    with patch("app.services.hermes_skill.runtime_skill_run_service.settings") as mock_settings, \
         patch("app.services.hermes_skill.runtime_skill_run_service.TaskService") as task_cls, \
         patch.object(RuntimeSkillRunService, "_resolve_release_meta", new=AsyncMock(return_value=_release_meta())), \
         patch.object(RuntimeSkillRunService, "_build_authorized_execution_context", new=AsyncMock(return_value={"context_version": 1, "descriptors": []})):
        mock_settings.SKILL_AGENT_ENABLED = True
        task_svc = AsyncMock()
        task_svc.find_idempotent_task = AsyncMock(side_effect=[None, existing])
        task_svc.create_task = AsyncMock(side_effect=IntegrityError("INSERT", {}, Exception("uq")))
        task_cls.return_value = task_svc

        with pytest.raises(ConflictError) as exc_info:
            await RuntimeSkillRunService(db).start(
                _request(idempotency_key="race-key", arguments={"prompt": "other"})
            )

    assert exc_info.value.message_key == "errors.run.idempotency_conflict"
    db.rollback.assert_awaited()


@pytest.mark.asyncio
async def test_find_idempotent_task_expires_key_after_ttl_without_soft_delete():
    from datetime import datetime, timedelta, timezone

    from app.services.hermes_skill.task_service import IDEMPOTENCY_TTL_SECONDS, TaskService

    db = AsyncMock()
    db.flush = AsyncMock()
    expired = MagicMock()
    expired.idempotency_key = "old-key"
    expired.created_at = datetime.now(timezone.utc) - timedelta(seconds=IDEMPOTENCY_TTL_SECONDS + 1)
    expired.deleted_at = None
    result = MagicMock()
    result.scalar_one_or_none.return_value = expired
    db.execute = AsyncMock(return_value=result)

    found = await TaskService(db).find_idempotent_task("org-1", "user-1", "tool.a", "old-key")

    assert found is None
    assert expired.idempotency_key is None
    assert expired.deleted_at is None
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_find_idempotent_task_replays_within_ttl():
    from datetime import datetime, timedelta, timezone

    from app.services.hermes_skill.task_service import TaskService

    db = AsyncMock()
    live = MagicMock()
    live.idempotency_key = "live-key"
    live.created_at = datetime.now(timezone.utc) - timedelta(hours=1)
    result = MagicMock()
    result.scalar_one_or_none.return_value = live
    db.execute = AsyncMock(return_value=result)

    found = await TaskService(db).find_idempotent_task("org-1", "user-1", "tool.a", "live-key")

    assert found is live
    assert live.idempotency_key == "live-key"

# --- RM-10 projection observability (T4) ---
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI, Header, HTTPException
from httpx import ASGITransport

from app.models.hermes_skill.hermes_task import HermesTask, TaskStatus
from app.services.hermes_skill.run_projection_updater_service import (
    RunProjectionUpdaterService,
    _inc_projection_sync_failed,
    get_projection_metrics_snapshot,
    reset_projection_metrics,
)


@pytest.fixture(autouse=True)
def _clear_projection_metrics():
    reset_projection_metrics()
    yield
    reset_projection_metrics()


def _db_missing_task():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result)
    return db


def _db_with_task(task: HermesTask):
    db = AsyncMock()
    call_count = {"n": 0}

    async def _execute_side_effect(stmt, *a, **kw):
        call_count["n"] += 1
        res = MagicMock()
        if call_count["n"] == 1:
            res.scalar_one_or_none.return_value = task
            return res
        res.scalar_one_or_none.return_value = 0
        return res

    db.execute.side_effect = _execute_side_effect
    return db


@pytest.mark.asyncio
async def test_projection_fail_counter_task_not_found():
    service = RunProjectionUpdaterService(_db_missing_task())
    ok = await service.sync_task_projection("missing-task", "org-1", "user-1")
    assert ok is False
    snap = get_projection_metrics_snapshot()
    assert snap["projection_sync_failed_total"]["task_not_found"] == 1


@pytest.mark.asyncio
async def test_projection_fail_counter_agent_run_not_found(monkeypatch):
    task = HermesTask(
        id="task-404",
        org_id="org-1",
        user_id="user-1",
        status=TaskStatus.RUNNING,
        projection_cursor=0,
    )
    service = RunProjectionUpdaterService(_db_with_task(task))

    mock_agent_app = FastAPI()

    @mock_agent_app.get("/internal/v1/runs/{run_id}")
    async def get_run_route(run_id: str, x_exec_org_id: str = Header(alias="X-Exec-Org-Id")):
        raise HTTPException(status_code=404, detail="not found")

    real_transport = ASGITransport(app=mock_agent_app)
    orig_async_client = httpx.AsyncClient

    def _custom_client(*args, **kwargs):
        kwargs["transport"] = real_transport
        kwargs["base_url"] = "http://testserver"
        return orig_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _custom_client)

    ok = await service.sync_task_projection("task-404", "org-1", "user-1")
    assert ok is False
    snap = get_projection_metrics_snapshot()
    assert snap["projection_sync_failed_total"]["agent_run_not_found"] == 1
    assert "http_error" not in snap["projection_sync_failed_total"]


@pytest.mark.asyncio
async def test_projection_fail_counter_http_error(monkeypatch):
    task = HermesTask(
        id="task-500",
        org_id="org-1",
        user_id="user-1",
        status=TaskStatus.RUNNING,
        projection_cursor=0,
    )
    service = RunProjectionUpdaterService(_db_with_task(task))

    mock_agent_app = FastAPI()

    @mock_agent_app.get("/internal/v1/runs/{run_id}")
    async def get_run_route(run_id: str, x_exec_org_id: str = Header(alias="X-Exec-Org-Id")):
        raise HTTPException(status_code=500, detail="boom")

    real_transport = ASGITransport(app=mock_agent_app)
    orig_async_client = httpx.AsyncClient

    def _custom_client(*args, **kwargs):
        kwargs["transport"] = real_transport
        kwargs["base_url"] = "http://testserver"
        return orig_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _custom_client)

    ok = await service.sync_task_projection("task-500", "org-1", "user-1")
    assert ok is False
    snap = get_projection_metrics_snapshot()
    assert snap["projection_sync_failed_total"]["http_error"] == 1
    assert "exception" not in snap["projection_sync_failed_total"]


@pytest.mark.asyncio
async def test_projection_fail_counter_exception(monkeypatch):
    task = HermesTask(
        id="task-exc",
        org_id="org-1",
        user_id="user-1",
        status=TaskStatus.RUNNING,
        projection_cursor=0,
    )
    service = RunProjectionUpdaterService(_db_with_task(task))

    class _BoomClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            raise RuntimeError("transport broken")

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(httpx, "AsyncClient", _BoomClient)

    ok = await service.sync_task_projection("task-exc", "org-1", "user-1")
    assert ok is False
    snap = get_projection_metrics_snapshot()
    assert snap["projection_sync_failed_total"]["exception"] == 1


@pytest.mark.asyncio
async def test_projection_metrics_fail_open_does_not_break_sync(monkeypatch):
    """Broken counter storage must not change sync outcome or raise."""

    class _BrokenDict(dict):
        def __setitem__(self, key, value):
            raise RuntimeError("counter store broken")

        def get(self, key, default=None):
            raise RuntimeError("counter store broken")

    monkeypatch.setattr(
        "app.services.hermes_skill.run_projection_updater_service._projection_sync_failed_total",
        _BrokenDict(),
    )
    _inc_projection_sync_failed("task_not_found")
    service = RunProjectionUpdaterService(_db_missing_task())
    ok = await service.sync_task_projection("missing-task", "org-1", "user-1")
    assert ok is False
    assert get_projection_metrics_snapshot() == {"projection_sync_failed_total": {}}


def test_projection_unknown_reason_maps_to_exception():
    _inc_projection_sync_failed("not_a_real_reason")
    snap = get_projection_metrics_snapshot()
    assert snap["projection_sync_failed_total"]["exception"] == 1
    assert "not_a_real_reason" not in snap["projection_sync_failed_total"]
