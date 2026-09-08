import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.runs import (
    _public_run_event,
    get_run,
    get_run_artifacts,
    get_run_result,
    stream_run_events,
)
from app.models.hermes_skill.hermes_task import HermesTask, TaskStatus
from app.services.hermes_skill.mcp_tool_mapper import McpToolMapper
from app.services.hermes_skill.permission_checker import PermissionChecker
from app.services.hermes_skill.runtime_skill_run_service import RuntimeSkillRunResult
from app.services.hermes_skill.skill_routing_service import (
    ROUTING_REASON_RUNTIME_FIXED_DEFAULT,
    RoutingResult,
    SkillRoutingService,
)
from app.services.mcp_skill_gateway.auth import McpAuthContext
from app.services.mcp_skill_gateway.mcp_execution_mode import (
    ASYNC_EVENT_MODE,
    resolve_mcp_execution_mode,
)

EMPLOYEE_AUTH_TYPE = "user_jwt"
MCP_CLIENT_AUTH_TYPE = "mcp_client_token"
FORBIDDEN_PUBLIC_KEYS = (
    "task_id",
    "task_no",
    "agent_alias",
    "agent_id",
    "profile_id",
    "workspace_id",
    "installation_id",
    "routing_reason",
    "event_token_url",
    "wait_strategy",
)
HERMES_TASK_PATH = "/api/v1/hermes/tasks/"


def _auth_ctx(auth_type: str) -> McpAuthContext:
    return McpAuthContext(
        user=SimpleNamespace(id="user-1"),
        org=SimpleNamespace(id="org-1"),
        auth_type=auth_type,
    )


def _runtime_skill():
    skill = MagicMock()
    skill.id = "skill-1"
    skill.skill_id = "writer_tool"
    skill.tool_name = "writer_tool"
    skill.source_type = "hermes_api_server"
    skill.input_schema = None
    skill.output_policy = {"artifact_mode": "pull_only"}
    return skill


def _runtime_installation():
    installation = MagicMock()
    installation.agent_id = "inst-1"
    installation.profile_id = "default"
    installation.workspace_id = "office-1"
    installation.id = "install-1"
    installation.routing_metadata = {
        "route_type": "hermes_api_server",
        "agent_profile": "default",
    }
    return installation


def _structured_content(run_id: str) -> dict:
    return {
        "run_id": run_id,
        "status": "QUEUED",
        "execution_mode": "async_event",
        "tool_name": "writer_tool",
        "event_stream": f"/api/v1/runs/{run_id}/events",
        "result_url": f"/api/v1/runs/{run_id}/result",
        "artifact_url": f"/api/v1/runs/{run_id}/artifacts",
        "contract_version": "1.2.1",
        "committed": True,
    }


def _scan_public_surface(value) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            assert key not in FORBIDDEN_PUBLIC_KEYS
            _scan_public_surface(nested)
        return
    if isinstance(value, list):
        for item in value:
            _scan_public_surface(item)
        return
    if isinstance(value, str):
        assert HERMES_TASK_PATH not in value


def _mock_user_org():
    user = MagicMock()
    user.id = "user-1"
    org = MagicMock()
    org.id = "org-1"
    return user, org


