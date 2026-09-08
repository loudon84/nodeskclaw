import json

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi.responses import JSONResponse

from app.api.runs import (
    _agent_post,
    _public_run_event,
    _public_run_result,
    _public_run_view,
    approve_run,
    cancel_run,
    decide_run_approval,
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


def _empty_ledger_db(db: AsyncMock) -> AsyncMock:
    empty = MagicMock()
    empty.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=empty)
    nested = AsyncMock()
    nested.__aenter__ = AsyncMock(return_value=None)
    nested.__aexit__ = AsyncMock(return_value=False)
    db.begin_nested = MagicMock(return_value=nested)
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    return db


def _assert_unwrapped_public_body(result: dict):
    assert "code" not in result
    assert "data" not in result


def _ledger_db_with_existing(existing) -> AsyncMock:
    db = _empty_ledger_db(AsyncMock())
    loaded = MagicMock()
    loaded.scalar_one_or_none.return_value = existing
    db.execute = AsyncMock(return_value=loaded)
    return db


def _approval_task() -> HermesTask:
    return HermesTask(
        id="run-1",
        org_id="org-1",
        user_id="user-1",
        tool_name="test_tool",
        status=TaskStatus.RUNNING,
    )


def _approval_route_patches(task: HermesTask, *, agent_post=None, agent_get=None):
    get_payload = {"run_id": "run-1", "org_id": "org-1", "status": "WAITING_APPROVAL"}
    post_payload = {"run_id": "run-1", "org_id": "org-1", "status": "WAITING_APPROVAL"}
    return (
        patch("app.api.runs.PermissionChecker.require_permission", new=AsyncMock()),
        patch("app.api.runs.TaskService.get_task", new=AsyncMock(return_value=task)),
        patch("app.api.runs.TaskService.assert_task_access", new=AsyncMock()),
        patch("app.api.runs._get_outbox_entry", new=AsyncMock(return_value=None)),
        patch("app.api.runs._agent_post", new=agent_post or AsyncMock(return_value=post_payload)),
        patch("app.api.runs._agent_get", new=agent_get or AsyncMock(return_value=get_payload)),
    )


@pytest.mark.asyncio
async def test_get_run_projection_missing_fails_closed():
    db = _empty_ledger_db(AsyncMock())
    user_org = _mock_user_org()

    with patch("app.api.runs.PermissionChecker.require_permission", new=AsyncMock()), \
         patch("app.api.runs.TaskService.get_task", side_effect=NotFoundError("Task 不存在", "errors.task.not_found")), \
         patch("app.api.runs._agent_get", new=AsyncMock()) as mock_agent_get:

        with pytest.raises(NotFoundError):
            await get_run(run_id="run-nonexistent", user_org=user_org, db=db)

        mock_agent_get.assert_not_called()


@pytest.mark.asyncio
async def test_get_run_undelivered_outbox_returns_dispatch_pending():
    db = _empty_ledger_db(AsyncMock())
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
        _assert_unwrapped_public_body(res)
        assert res["status"] == "QUEUED"
        assert res["run_id"] == "run-1"
        assert res["tool_name"] == "test_tool"
        mock_agent_get.assert_not_called()


@pytest.mark.asyncio
async def test_get_run_delivered_outbox_proxies_agent_and_verifies_org():
    db = _empty_ledger_db(AsyncMock())
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
    db = _empty_ledger_db(AsyncMock())
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

    _assert_unwrapped_public_body(result)
    assert result == {
        "run_id": "run-1",
        "tool_name": "test_tool",
        "status": "RUNNING",
        "created_at": "2026-08-31T00:00:00Z",
        "updated_at": "2026-08-31T00:01:00Z",
    }


@pytest.mark.asyncio
async def test_get_run_result_returns_only_public_text_and_error_fields():
    db = _empty_ledger_db(AsyncMock())
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

    _assert_unwrapped_public_body(result)
    assert result == {
        "run_id": "run-1",
        "status": "COMPLETED",
        "text": "done",
        "error_code": None,
        "error_message": None,
    }


