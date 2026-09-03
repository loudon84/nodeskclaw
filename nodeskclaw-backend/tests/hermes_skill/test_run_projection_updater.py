import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Any

from fastapi import FastAPI, Header, HTTPException
import httpx
from httpx import ASGITransport
from pydantic import BaseModel, Field

from sqlalchemy.exc import MissingGreenlet

from app.models.hermes_skill.hermes_task import HermesTask, TaskStatus
from app.services.hermes_skill.run_projection_updater_service import (
    RunProjectionUpdaterService,
    RunProjectionWorker,
)


class ArtifactDescriptor(BaseModel):
    artifact_id: str
    name: str
    content_type: str | None = None
    size_bytes: int | None = None
    download_url: str | None = None
    checksum_sha256: str | None = None


class RunEventView(BaseModel):
    event_id: str
    run_id: str
    event_type: str
    event_seq: int
    source: str = "agent"
    source_event_id: str | None = None
    timestamp: str
    payload: dict[str, Any] = Field(default_factory=dict)


class EventsResponse(BaseModel):
    org_id: str
    run_id: str
    items: list[RunEventView] = Field(default_factory=list)
    next_seq: int | None = None


class ResultResponse(BaseModel):
    org_id: str
    run_id: str
    status: str
    result: dict[str, Any] | None = None


class ArtifactsResponse(BaseModel):
    org_id: str
    run_id: str
    items: list[ArtifactDescriptor] = Field(default_factory=list)


class RunView(BaseModel):
    run_id: str
    org_id: str
    user_id: str
    tool_name: str
    status: str
    snapshot: dict[str, Any]
    result: dict[str, Any] | None = None
    attempt_id: str | None = None
    generation: int = 0
    created_at: str
    updated_at: str


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

    mock_agent_app = FastAPI()

    dummy_run = RunView(
        run_id="task-1",
        org_id="org-1",
        user_id="user-1",
        tool_name="demo_tool",
        status="COMPLETED",
        snapshot={},
        result={"content": "output text", "summary": "done"},
        created_at="2026-08-27T00:00:00Z",
        updated_at="2026-08-27T00:00:00Z",
    )
    events_items = [
        RunEventView(
            event_id="e1",
            run_id="task-1",
            event_type="run.started",
            event_seq=1,
            timestamp="2026-08-27T00:00:00Z",
            payload={},
        ),
        RunEventView(
            event_id="e2",
            run_id="task-1",
            event_type="custom.step",
            event_seq=2,
            timestamp="2026-08-27T00:00:01Z",
            payload={"step": 1},
        ),
        RunEventView(
            event_id="e3",
            run_id="task-1",
            event_type="run.completed",
            event_seq=3,
            timestamp="2026-08-27T00:00:02Z",
            payload={"summary": "done"},
        ),
    ]
    artifacts_items = [
        ArtifactDescriptor(
            artifact_id="art-1",
            name="result.txt",
            content_type="text/plain",
            size_bytes=100,
        )
    ]

    @mock_agent_app.get("/internal/v1/runs/{run_id}", response_model=RunView)
    async def get_run_route(run_id: str, x_exec_org_id: str = Header(alias="X-Exec-Org-Id")):
        if x_exec_org_id != "org-1" or run_id != "task-1":
            raise HTTPException(status_code=404, detail="not found")
        return dummy_run

    @mock_agent_app.get("/internal/v1/runs/{run_id}/events", response_model=EventsResponse)
    async def get_events_route(run_id: str, after_seq: int = 0, x_exec_org_id: str = Header(alias="X-Exec-Org-Id")):
        if x_exec_org_id != "org-1" or run_id != "task-1":
            raise HTTPException(status_code=404, detail="not found")
        filtered = [e for e in events_items if e.event_seq > after_seq]
        return EventsResponse(
            org_id="org-1",
            run_id=run_id,
            items=filtered,
            next_seq=filtered[-1].event_seq if filtered else after_seq,
        )

    @mock_agent_app.get("/internal/v1/runs/{run_id}/result", response_model=ResultResponse)
    async def get_result_route(run_id: str, x_exec_org_id: str = Header(alias="X-Exec-Org-Id")):
        if x_exec_org_id != "org-1" or run_id != "task-1":
            raise HTTPException(status_code=404, detail="not found")
        return ResultResponse(
            org_id="org-1",
            run_id=run_id,
            status="COMPLETED",
            result={"content": "output text", "summary": "done"},
        )

    @mock_agent_app.get("/internal/v1/runs/{run_id}/artifacts", response_model=ArtifactsResponse)
    async def get_artifacts_route(run_id: str, x_exec_org_id: str = Header(alias="X-Exec-Org-Id")):
        if x_exec_org_id != "org-1" or run_id != "task-1":
            raise HTTPException(status_code=404, detail="not found")
        return ArtifactsResponse(
            org_id="org-1",
            run_id=run_id,
            items=artifacts_items,
        )

    real_transport = ASGITransport(app=mock_agent_app)
    orig_async_client = httpx.AsyncClient

    def _custom_client(*args, **kwargs):
        kwargs["transport"] = real_transport
        kwargs["base_url"] = "http://testserver"
        return orig_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _custom_client)

    ok = await service.sync_task_projection("task-1", "org-1", "user-1")
    assert ok is True
    assert mock_task.status == TaskStatus.COMPLETED
    assert mock_task.projection_cursor == 3
    assert mock_task.result_content == "output text"
    assert mock_task.result_summary == "done"
    assert mock_task.server_artifacts == [artifacts_items[0].model_dump()]
    assert db.add.call_count == 2  # events with seq 2 and 3 added (seq 1 was <= cursor 1)
    assert db.commit.called


