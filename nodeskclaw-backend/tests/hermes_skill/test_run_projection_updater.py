import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.hermes_skill.hermes_task import HermesTask, TaskStatus
from app.services.hermes_skill.run_projection_updater_service import RunProjectionUpdaterService


@pytest.mark.asyncio
async def test_sync_task_projection_updates_events_and_cursor(monkeypatch):
    db = AsyncMock()
    mock_task = HermesTask(
        id="task-1",
        org_id="org-1",
        user_id="user-1",
        status=TaskStatus.RUNNING,
        projection_cursor=1,
    )
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_task
    db.execute.return_value = mock_res

    service = RunProjectionUpdaterService(db)

    # Mock httpx responses
    fake_run_resp = MagicMock(status_code=200)
    fake_run_resp.json.return_value = {"status": "COMPLETED"}

    fake_events_resp = MagicMock(status_code=200)
    fake_events_resp.json.return_value = {
        "events": [
            {"event_seq": 1, "event_type": "run.started", "payload": {}},
            {"event_seq": 2, "event_type": "custom.step", "payload": {"step": 1}},
            {"event_seq": 3, "event_type": "run.completed", "payload": {"summary": "done"}},
        ]
    }

    fake_result_resp = MagicMock(status_code=200)
    fake_result_resp.json.return_value = {"content": "output text", "summary": "done"}

    fake_artifacts_resp = MagicMock(status_code=200)
    fake_artifacts_resp.json.return_value = {"artifacts": [{"name": "result.txt"}]}

    async def mock_get(url):
        if url.endswith("/events"):
            return fake_events_resp
        elif url.endswith("/result"):
            return fake_result_resp
        elif url.endswith("/artifacts"):
            return fake_artifacts_resp
        else:
            return fake_run_resp

    mock_client = AsyncMock()
    mock_client.get.side_effect = mock_get
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("httpx.AsyncClient", return_value=mock_client):
        ok = await service.sync_task_projection("task-1", "org-1", "user-1")
        assert ok is True
        assert mock_task.status == TaskStatus.COMPLETED
        assert mock_task.projection_cursor == 3
        assert mock_task.result_content == "output text"
        assert db.add.call_count == 2  # events with seq 2 and 3 added
        assert db.commit.called