@pytest.mark.asyncio
async def test_get_run_artifacts_returns_only_public_descriptors():
    db = _empty_ledger_db(AsyncMock())
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

    _assert_unwrapped_public_body(result)
    assert result == {
        "run_id": "run-1",
        "items": [{
            "artifact_id": "artifact-1",
            "name": "result.txt",
            "content_type": "text/plain",
            "size_bytes": 12,
            "checksum_sha256": "abc",
        }],
    }
    assert "storage_url" not in result["items"][0]
    assert "credential" not in result["items"][0]


@pytest.mark.asyncio
async def test_download_run_artifact_does_not_leak_storage_credentials():
    import httpx

    db = _empty_ledger_db(AsyncMock())
    user_org = _mock_user_org()
    task = HermesTask(id="run-1", org_id="org-1", user_id="user-1", tool_name="test_tool", status=TaskStatus.RUNNING)
    agent_artifacts = {
        "run_id": "run-1",
        "org_id": "org-1",
        "items": [{
            "artifact_id": "artifact-1",
            "name": "result.txt",
            "content_type": "text/plain",
            "size_bytes": 4,
            "checksum_sha256": "abcd",
            "storage_url": "s3://internal-bucket/result.txt",
            "credential": "secret-token",
            "presigned_url": "https://example.com/presigned?token=leak",
        }],
    }
    agent_bytes = httpx.Response(
        status_code=200,
        content=b"data",
        headers={
            "content-type": "text/plain",
            "X-Storage-Credential": "secret-token",
            "Authorization": "Bearer leak",
        },
        request=httpx.Request("GET", "http://agent/internal/v1/runs/run-1/artifacts/artifact-1/bytes"),
    )

    with patch("app.api.runs.PermissionChecker.require_permission", new=AsyncMock()), \
         patch("app.api.runs.TaskService.get_task", new=AsyncMock(return_value=task)), \
         patch("app.api.runs.TaskService.assert_task_access", new=AsyncMock()), \
         patch("app.api.runs._get_outbox_entry", new=AsyncMock(return_value=None)), \
         patch("app.api.runs._agent_get", new=AsyncMock(return_value=agent_artifacts)), \
         patch("httpx.AsyncClient.get", new=AsyncMock(return_value=agent_bytes)):

        response = await download_run_artifact(
            run_id="run-1",
            artifact_id="artifact-1",
            user_org=user_org,
            db=db,
        )

    assert response.body == b"data"
    header_blob = " ".join(f"{k}:{v}" for k, v in response.headers.items()).lower()
    assert "secret-token" not in header_blob
    assert "presigned" not in header_blob
    assert "authorization" not in header_blob
    assert "storage" not in header_blob
    assert response.headers.get("cache-control") == "no-store"


@pytest.mark.asyncio
async def test_cancel_undelivered_outbox_cancels_projection():
    db = _empty_ledger_db(AsyncMock())
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
        _assert_unwrapped_public_body(res)
        assert res["status"] == "CANCELLED"
        assert res["run_id"] == "run-1"
        assert outbox.status == RunDispatchStatus.CANCELLED.value
        assert task.status == "cancelled"
        mock_agent_post.assert_not_called()


@pytest.mark.asyncio
async def test_cancel_delivered_run_requests_cancellation_for_active_edge_jobs():
    db = _empty_ledger_db(AsyncMock())
    user_org = _mock_user_org()
    task = HermesTask(id="run-1", org_id="org-1", user_id="user-1", tool_name="test_tool", status=TaskStatus.RUNNING)

    with patch("app.api.runs.PermissionChecker.require_permission", new=AsyncMock()), \
         patch("app.api.runs.TaskService.get_task", new=AsyncMock(return_value=task)), \
         patch("app.api.runs.TaskService.assert_task_access", new=AsyncMock()), \
         patch("app.api.runs._get_outbox_entry", new=AsyncMock(return_value=None)), \
         patch("app.api.runs._agent_post", new=AsyncMock(return_value={"org_id": "org-1", "run_id": "run-1", "tool_name": "test_tool", "status": "CANCELLING"})):
        result = await cancel_run(run_id="run-1", user_org=user_org, db=db)

    _assert_unwrapped_public_body(result)
    assert result["status"] == "CANCELLING"
    statement = str(db.execute.await_args.args[0])
    assert "edge_jobs" in statement
    assert "cancel_requested_at" in statement
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_cancel_run_agent_conflict_is_not_http_500():
    db = _empty_ledger_db(AsyncMock())
    user_org = _mock_user_org()
    task = HermesTask(id="run-1", org_id="org-1", user_id="user-1", tool_name="test_tool", status=TaskStatus.RUNNING)
    conflict = AppException(
        code=40900,
        message="approval not active",
        status_code=409,
        message_key="errors.run.agent_error",
    )
    with patch("app.api.runs.PermissionChecker.require_permission", new=AsyncMock()), \
         patch("app.api.runs.TaskService.get_task", new=AsyncMock(return_value=task)), \
         patch("app.api.runs.TaskService.assert_task_access", new=AsyncMock()), \
         patch("app.api.runs._get_outbox_entry", new=AsyncMock(return_value=None)), \
         patch("app.api.runs._agent_post", new=AsyncMock(side_effect=conflict)):
        with pytest.raises(AppException) as exc_info:
            await cancel_run(run_id="run-1", user_org=user_org, db=db)
    assert exc_info.value.status_code == 409
    assert exc_info.value.status_code != 500