@pytest.mark.asyncio
async def test_sync_task_projection_handles_timed_out(monkeypatch):
    db = AsyncMock()
    mock_task = HermesTask(
        id="task-2",
        org_id="org-1",
        user_id="user-1",
        status=TaskStatus.RUNNING,
        projection_cursor=0,
    )
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_task
    db.execute.return_value = mock_res

    service = RunProjectionUpdaterService(db)

    mock_agent_app = FastAPI()

    timed_out_run = RunView(
        run_id="task-2",
        org_id="org-1",
        user_id="user-1",
        tool_name="demo_tool",
        status="TIMED_OUT",
        snapshot={},
        result=None,
        created_at="2026-08-27T00:00:00Z",
        updated_at="2026-08-27T00:00:00Z",
    )

    @mock_agent_app.get("/internal/v1/runs/{run_id}", response_model=RunView)
    async def get_run_route(run_id: str, x_exec_org_id: str = Header(alias="X-Exec-Org-Id")):
        return timed_out_run

    @mock_agent_app.get("/internal/v1/runs/{run_id}/events", response_model=EventsResponse)
    async def get_events_route(run_id: str, after_seq: int = 0, x_exec_org_id: str = Header(alias="X-Exec-Org-Id")):
        return EventsResponse(org_id="org-1", run_id=run_id, items=[])

    real_transport = ASGITransport(app=mock_agent_app)
    orig_async_client = httpx.AsyncClient

    def _custom_client(*args, **kwargs):
        kwargs["transport"] = real_transport
        kwargs["base_url"] = "http://testserver"
        return orig_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _custom_client)

    ok = await service.sync_task_projection("task-2", "org-1", "user-1")
    assert ok is True
    assert mock_task.status == TaskStatus.FAILED
    assert mock_task.error_code == "errors.skill_run.timed_out"
    assert "timed out" in mock_task.error_message


class _ExpireAfterFirstReadTask:
    def __init__(self, task_id: str, org_id: str, user_id: str):
        self._id = task_id
        self._org_id = org_id
        self._user_id = user_id
        self.expired = False

    def _read(self, value: str) -> str:
        if self.expired:
            raise MissingGreenlet(
                "greenlet_spawn has not been called; can't call await_only() here. "
                "Was IO attempted in an unexpected place?"
            )
        return value

    @property
    def id(self) -> str:
        return self._read(self._id)

    @property
    def org_id(self) -> str:
        return self._read(self._org_id)

    @property
    def user_id(self) -> str:
        return self._read(self._user_id)


@pytest.mark.asyncio
# @lat: [[architecture/backend#C2 Projection Sync#Session Isolation After Commit]]
async def test_run_once_does_not_touch_expired_orm_after_first_sync(monkeypatch):
    task_a = _ExpireAfterFirstReadTask("task-a", "org-1", "user-1")
    task_b = _ExpireAfterFirstReadTask("task-b", "org-1", "user-2")

    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = [task_a, task_b]
    mock_db.execute.return_value = mock_res
    mock_db.__aenter__.return_value = mock_db
    mock_db.__aexit__.return_value = False

    synced: list[tuple[str, str, str | None]] = []

    async def fake_sync(self, task_id, org_id, user_id=None):
        task_a.expired = True
        task_b.expired = True
        synced.append((task_id, org_id, user_id))
        return True

    monkeypatch.setattr(
        "app.services.hermes_skill.run_projection_updater_service.async_session_factory",
        lambda: mock_db,
    )
    monkeypatch.setattr(RunProjectionUpdaterService, "sync_task_projection", fake_sync)

    await RunProjectionWorker()._run_once()

    assert synced == [
        ("task-a", "org-1", "user-1"),
        ("task-b", "org-1", "user-2"),
    ]

