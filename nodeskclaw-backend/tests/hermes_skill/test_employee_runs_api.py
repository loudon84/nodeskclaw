import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
from app.api.runs import (
    _agent_post,
    approve_run,
    cancel_run,
    download_run_artifact,
    get_run,
    get_run_artifacts,
    get_run_result,
    resume_run,
    stream_run_events,
)
from app.core.exceptions import AppException, ForbiddenError, NotFoundError
from app.models.hermes_skill.hermes_task import HermesTask, TaskStatus
from app.models.hermes_skill.run_dispatch_outbox import RunDispatchOutbox, RunDispatchStatus


def _mock_user_org():
    user = MagicMock()
    user.id = "user-1"
    org = MagicMock()
    org.id = "org-1"
    return user, org


@pytest.mark.asyncio
async def test_get_run_projection_missing_fails_closed():
    db = AsyncMock()
    user_org = _mock_user_org()

    with patch("app.api.runs.PermissionChecker.require_permission", new=AsyncMock()), \
         patch("app.api.runs.TaskService.get_task", side_effect=NotFoundError("Task 不存在", "errors.task.not_found")), \
         patch("app.api.runs._agent_get", new=AsyncMock()) as mock_agent_get:
        
        with pytest.raises(NotFoundError):
            await get_run(run_id="run-nonexistent", user_org=user_org, db=db)
        
        mock_agent_get.assert_not_called()