@pytest.mark.asyncio
async def test_cancel_run_agent_500_is_not_http_500():
    db = _empty_ledger_db(AsyncMock())
    user_org = _mock_user_org()
    task = HermesTask(id="run-1", org_id="org-1", user_id="user-1", tool_name="test_tool", status=TaskStatus.RUNNING)
    response = MagicMock()
    response.status_code = 500
    conflict = httpx.HTTPStatusError("agent failed", request=MagicMock(), response=response)
    with patch("app.api.runs.PermissionChecker.require_permission", new=AsyncMock()), \
         patch("app.api.runs.TaskService.get_task", new=AsyncMock(return_value=task)), \
         patch("app.api.runs.TaskService.assert_task_access", new=AsyncMock()), \
         patch("app.api.runs._get_outbox_entry", new=AsyncMock(return_value=None)), \
         patch("app.api.runs._agent_post", new=AsyncMock(side_effect=conflict)):
        with pytest.raises(AppException) as exc_info:
            await cancel_run(run_id="run-1", user_org=user_org, db=db)
    assert exc_info.value.status_code == 409
    assert exc_info.value.status_code != 500


@pytest.mark.asyncio
async def test_cancel_run_agent_mutation_without_tool_name_is_not_http_500():
    db = _empty_ledger_db(AsyncMock())
    user_org = _mock_user_org()
    task = HermesTask(id="run-1", org_id="org-1", user_id="user-1", tool_name="test_tool", status=TaskStatus.RUNNING)
    with patch("app.api.runs.PermissionChecker.require_permission", new=AsyncMock()), \
         patch("app.api.runs.TaskService.get_task", new=AsyncMock(return_value=task)), \
         patch("app.api.runs.TaskService.assert_task_access", new=AsyncMock()), \
         patch("app.api.runs._get_outbox_entry", new=AsyncMock(return_value=None)), \
         patch(
             "app.api.runs._agent_post",
             new=AsyncMock(
                 return_value={
                     "org_id": "org-1",
                     "run_id": "run-1",
                     "status": "CANCELLING",
                     "idempotent": True,
                 }
             ),
         ):
        result = await cancel_run(run_id="run-1", user_org=user_org, db=db)
    _assert_unwrapped_public_body(result)
    assert result["run_id"] == "run-1"
    assert result["tool_name"] == "test_tool"
    assert result["status"] == "CANCELLING"


@pytest.mark.asyncio
async def test_resume_undelivered_outbox_rejected():
    db = _empty_ledger_db(AsyncMock())
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
    db = _empty_ledger_db(AsyncMock())
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
    db = _empty_ledger_db(AsyncMock())
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
         patch("app.api.runs._agent_post", new=AsyncMock(return_value={"run_id": "run-1", "org_id": "org-1", "status": "APPROVED"})) as mock_post, \
         patch("app.api.runs._agent_get", new=AsyncMock(return_value={"run_id": "run-1", "org_id": "org-1", "status": "WAITING_APPROVAL"})):

        payload = {"decision": "APPROVE", "evidence": "verified by admin"}
        res = await approve_run(run_id="run-1", approval_id="app-1", body=payload, user_org=user_org, db=db)
        assert res["code"] == 0
        assert res["data"]["decision"] == "allow"
        assert res["data"]["status"] == "WAITING_APPROVAL"
        assert res["data"]["approval_id"] == "app-1"
        mock_post.assert_called_once_with(
            "/internal/v1/runs/run-1/approvals/app-1",
            json_body={"decision": "approve", "evidence": "verified by admin"},
            org_id="org-1",
            user_id="user-1",
        )