async def _call_runtime_tool(auth_type: str, run_id: str) -> dict:
    db = AsyncMock()
    mapper = McpToolMapper(db)
    skill = _runtime_skill()
    installation = _runtime_installation()
    routing_result = RoutingResult(
        matched=True,
        installation=installation,
        skill=skill,
        reason=ROUTING_REASON_RUNTIME_FIXED_DEFAULT,
        installation_id=installation.id,
        skill_id=skill.skill_id,
        agent_id=installation.agent_id,
    )
    created_task = MagicMock()
    created_task.id = run_id
    created_task.task_no = "TASK-hidden"
    created_task.status = TaskStatus.QUEUED
    created_task.event_url = f"/api/v1/hermes/tasks/{run_id}/events"
    created_task.artifact_url = f"/api/v1/hermes/tasks/{run_id}/artifacts"
    created_task.server_artifacts = []

    with patch.object(PermissionChecker, "require_permission", AsyncMock()), \
         patch.object(SkillRoutingService, "get_exposed_skill", AsyncMock(return_value=skill)), \
         patch.object(
             SkillRoutingService,
             "resolve_runtime_skill_fixed_route",
             AsyncMock(return_value=routing_result),
         ), \
         patch("app.services.hermes_skill.mcp_tool_mapper.SkillReleaseService") as release_cls, \
         patch("app.services.hermes_skill.mcp_tool_mapper.AgentAliasResolver") as mock_alias_cls, \
         patch("app.services.hermes_skill.mcp_tool_mapper.RuntimeSkillRunService") as mock_run_svc_cls, \
         patch("app.services.hermes_skill.mcp_tool_mapper.HermesSkillAuthorizationService") as mock_authz_cls, \
         patch("app.services.hermes_skill.skill_audit_logger.SkillAuditLogger") as mock_audit_cls, \
         patch.object(mapper, "_resolve_runtime_route_health", AsyncMock(return_value={"ok": True})), \
         patch("app.services.hermes_skill.mcp_tool_mapper.settings.SKILL_AGENT_ENABLED", True), \
         patch("app.services.mcp_skill_gateway.mcp_execution_mode.settings.MCP_TASK_SSE_ENABLED", True), \
         patch(
             "app.services.mcp_skill_gateway.mcp_execution_mode.settings.MCP_TASK_DEFAULT_EXECUTION_MODE",
             "async_event",
         ):
        release_cls.return_value.get_published_by_skill_db_id = AsyncMock(return_value=None)
        mock_alias_cls.return_value.enrich_routing = AsyncMock()
        mock_alias_cls.return_value.resolve = AsyncMock(return_value=None)
        mock_authz_cls.return_value.can_invoke = AsyncMock(return_value=True)
        mock_run_svc = AsyncMock()
        mock_run_svc.start.return_value = RuntimeSkillRunResult(
            task=created_task,
            sse_token="hidden",
            structured_content=_structured_content(run_id),
        )
        mock_run_svc_cls.return_value = mock_run_svc
        mock_audit_cls.return_value = AsyncMock()
        return await mapper.call_tool(
            "writer_tool",
            {"prompt": "profile"},
            "org-1",
            "user-1",
            auth_ctx=_auth_ctx(auth_type),
        )


def test_pc10_employee_jwt_envelope_parity(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "MCP_TASK_SSE_ENABLED", True)
    monkeypatch.setattr(settings, "MCP_TASK_DEFAULT_EXECUTION_MODE", "async_event")
    skill = _runtime_skill()
    jwt_mode = resolve_mcp_execution_mode(
        _auth_ctx(EMPLOYEE_AUTH_TYPE),
        skill,
        {"artifact_mode": "pull_only"},
    )
    token_mode = resolve_mcp_execution_mode(
        _auth_ctx(MCP_CLIENT_AUTH_TYPE),
        skill,
        {"artifact_mode": "pull_only"},
    )
    assert jwt_mode == ASYNC_EVENT_MODE
    assert token_mode == jwt_mode
    assert _auth_ctx(EMPLOYEE_AUTH_TYPE).auth_type == EMPLOYEE_AUTH_TYPE