@pytest.mark.asyncio
async def test_get_run_undelivered_outbox_returns_dispatch_pending():
    db = AsyncMock()
    user_org = _mock_user_org()

    task = HermesTask(
        id="run-1",
        org_id="org-1",
        user_id="user-1",
        tool_name="test_tool",
        status=TaskStatus.QUEUED,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    outbox = RunDispatchOutbox(
        run_id="run-1",
        dispatch_id="disp-1",
        org_id="org-1",
        user_id="user-1",
        tool_name="test_tool",
        status=RunDispatchStatus.PENDING.value,
        payload={},
        command_digest="digest",
    )

    with patch("app.api.runs.PermissionChecker.require_permission", new=AsyncMock()), \
         patch("app.api.runs.TaskService.get_task", new=AsyncMock(return_value=task)), \
         patch("app.api.runs.TaskService.assert_task_access", new=AsyncMock()), \
         patch("app.api.runs._get_outbox_entry", new=AsyncMock(return_value=outbox)), \
         patch("app.api.runs._agent_get", new=AsyncMock()) as mock_agent_get:

        res = await get_run(run_id="run-1", user_org=user_org, db=db)
        assert res["code"] == 0
        assert res["data"]["status"] == "QUEUED"
        assert res["data"]["run_id"] == "run-1"
        mock_agent_get.assert_not_called()


@pytest.mark.asyncio
async def test_get_run_delivered_outbox_proxies_agent_and_verifies_org():
    db = AsyncMock()
    user_org = _mock_user_org()

    task = HermesTask(
        id="run-1",
        org_id="org-1",
        user_id="user-1",
        tool_name="test_tool",
        status=TaskStatus.QUEUED,
    )

    with patch("app.api.runs.PermissionChecker.require_permission", new=AsyncMock()), \
         patch("app.api.runs.TaskService.get_task", new=AsyncMock(return_value=task)), \
         patch("app.api.runs.TaskService.assert_task_access", new=AsyncMock()), \
         patch("app.api.runs._get_outbox_entry", new=AsyncMock(return_value=None)), \
         patch("app.api.runs._agent_get", new=AsyncMock(return_value={"run_id": "run-1", "org_id": "org-foreign", "status": "RUNNING"})):

        with pytest.raises(ForbiddenError):
            await get_run(run_id="run-1", user_org=user_org, db=db)


@pytest.mark.asyncio
async def test_get_run_returns_only_the_public_run_projection():
    db = AsyncMock()
    user_org = _mock_user_org()
    task = HermesTask(id="run-1", org_id="org-1", user_id="user-1", tool_name="test_tool", status=TaskStatus.RUNNING)
    agent_run = {
        "run_id": "run-1",
        "org_id": "org-1",
        "user_id": "user-1",
        "tool_name": "test_tool",
        "status": "RUNNING",
        "snapshot": {"runtime_policy": {"internal_url": "http://agent"}},
        "created_at": "2026-08-31T00:00:00Z",
        "updated_at": "2026-08-31T00:01:00Z",
    }

    with patch("app.api.runs.PermissionChecker.require_permission", new=AsyncMock()), \
         patch("app.api.runs.TaskService.get_task", new=AsyncMock(return_value=task)), \
         patch("app.api.runs.TaskService.assert_task_access", new=AsyncMock()), \
         patch("app.api.runs._get_outbox_entry", new=AsyncMock(return_value=None)), \
         patch("app.api.runs._agent_get", new=AsyncMock(return_value=agent_run)):

        result = await get_run(run_id="run-1", user_org=user_org, db=db)

    assert result["data"] == {
        "run_id": "run-1",
        "tool_name": "test_tool",
        "status": "RUNNING",
        "created_at": "2026-08-31T00:00:00Z",
        "updated_at": "2026-08-31T00:01:00Z",
    }


@pytest.mark.asyncio
async def test_get_run_result_returns_only_public_text_and_error_fields():
    db = AsyncMock()
    user_org = _mock_user_org()
    task = HermesTask(id="run-1", org_id="org-1", user_id="user-1", tool_name="test_tool", status=TaskStatus.RUNNING)
    agent_result = {
        "run_id": "run-1",
        "org_id": "org-1",
        "user_id": "user-1",
        "status": "COMPLETED",
        "result_content": "done",
        "routing_metadata": {"gateway_token": "secret"},
    }

    with patch("app.api.runs.PermissionChecker.require_permission", new=AsyncMock()), \
         patch("app.api.runs.TaskService.get_task", new=AsyncMock(return_value=task)), \
         patch("app.api.runs.TaskService.assert_task_access", new=AsyncMock()), \
         patch("app.api.runs._get_outbox_entry", new=AsyncMock(return_value=None)), \
         patch("app.api.runs._agent_get", new=AsyncMock(return_value=agent_result)):

        result = await get_run_result(run_id="run-1", user_org=user_org, db=db)

    assert result["data"] == {
        "run_id": "run-1",
        "status": "COMPLETED",
        "text": "done",
        "error_code": None,
        "error_message": None,
    }


@pytest.mark.asyncio
async def test_get_run_artifacts_returns_only_public_descriptors():
    db = AsyncMock()
    user_org = _mock_user_org()
    task = HermesTask(id="run-1", org_id="org-1", user_id="user-1", tool_name="test_tool", status=TaskStatus.RUNNING)
    agent_artifacts = {
        "run_id": "run-1",
        "org_id": "org-1",
        "items": [{
            "artifact_id": "artifact-1",
            "name": "result.txt",
            "content_type": "text/plain",
            "size_bytes": 12,
            "checksum_sha256": "abc",
            "storage_url": "s3://internal-bucket/result.txt",
            "credential": "secret",
        }],
    }

    with patch("app.api.runs.PermissionChecker.require_permission", new=AsyncMock()), \
         patch("app.api.runs.TaskService.get_task", new=AsyncMock(return_value=task)), \
         patch("app.api.runs.TaskService.assert_task_access", new=AsyncMock()), \
         patch("app.api.runs._get_outbox_entry", new=AsyncMock(return_value=None)), \
         patch("app.api.runs._agent_get", new=AsyncMock(return_value=agent_artifacts)):

        result = await get_run_artifacts(run_id="run-1", user_org=user_org, db=db)

    assert result["data"] == {
        "run_id": "run-1",
        "items": [{
            "artifact_id": "artifact-1",
            "name": "result.txt",
            "content_type": "text/plain",
            "size_bytes": 12,
            "checksum_sha256": "abc",
        }],
    }


@pytest.mark.asyncio
async def test_cancel_undelivered_outbox_cancels_projection():
    db = AsyncMock()
    user_org = _mock_user_org()

    task = HermesTask(
        id="run-1",
        org_id="org-1",
        user_id="user-1",
        tool_name="test_tool",
        status=TaskStatus.QUEUED,
    )
    outbox = RunDispatchOutbox(
        run_id="run-1",
        dispatch_id="disp-1",
        org_id="org-1",
        user_id="user-1",
        tool_name="test_tool",
        status=RunDispatchStatus.PENDING.value,
        payload={},
        command_digest="digest",
    )

    with patch("app.api.runs.PermissionChecker.require_permission", new=AsyncMock()), \
         patch("app.api.runs.TaskService.get_task", new=AsyncMock(return_value=task)), \
         patch("app.api.runs.TaskService.assert_task_access", new=AsyncMock()), \
         patch("app.api.runs._get_outbox_entry", new=AsyncMock(return_value=outbox)), \
         patch("app.api.runs._agent_post", new=AsyncMock()) as mock_agent_post:

        res = await cancel_run(run_id="run-1", user_org=user_org, db=db)
        assert res["code"] == 0
        assert res["data"]["status"] == "CANCELLED"
        assert outbox.status == RunDispatchStatus.CANCELLED.value
        assert task.status == "cancelled"
        mock_agent_post.assert_not_called()


@pytest.mark.asyncio
async def test_resume_undelivered_outbox_rejected():
    db = AsyncMock()
    user_org = _mock_user_org()

    task = HermesTask(
        id="run-1",
        org_id="org-1",
        user_id="user-1",
        tool_name="test_tool",
        status=TaskStatus.QUEUED,
    )
    outbox = RunDispatchOutbox(
        run_id="run-1",
        dispatch_id="disp-1",
        org_id="org-1",
        user_id="user-1",
        tool_name="test_tool",
        status=RunDispatchStatus.PENDING.value,
        payload={},
        command_digest="digest",
    )

    with patch("app.api.runs.PermissionChecker.require_permission", new=AsyncMock()), \
         patch("app.api.runs.TaskService.get_task", new=AsyncMock(return_value=task)), \
         patch("app.api.runs.TaskService.assert_task_access", new=AsyncMock()), \
         patch("app.api.runs._get_outbox_entry", new=AsyncMock(return_value=outbox)):

        with pytest.raises(ForbiddenError):
            await resume_run(run_id="run-1", user_org=user_org, db=db)


@pytest.mark.asyncio
async def test_resume_run_proxies_json_body_and_exec_headers():
    db = AsyncMock()
    user_org = _mock_user_org()

    task = HermesTask(
        id="run-1",
        org_id="org-1",
        user_id="user-1",
        tool_name="test_tool",
        status=TaskStatus.RUNNING,
    )

    with patch("app.api.runs.PermissionChecker.require_permission", new=AsyncMock()), \
         patch("app.api.runs.TaskService.get_task", new=AsyncMock(return_value=task)), \
         patch("app.api.runs.TaskService.assert_task_access", new=AsyncMock()), \
         patch("app.api.runs._get_outbox_entry", new=AsyncMock(return_value=None)), \
         patch("app.api.runs._agent_post", new=AsyncMock(return_value={"run_id": "run-1", "org_id": "org-1", "status": "RUNNING"})) as mock_post:

        payload = {"action": "continue", "input": {"val": 42}}
        res = await resume_run(run_id="run-1", body=payload, user_org=user_org, db=db)
        assert res["code"] == 0
        assert res["data"]["run_id"] == "run-1"
        mock_post.assert_called_once_with(
            "/internal/v1/runs/run-1/resume",
            json_body=payload,
            org_id="org-1",
            user_id="user-1",
        )


@pytest.mark.asyncio
async def test_approve_run_proxies_json_body_and_exec_headers():
    db = AsyncMock()
    user_org = _mock_user_org()

    task = HermesTask(
        id="run-1",
        org_id="org-1",
        user_id="user-1",
        tool_name="test_tool",
        status=TaskStatus.RUNNING,
    )

    with patch("app.api.runs.PermissionChecker.require_permission", new=AsyncMock()), \
         patch("app.api.runs.TaskService.get_task", new=AsyncMock(return_value=task)), \
         patch("app.api.runs.TaskService.assert_task_access", new=AsyncMock()), \
         patch("app.api.runs._get_outbox_entry", new=AsyncMock(return_value=None)), \
         patch("app.api.runs._agent_post", new=AsyncMock(return_value={"run_id": "run-1", "org_id": "org-1", "status": "APPROVED"})) as mock_post:

        payload = {"decision": "APPROVE", "evidence": "verified by admin"}
        res = await approve_run(run_id="run-1", approval_id="app-1", body=payload, user_org=user_org, db=db)
        assert res["code"] == 0
        assert res["data"]["status"] == "APPROVED"
        mock_post.assert_called_once_with(
            "/internal/v1/runs/run-1/approvals/app-1",
            json_body=payload,
            org_id="org-1",
            user_id="user-1",
        )


@pytest.mark.asyncio
async def test_agent_4xx_mapped_to_app_exception():
    import httpx

    fake_response = httpx.Response(
        status_code=400,
        json={"error_code": 40001, "message_key": "errors.run.invalid_state", "message": "Run cannot be resumed"},
        request=httpx.Request("POST", "http://test/internal/v1/runs/run-1/resume"),
    )

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=fake_response)):
        with pytest.raises(AppException) as exc_info:
            await _agent_post("/internal/v1/runs/run-1/resume", json_body={}, org_id="org-1", user_id="user-1")
        assert exc_info.value.status_code == 400
        assert exc_info.value.message_key == "errors.run.invalid_state"
        assert exc_info.value.message == "Run cannot be resumed"