@pytest.mark.asyncio
async def test_approve_run_deny_maps_to_internal_deny():
    db = _empty_ledger_db(AsyncMock())
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
         patch("app.api.runs._agent_post", new=AsyncMock(return_value={"run_id": "run-1", "org_id": "org-1", "status": "WAITING_APPROVAL"})) as mock_post, \
         patch("app.api.runs._agent_get", new=AsyncMock(return_value={"run_id": "run-1", "org_id": "org-1", "status": "WAITING_APPROVAL"})):
        res = await approve_run(
            run_id="run-1",
            approval_id="app-1",
            body={"decision": "DENY"},
            user_org=user_org,
            db=db,
        )
    assert res["code"] == 0
    mock_post.assert_called_once_with(
        "/internal/v1/runs/run-1/approvals/app-1",
        json_body={"decision": "deny"},
        org_id="org-1",
        user_id="user-1",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("forbidden", ["session", "always"])
async def test_approve_run_rejects_session_and_always_before_agent(forbidden):
    db = _empty_ledger_db(AsyncMock())
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
         patch("app.api.runs._agent_post", new=AsyncMock()) as mock_post:
        with pytest.raises(AppException) as exc_info:
            await approve_run(
                run_id="run-1",
                approval_id="app-1",
                body={"decision": forbidden},
                user_org=user_org,
                db=db,
            )
    assert exc_info.value.status_code == 400
    assert exc_info.value.message_key == "errors.run.approval_choice_forbidden"
    mock_post.assert_not_called()


def _canonical_error(result) -> tuple[int, dict]:
    assert isinstance(result, JSONResponse)
    return result.status_code, json.loads(result.body.decode())


@pytest.mark.asyncio
# @lat: [[architecture/skill-agent#RM-17 Public Approval Decision]]
async def test_decide_run_approval_returns_bare_receipt():
    db = _empty_ledger_db(AsyncMock())
    user_org = _mock_user_org()
    task = _approval_task()
    mock_post = AsyncMock(return_value={"run_id": "run-1", "org_id": "org-1", "status": "WAITING_APPROVAL"})
    patches = _approval_route_patches(task, agent_post=mock_post)
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        res = await decide_run_approval(
            run_id="run-1",
            approval_id="app-1",
            body={"decision": "allow"},
            user_org=user_org,
            db=db,
            idempotency_key="key-1",
        )
    assert res["run_id"] == "run-1"
    assert res["approval_id"] == "app-1"
    assert res["decision"] == "allow"
    assert res["status"] == "WAITING_APPROVAL"
    assert "decided_at" in res
    assert "code" not in res
    assert "data" not in res
    db.commit.assert_awaited_once()
    mock_post.assert_called_once_with(
        "/internal/v1/runs/run-1/approvals/app-1",
        json_body={"decision": "approve"},
        org_id="org-1",
        user_id="user-1",
    )


@pytest.mark.asyncio
async def test_decide_run_approval_requires_idempotency_key():
    db = _empty_ledger_db(AsyncMock())
    user_org = _mock_user_org()
    task = _approval_task()
    mock_post = AsyncMock()
    patches = _approval_route_patches(task, agent_post=mock_post)
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        res = await decide_run_approval(
            run_id="run-1",
            approval_id="app-1",
            body={"decision": "allow"},
            user_org=user_org,
            db=db,
            idempotency_key=None,
        )
    status, payload = _canonical_error(res)
    assert status == 400
    assert payload["error_code"] == "IDEMPOTENCY_KEY_REQUIRED"
    assert payload["message_key"] == "errors.run.idempotency_key_required"
    mock_post.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("body", "error_code", "message_key"),
    [
        ({"decision": "session"}, "APPROVAL_DECISION_INVALID", "errors.run.approval_choice_forbidden"),
        ({"decision": "always"}, "APPROVAL_DECISION_INVALID", "errors.run.approval_choice_forbidden"),
        ({"decision": "maybe"}, "APPROVAL_DECISION_INVALID", "errors.run.approval_choice_forbidden"),
        ({"decision": "allow", "extra": True}, "APPROVAL_DECISION_INVALID", "errors.run.approval_decision_invalid"),
        ({"decision": "allow", "comment": "x" * 501}, "APPROVAL_DECISION_INVALID", "errors.run.approval_decision_invalid"),
    ],
)
async def test_decide_run_approval_rejects_invalid_decision(body, error_code, message_key):
    db = _empty_ledger_db(AsyncMock())
    user_org = _mock_user_org()
    task = _approval_task()
    mock_post = AsyncMock()
    patches = _approval_route_patches(task, agent_post=mock_post)
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        res = await decide_run_approval(
            run_id="run-1",
            approval_id="app-1",
            body=body,
            user_org=user_org,
            db=db,
            idempotency_key="key-1",
        )
    status, payload = _canonical_error(res)
    assert status == 400
    assert payload["error_code"] == error_code
    assert payload["message_key"] == message_key
    mock_post.assert_not_called()


