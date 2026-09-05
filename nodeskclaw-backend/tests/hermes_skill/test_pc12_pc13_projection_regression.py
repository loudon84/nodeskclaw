from datetime import datetime, timezone
from json import loads
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.runs import get_run, get_run_artifacts, get_run_result, stream_run_events
from app.models.hermes_skill.hermes_task import HermesTask, TaskStatus
from tests.hermes_skill.test_employee_jwt_public_conformance import (
    EMPLOYEE_AUTH_TYPE,
    _auth_ctx,
    _call_runtime_tool,
    _mock_user_org,
    _scan_public_surface,
)


@pytest.mark.asyncio
async def test_pc12_projection_regression():
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
    dumped = str(run_view) + str(result_view) + str(artifacts_view)
    assert "runtime_run_id" not in dumped
    assert "runtime_session_id" not in dumped
    assert _auth_ctx(EMPLOYEE_AUTH_TYPE).auth_type == EMPLOYEE_AUTH_TYPE


@pytest.mark.asyncio
async def test_pc12_waiting_approval_event_hides_runtime_identity():
    db = AsyncMock()
    user_org = _mock_user_org()
    request = MagicMock()
    request.is_disconnected = AsyncMock(return_value=False)
    task = HermesTask(
        id="run-wait",
        org_id="org-1",
        user_id="user-1",
        tool_name="writer_tool",
        status=TaskStatus.RUNNING,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    status_calls = {"n": 0}

    async def _agent_get_side_effect(path, params=None, org_id=None, user_id=None):
        if path.endswith("/events"):
            return {
                "items": [{
                    "event_type": "approval.requested",
                    "event_seq": 4,
                    "timestamp": "2026-09-05T00:00:04Z",
                    "payload": {
                        "approval_id": "appr-live",
                        "summary": "delete file",
                        "runtime_run_id": "rr-secret",
                        "choice": "session",
                    },
                }]
            }
        status_calls["n"] += 1
        status = "WAITING_APPROVAL" if status_calls["n"] == 1 else "CANCELLED"
        return {
            "run_id": "run-wait",
            "org_id": "org-1",
            "tool_name": "writer_tool",
            "status": status,
            "runtime_run_id": "rr-secret",
            "created_at": "2026-09-05T00:00:00Z",
            "updated_at": "2026-09-05T00:00:09Z",
        }

    with patch("app.api.runs._authorize_run", new=AsyncMock(return_value=task)), \
         patch("app.api.runs._get_outbox_entry", new=AsyncMock(return_value=None)), \
         patch("app.api.runs.pg_notify_service.subscribe"), \
         patch("app.api.runs.pg_notify_service.unsubscribe"), \
         patch("app.api.runs._agent_get", new=AsyncMock(side_effect=_agent_get_side_effect)):
        run_view = await get_run(run_id="run-wait", user_org=user_org, db=db)
        response = await stream_run_events(
            run_id="run-wait",
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
    _scan_public_surface(run_view)
    assert run_view["status"] == "WAITING_APPROVAL"
    assert "runtime_run_id" not in str(run_view)
    assert "event: approval.requested\n" in body
    assert "rr-secret" not in body
    assert "runtime_run_id" not in body
    frame = loads(body.split("data: ", 1)[1].split("\n\n", 1)[0])
    _scan_public_surface(frame)
    assert frame["payload"] == {"approval_id": "appr-live", "summary": "delete file"}


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
async def test_pc13_projection_regression(agent_status, event_type):
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
    _scan_public_surface(loads(body.split("data: ", 1)[1].split("\n\n", 1)[0]))
    assert _auth_ctx(EMPLOYEE_AUTH_TYPE).auth_type == EMPLOYEE_AUTH_TYPE