@pytest.mark.asyncio
async def test_agent_404_mapped_to_not_found():
    import httpx

    fake_response = httpx.Response(
        status_code=404,
        request=httpx.Request("POST", "http://test/internal/v1/runs/run-nonexistent/resume"),
    )

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=fake_response)):
        with pytest.raises(NotFoundError) as exc_info:
            await _agent_post("/internal/v1/runs/run-nonexistent/resume", json_body={}, org_id="org-1", user_id="user-1")
        assert exc_info.value.status_code == 404
        assert exc_info.value.message_key == "errors.run.not_found"


@pytest.mark.asyncio
async def test_stream_run_events_passes_semantic_event_type_and_seq():
    db = AsyncMock()
    user_org = _mock_user_org()
    request = MagicMock()
    request.is_disconnected = AsyncMock(return_value=False)

    task = HermesTask(
        id="run-1",
        org_id="org-1",
        user_id="user-1",
        tool_name="test_tool",
        status=TaskStatus.RUNNING,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    semantic_item = {
        "event_id": "evt-sem-1",
        "run_id": "run-1",
        "event_type": "assistant.message",
        "event_seq": 7,
        "source": "agent",
        "source_event_id": "hermes:run-1:att-1:assistant:1",
        "timestamp": "2026-08-31T00:00:00Z",
        "payload": {"text": "hello"},
    }
    terminal_item = {
        "event_id": "evt-done",
        "run_id": "run-1",
        "event_type": "run.completed",
        "event_seq": 8,
        "source": "agent",
        "timestamp": "2026-08-31T00:00:01Z",
        "payload": {},
    }

    async def _agent_get_side_effect(path, params=None, org_id=None, user_id=None):
        if path.endswith("/events"):
            return {"items": [semantic_item, terminal_item]}
        return {"run_id": "run-1", "org_id": "org-1", "status": "COMPLETED"}

    with patch("app.api.runs._authorize_run", new=AsyncMock(return_value=task)), \
         patch("app.api.runs._get_outbox_entry", new=AsyncMock(return_value=None)), \
         patch("app.api.runs.pg_notify_service.subscribe"), \
         patch("app.api.runs.pg_notify_service.unsubscribe"), \
         patch("app.api.runs._agent_get", new=AsyncMock(side_effect=_agent_get_side_effect)):

        response = await stream_run_events(
            run_id="run-1",
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

    assert "event: assistant.message\n" in body
    assert "id: run-1:7\n" in body
    assert "event: run.completed\n" in body
    assert "id: run-1:8\n" in body
    assert "source_event_id" not in body
    assert '"source"' not in body