@pytest.mark.asyncio
async def test_approve_run_and_decision_share_submit_service():
    db = _empty_ledger_db(AsyncMock())
    user_org = _mock_user_org()
    task = _approval_task()
    receipt = {
        "run_id": "run-1",
        "approval_id": "app-1",
        "decision": "allow",
        "status": "WAITING_APPROVAL",
        "decided_at": "2026-09-07T00:00:00Z",
    }
    mock_submit = AsyncMock(return_value=receipt)
    with patch("app.api.runs.PermissionChecker.require_permission", new=AsyncMock()), \
         patch("app.api.runs.TaskService.get_task", new=AsyncMock(return_value=task)), \
         patch("app.api.runs.TaskService.assert_task_access", new=AsyncMock()), \
         patch("app.api.runs._get_outbox_entry", new=AsyncMock(return_value=None)), \
         patch("app.api.runs.submit_approval_decision", new=mock_submit):
        legacy = await approve_run(
            run_id="run-1",
            approval_id="app-1",
            body={"decision": "allow"},
            user_org=user_org,
            db=db,
            idempotency_key="legacy-key",
        )
        canonical = await decide_run_approval(
            run_id="run-1",
            approval_id="app-1",
            body={"decision": "allow"},
            user_org=user_org,
            db=db,
            idempotency_key="canon-key",
        )
    assert mock_submit.call_count == 2
    assert legacy == {"code": 0, "data": receipt}
    assert canonical == receipt


@pytest.mark.asyncio
async def test_idempotency_replay_returns_frozen_receipt_without_second_post():
    existing = MagicMock()
    existing.idempotency_key = "key-1"
    existing.decision = "allow"
    existing.response_body = {
        "run_id": "run-1",
        "approval_id": "app-1",
        "decision": "allow",
        "status": "WAITING_APPROVAL",
        "decided_at": "2026-09-07T00:00:00Z",
    }
    db = _ledger_db_with_existing(existing)
    user_org = _mock_user_org()
    task = _approval_task()
    mock_post = AsyncMock()
    patches = _approval_route_patches(task, agent_post=mock_post)
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        res = await decide_run_approval(
            run_id="run-1",
            approval_id="app-1",
            body={"decision": "allow"},
            user_org=user_org,
            db=db,
            idempotency_key="key-1",
        )
    assert res == existing.response_body
    mock_post.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_idempotency_conflict_same_key_different_decision():
    existing = MagicMock()
    existing.idempotency_key = "key-1"
    existing.decision = "allow"
    existing.response_body = {"run_id": "run-1", "decision": "allow"}
    db = _ledger_db_with_existing(existing)
    user_org = _mock_user_org()
    task = _approval_task()
    mock_post = AsyncMock()
    patches = _approval_route_patches(task, agent_post=mock_post)
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        res = await decide_run_approval(
            run_id="run-1",
            approval_id="app-1",
            body={"decision": "deny"},
            user_org=user_org,
            db=db,
            idempotency_key="key-1",
        )
    status, payload = _canonical_error(res)
    assert status == 409
    assert payload["error_code"] == "IDEMPOTENCY_CONFLICT"
    assert payload["message_key"] == "errors.run.idempotency_conflict"
    mock_post.assert_not_called()