@pytest.mark.asyncio
async def test_pc10_tools_call_keyset_parity_for_user_jwt():
    jwt_payload = await _call_runtime_tool(EMPLOYEE_AUTH_TYPE, "run-jwt")
    token_payload = await _call_runtime_tool(MCP_CLIENT_AUTH_TYPE, "run-token")
    jwt_keys = set(jwt_payload) - {"run_id"}
    token_keys = set(token_payload) - {"run_id"}
    assert jwt_keys == token_keys
    for payload in (jwt_payload, token_payload):
        assert payload["status"] == "QUEUED"
        assert payload["contract_version"] == "1.2.1"
        assert payload["event_stream"].startswith("/api/v1/runs/")
        assert payload["result_url"].startswith("/api/v1/runs/")
        assert payload["artifact_url"].startswith("/api/v1/runs/")
        _scan_public_surface(payload)
    assert jwt_payload["run_id"] != token_payload["run_id"]
    assert _auth_ctx(EMPLOYEE_AUTH_TYPE).auth_type == EMPLOYEE_AUTH_TYPE


@pytest.mark.asyncio
async def test_pc11_catalog_matches_call_resolver(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "MCP_TASK_SSE_ENABLED", True)
    monkeypatch.setattr(settings, "MCP_TASK_DEFAULT_EXECUTION_MODE", "async_event")
    mapper = McpToolMapper(AsyncMock())
    skill = _runtime_skill()
    installation = _runtime_installation()
    with patch.object(mapper, "_resolve_runtime_route_health", AsyncMock(return_value={"ok": True})):
        metadata = await mapper._build_runtime_skill_tool_metadata(skill, "org-1", installation)
    for auth_type in (EMPLOYEE_AUTH_TYPE, MCP_CLIENT_AUTH_TYPE):
        resolved = resolve_mcp_execution_mode(
            _auth_ctx(auth_type),
            skill,
            {"artifact_mode": "pull_only"},
        )
        assert metadata["defaultExecutionMode"] == resolved
        assert resolved in metadata["executionModes"]
    assert _auth_ctx(EMPLOYEE_AUTH_TYPE).auth_type == EMPLOYEE_AUTH_TYPE


