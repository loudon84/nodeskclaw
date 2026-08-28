import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
from app.api.runs import get_run, get_run_result, get_run_artifacts, download_run_artifact, cancel_run, resume_run, approve_run
from app.core.exceptions import ForbiddenError, NotFoundError
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
        assert res["data"]["status"] == "DISPATCH_PENDING"
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