@pytest.mark.asyncio
async def test_idempotency_already_decided_new_key():
    existing = MagicMock()
    existing.idempotency_key = "key-1"
    existing.decision = "allow"
    existing.response_body = {"run_id": "run-1", "decision": "allow"}
    db = _ledger_db_with_existing(existing)
    user_org = _mock_user_org()
    task = _approval_task()
    mock_post = AsyncMock()
    patches = _approval_route_patches(task, agent_post=mock_post)
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        res = await decide_run_approval(
            run_id="run-1",
            approval_id="app-1",
            body={"decision": "allow"},
            user_org=user_org,
            db=db,
            idempotency_key="key-2",
        )
    status, payload = _canonical_error(res)
    assert status == 409
    assert payload["error_code"] == "APPROVAL_ALREADY_DECIDED"
    assert payload["message_key"] == "errors.run.approval_already_decided"
    mock_post.assert_not_called()


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


def test_public_run_event_projects_semantic_types_and_drops_unknown():
    assert _public_run_event(
        {
            "event_type": "reasoning.summary",
            "event_seq": 5,
            "timestamp": "2026-08-31T00:00:03Z",
            "payload": {"summary": "checked docs", "chain_of_thought": "secret"},
        },
        "run-1",
    ) == {
        "event_id": "run-1:5",
        "run_id": "run-1",
        "event_type": "reasoning.summary",
        "event_seq": 5,
        "timestamp": "2026-08-31T00:00:03Z",
        "payload": {"summary": "checked docs"},
    }
    assert _public_run_event(
        {
            "event_type": "tool.call",
            "event_seq": 3,
            "timestamp": "2026-08-31T00:00:01Z",
            "payload": {
                "tool_name": "search",
                "call_id": "call-1",
                "status": "started",
                "arguments": {"q": "x"},
            },
        },
        "run-1",
    )["payload"] == {"tool_name": "search", "call_id": "call-1", "status": "started"}
    assert _public_run_event(
        {
            "event_type": "clarify.requested",
            "event_seq": 6,
            "timestamp": "2026-08-31T00:00:04Z",
            "payload": {"question": "which file?", "options": ["a", "b"]},
        },
        "run-1",
    )["payload"] == {"question": "which file?", "options": ["a", "b"]}
    assert _public_run_event(
        {
            "event_type": "approval.requested",
            "event_seq": 7,
            "timestamp": "2026-08-31T00:00:05Z",
            "payload": {"approval_id": "appr-1", "summary": "delete file"},
        },
        "run-1",
    )["payload"] == {"approval_id": "appr-1", "summary": "delete file", "options": ["allow", "deny"]}


def test_public_run_event_projects_approval_options():
    projected = _public_run_event(
        {
            "event_type": "approval.requested",
            "event_seq": 7,
            "timestamp": "2026-08-31T00:00:05Z",
            "payload": {"approval_id": "appr-1", "summary": "delete file", "runtime_run_id": "secret"},
        },
        "run-1",
    )
    assert projected is not None
    assert projected["payload"] == {"approval_id": "appr-1", "summary": "delete file", "options": ["allow", "deny"]}
    assert "runtime_run_id" not in str(projected)
    assert _public_run_event(
        {
            "event_type": "internal.debug",
            "event_seq": 99,
            "timestamp": "2026-08-31T00:00:06Z",
            "payload": {"secret": "nope"},
        },
        "run-1",
    ) is None
    assert _public_run_event(
        {
            "event_type": "internal.runtime.trace",
            "event_seq": 100,
            "timestamp": "2026-08-31T00:00:07Z",
            "payload": {"runtime_event_type": "subagent.started", "category": "subagent"},
        },
        "run-1",
    ) is None
    assert _public_run_event(
        {
            "event_type": "tool.call",
            "event_seq": 3,
            "timestamp": "2026-08-31T00:00:01Z",
            "payload": {"tool_name": "search", "call_id": "call-1", "status": "bogus"},
        },
        "run-1",
    ) is None