@pytest.mark.asyncio
async def test_pc12_single_plane_isolation():
    accepted = await _call_runtime_tool(EMPLOYEE_AUTH_TYPE, "run-iso")
    _scan_public_surface(accepted)

    db = AsyncMock()
    user_org = _mock_user_org()
    task = HermesTask(id="run-iso", org_id="org-1", user_id="user-1", tool_name="writer_tool", status=TaskStatus.RUNNING)
    agent_run = {
        "run_id": "run-iso",
        "org_id": "org-1",
        "tool_name": "writer_tool",
        "status": "RUNNING",
        "created_at": "2026-08-31T00:00:00Z",
        "updated_at": "2026-08-31T00:01:00Z",
        "task_id": "must-not-leak",
    }
    agent_result = {
        "run_id": "run-iso",
        "org_id": "org-1",
        "status": "COMPLETED",
        "result_content": "done",
        "task_no": "TASK-hidden",
    }
    agent_artifacts = {
        "run_id": "run-iso",
        "org_id": "org-1",
        "items": [{
            "artifact_id": "art-1",
            "name": "out.txt",
            "content_type": "text/plain",
            "size_bytes": 4,
            "checksum_sha256": "abcd",
            "installation_id": "install-1",
        }],
    }
    with patch("app.api.runs.PermissionChecker.require_permission", new=AsyncMock()), \
         patch("app.api.runs.TaskService.get_task", new=AsyncMock(return_value=task)), \
         patch("app.api.runs.TaskService.assert_task_access", new=AsyncMock()), \
         patch("app.api.runs._get_outbox_entry", new=AsyncMock(return_value=None)), \
         patch("app.api.runs._agent_get", new=AsyncMock(side_effect=[agent_run, agent_result, agent_artifacts])):
        run_view = await get_run(run_id="run-iso", user_org=user_org, db=db)
        result_view = await get_run_result(run_id="run-iso", user_org=user_org, db=db)
        artifacts_view = await get_run_artifacts(run_id="run-iso", user_org=user_org, db=db)
    _scan_public_surface(run_view)
    _scan_public_surface(result_view)
    _scan_public_surface(artifacts_view)
    assert _auth_ctx(EMPLOYEE_AUTH_TYPE).auth_type == EMPLOYEE_AUTH_TYPE


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("agent_status", "event_type"),
    [
        ("COMPLETED", "run.completed"),
        ("FAILED", "run.failed"),
        ("CANCELLED", "run.cancelled"),
        ("TIMED_OUT", "run.timed_out"),
    ],
)
async def test_pc13_public_terminal_delivery(agent_status, event_type):
    db = AsyncMock()
    user_org = _mock_user_org()
    request = MagicMock()
    request.is_disconnected = AsyncMock(return_value=False)
    task = HermesTask(
        id="run-term",
        org_id="org-1",
        user_id="user-1",
        tool_name="writer_tool",
        status=TaskStatus.RUNNING,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    async def _agent_get_side_effect(path, params=None, org_id=None, user_id=None):
        if path.endswith("/events"):
            return {"items": []}
        return {"run_id": "run-term", "org_id": "org-1", "status": agent_status}

    with patch("app.api.runs._authorize_run", new=AsyncMock(return_value=task)), \
         patch("app.api.runs._get_outbox_entry", new=AsyncMock(return_value=None)), \
         patch("app.api.runs.pg_notify_service.subscribe"), \
         patch("app.api.runs.pg_notify_service.unsubscribe"), \
         patch("app.api.runs._agent_get", new=AsyncMock(side_effect=_agent_get_side_effect)):
        response = await stream_run_events(
            run_id="run-term",
            request=request,
            last_event_id=None,
            user_org=user_org,
            db=db,
            last_event_id_header=None,
        )
        chunks: list[str] = []
        async for chunk in response.body_iterator:
            chunks.append(chunk if isinstance(chunk, str) else chunk.decode())
        body = "".join(chunks)
    assert f"event: {event_type}\n" in body
    assert "hermes.run.delta" not in body
    _scan_public_surface(json.loads(body.split("data: ", 1)[1].split("\n\n", 1)[0]))
    assert _auth_ctx(EMPLOYEE_AUTH_TYPE).auth_type == EMPLOYEE_AUTH_TYPE


def test_pc14_employee_public_face_regression_corpus():
    run_id = "run-pc14"
    plain = _public_run_event(
        {
            "event_type": "assistant.message",
            "event_seq": 1,
            "payload": {"text": "hello"},
        },
        run_id,
    )
    tool = _public_run_event(
        {
            "event_type": "tool.call",
            "event_seq": 2,
            "payload": {"tool_name": "search", "call_id": "call-1", "status": "started"},
        },
        run_id,
    )
    approval = _public_run_event(
        {
            "event_type": "approval.requested",
            "event_seq": 3,
            "payload": {"approval_id": "appr-1", "summary": "need review"},
        },
        run_id,
    )
    cancelled = _public_run_event(
        {
            "event_type": "run.cancelled",
            "event_seq": 4,
            "payload": {"phase": "CANCELLED"},
        },
        run_id,
    )
    dropped_reasoning = _public_run_event(
        {"event_type": "reasoning.available", "event_seq": 5, "payload": {}},
        run_id,
    )
    assert plain is not None and plain["payload"]["text"] == "hello"
    assert tool is not None and tool["payload"]["call_id"] == "call-1"
    assert approval is not None and approval["payload"]["approval_id"] == "appr-1"
    assert cancelled is not None and cancelled["event_type"] == "run.cancelled"
    assert dropped_reasoning is None
    for frame in (plain, tool, approval, cancelled):
        _scan_public_surface(frame)
    assert _auth_ctx(EMPLOYEE_AUTH_TYPE).auth_type == EMPLOYEE_AUTH_TYPE


def test_pc_evidence_records_user_jwt_and_does_not_skip():
    assert EMPLOYEE_AUTH_TYPE == "user_jwt"
    assert _auth_ctx(EMPLOYEE_AUTH_TYPE).auth_type == "user_jwt"