def test_public_run_event_progress_uses_phase_not_status():
    projected = _public_run_event(
        {
            "event_type": "run.progress",
            "event_seq": 1,
            "status": "HERMES_TASK_SECRET",
            "timestamp": "2026-08-31T00:00:00Z",
            "payload": {"phase": "RUNTIME_RUNNING", "stage": "runtime_running", "message": "streaming"},
        },
        "run-1",
    )
    assert projected is not None
    assert projected["payload"]["phase"] == "RUNTIME_RUNNING"
    assert projected["payload"]["stage"] == "runtime_running"
    assert "HERMES_TASK_SECRET" not in str(projected)


@pytest.mark.asyncio
async def test_stream_run_events_passes_semantic_event_type_and_seq():
    db = _empty_ledger_db(AsyncMock())
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

    semantic_items = [
        {
            "event_id": "evt-sem-1",
            "run_id": "run-1",
            "event_type": "assistant.message",
            "event_seq": 7,
            "source": "agent",
            "source_event_id": "hermes:run-1:att-1:assistant:1",
            "timestamp": "2026-08-31T00:00:00Z",
            "payload": {"text": "hello"},
        },
        {
            "event_id": "evt-rs",
            "run_id": "run-1",
            "event_type": "reasoning.summary",
            "event_seq": 8,
            "source": "agent",
            "timestamp": "2026-08-31T00:00:01Z",
            "payload": {"summary": "checked docs"},
        },
        {
            "event_id": "evt-tool",
            "run_id": "run-1",
            "event_type": "tool.call",
            "event_seq": 9,
            "source": "agent",
            "timestamp": "2026-08-31T00:00:02Z",
            "payload": {"tool_name": "search", "call_id": "call-1", "status": "started"},
        },
        {
            "event_id": "evt-clarify",
            "run_id": "run-1",
            "event_type": "clarify.requested",
            "event_seq": 10,
            "source": "agent",
            "timestamp": "2026-08-31T00:00:03Z",
            "payload": {"question": "which file?", "options": ["a", "b"]},
        },
        {
            "event_id": "evt-appr",
            "run_id": "run-1",
            "event_type": "approval.requested",
            "event_seq": 11,
            "source": "agent",
            "timestamp": "2026-08-31T00:00:04Z",
            "payload": {"approval_id": "appr-1", "summary": "delete file"},
        },
        {
            "event_id": "evt-unknown",
            "run_id": "run-1",
            "event_type": "internal.debug",
            "event_seq": 12,
            "source": "agent",
            "timestamp": "2026-08-31T00:00:05Z",
            "payload": {"secret": "nope"},
        },
        {
            "event_id": "evt-done",
            "run_id": "run-1",
            "event_type": "run.completed",
            "event_seq": 13,
            "source": "agent",
            "timestamp": "2026-08-31T00:00:06Z",
            "payload": {},
        },
    ]

    async def _agent_get_side_effect(path, params=None, org_id=None, user_id=None):
        if path.endswith("/events"):
            after_seq = int((params or {}).get("after_seq") or 0)
            return {"items": [item for item in semantic_items if int(item["event_seq"]) > after_seq]}
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
        assert response.headers.get("cache-control") == "no-store"
        chunks: list[str] = []
        async for chunk in response.body_iterator:
            chunks.append(chunk if isinstance(chunk, str) else chunk.decode())
        body = "".join(chunks)

    assert "event: assistant.message\n" in body
    assert "id: run-1:7\n" in body
    assert "event: reasoning.summary\n" in body
    assert "event: tool.call\n" in body
    assert "event: clarify.requested\n" in body
    assert "event: approval.requested\n" in body
    assert "event: run.completed\n" in body
    assert "id: run-1:13\n" in body
    assert "internal.debug" not in body
    assert "source_event_id" not in body
    assert '"source"' not in body
    assert "chain_of_thought" not in body
    assert '"arguments"' not in body
    completed_at = body.find("event: run.completed\n")
    assert completed_at >= 0
    assert body.find("event: run.completed\n") <= len(body)


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
async def test_stream_run_events_delivers_terminal_before_close(agent_status, event_type):
    db = _empty_ledger_db(AsyncMock())
    user_org = _mock_user_org()
    request = MagicMock()
    request.is_disconnected = AsyncMock(return_value=False)
    task = HermesTask(
        id="run-1",
        org_id="org-1",
        user_id="user-1",
        tool_name="test_tool",
        status=TaskStatus.RUNNING,
    )

    async def _agent_get_side_effect(path, params=None, org_id=None, user_id=None):
        if path.endswith("/events"):
            return {"items": []}
        return {
            "run_id": "run-1",
            "org_id": "org-1",
            "status": agent_status,
            "updated_at": "2026-08-31T00:00:09Z",
        }

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
        assert response.headers.get("cache-control") == "no-store"
        chunks: list[str] = []
        async for chunk in response.body_iterator:
            chunks.append(chunk if isinstance(chunk, str) else chunk.decode())
        body = "".join(chunks)

    assert f"event: {event_type}\n" in body
    assert "event: hermes.run.delta" not in body


@pytest.mark.asyncio
async def test_stream_run_events_honors_last_event_id_resume():
    db = _empty_ledger_db(AsyncMock())
    user_org = _mock_user_org()
    request = MagicMock()
    request.is_disconnected = AsyncMock(return_value=False)
    task = HermesTask(
        id="run-1",
        org_id="org-1",
        user_id="user-1",
        tool_name="test_tool",
        status=TaskStatus.RUNNING,
    )
    captured_after_seq: list[int] = []

    async def _agent_get_side_effect(path, params=None, org_id=None, user_id=None):
        if path.endswith("/events"):
            after_seq = int((params or {}).get("after_seq") or 0)
            captured_after_seq.append(after_seq)
            return {
                "items": [
                    {
                        "event_type": "run.completed",
                        "event_seq": after_seq + 1,
                        "timestamp": "2026-08-31T00:00:06Z",
                        "payload": {},
                    }
                ]
            }
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
            last_event_id_header="run-1:7",
        )
        async for _ in response.body_iterator:
            pass

    assert captured_after_seq
    assert captured_after_seq[0] == 7


def test_public_run_view_result_strips_topology_keys():
    view = _public_run_view(
        {
            "run_id": "run-1",
            "tool_name": "writer",
            "status": "RUNNING",
            "created_at": "2026-09-08T00:00:00Z",
            "updated_at": "2026-09-08T00:00:01Z",
            "delegation_topology": "runtime_delegated",
            "runtime_capability_ref": "cap://x",
            "execution_snapshot": {"members": []},
            "runtime_members": [{"id": "child"}],
        }
    )
    assert view["run_id"] == "run-1"
    assert view["tool_name"] == "writer"
    assert "delegation_topology" not in view
    assert "runtime_capability_ref" not in view
    assert "execution_snapshot" not in view
    assert "runtime_members" not in view

    result = _public_run_result(
        {
            "status": "COMPLETED",
            "result_content": "ok",
            "delegation_topology": "runtime_delegated",
            "runtime_capability_ref": "cap://x",
            "execution_snapshot": {},
            "runtime_members": [],
        },
        "run-1",
    )
    assert result["run_id"] == "run-1"
    assert result["text"] == "ok"
    assert "delegation_topology" not in result
    assert "runtime_capability_ref" not in result
    assert "execution_snapshot" not in result
    assert "runtime_members" not in result


def test_public_run_sse_drops_internal_runtime_and_subagent_topology():
    assert _public_run_event(
        {
            "event_type": "internal.runtime.trace",
            "event_seq": 8,
            "payload": {"runtime_event_type": "subagent.started", "delegation_topology": "runtime_delegated"},
        },
        "run-1",
    ) is None
    assert _public_run_event(
        {
            "event_type": "subagent.started",
            "event_seq": 9,
            "payload": {"child_run_id": "child-1"},
        },
        "run-1",
    ) is None
    projected = _public_run_event(
        {
            "event_type": "run.progress",
            "event_seq": 1,
            "timestamp": "2026-09-08T00:00:00Z",
            "payload": {
                "phase": "RUNTIME_RUNNING",
                "delegation_topology": "runtime_delegated",
                "runtime_capability_ref": "cap://x",
            },
        },
        "run-1",
    )
    assert projected is not None
    assert projected["run_id"] == "run-1"
    assert "delegation_topology" not in projected
    assert "delegation_topology" not in projected["payload"]
    assert "runtime_capability_ref" not in projected["payload"]
    assert "child_run_id" not in str(projected)
