import asyncio
from collections.abc import AsyncGenerator
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api import workspace_deploys as workspace_deploys_api
from app.core.deps import get_current_org, get_db
from app.services.k8s.event_bus import SSEEvent


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(workspace_deploys_api.router, prefix="/workspaces")
    return app


def _org_ctx():
    return SimpleNamespace(id="user-1"), SimpleNamespace(id="org-1")


def _terminal_deploy():
    return SimpleNamespace(
        id="deploy-1",
        status="success",
        completed_agents=1,
        failed_agents=0,
        progress_detail={
            "agents": [
                {
                    "display_name": "Agent A",
                    "status": "success",
                    "error": None,
                }
            ]
        },
    )


def _running_deploy():
    return SimpleNamespace(
        id="deploy-1",
        status="deploying",
        completed_agents=0,
        failed_agents=0,
        progress_detail={},
    )


@pytest.mark.asyncio
async def test_workspace_deploy_progress_replays_terminal_snapshot_after_subscription(monkeypatch):
    app = _make_app()
    fake_db = SimpleNamespace(calls=0)
    calls: list[str] = []
    queue: asyncio.Queue[SSEEvent] = asyncio.Queue()

    async def execute(_stmt):
        fake_db.calls += 1
        if fake_db.calls == 1:
            calls.append("access_query")
            return _Result("deploy-1")
        calls.append("snapshot_query")
        return _Result(_terminal_deploy())

    async def override_db() -> AsyncGenerator[SimpleNamespace, None]:
        yield fake_db

    def create_subscription(*topics):
        assert topics == ("workspace_deploy_progress",)
        calls.append("subscribe")

        def cleanup():
            calls.append("cleanup")

        return queue, cleanup

    fake_db.execute = execute
    app.dependency_overrides[get_current_org] = _org_ctx
    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(workspace_deploys_api.event_bus, "create_subscription", create_subscription)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/workspaces/deploys/deploy-1/progress")

    assert response.status_code == 200
    assert '"event": "agent_progress"' in response.text
    assert '"event": "complete"' in response.text
    assert '"status": "success"' in response.text
    assert calls == ["access_query", "subscribe", "snapshot_query", "cleanup"]


@pytest.mark.asyncio
async def test_workspace_deploy_progress_keeps_complete_event_published_during_snapshot_check(monkeypatch):
    app = _make_app()
    fake_db = SimpleNamespace(calls=0)
    calls: list[str] = []
    queue: asyncio.Queue[SSEEvent] = asyncio.Queue()

    async def execute(_stmt):
        fake_db.calls += 1
        if fake_db.calls == 1:
            calls.append("access_query")
            return _Result("deploy-1")
        calls.append("snapshot_query")
        queue.put_nowait(
            SSEEvent(
                event="workspace_deploy_progress",
                data={
                    "workspace_deploy_id": "deploy-1",
                    "event": "complete",
                    "status": "success",
                    "success_count": 1,
                    "failed_count": 0,
                },
            )
        )
        return _Result(_running_deploy())

    async def override_db() -> AsyncGenerator[SimpleNamespace, None]:
        yield fake_db

    def create_subscription(*topics):
        assert topics == ("workspace_deploy_progress",)
        calls.append("subscribe")

        def cleanup():
            calls.append("cleanup")

        return queue, cleanup

    fake_db.execute = execute
    app.dependency_overrides[get_current_org] = _org_ctx
    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(workspace_deploys_api.event_bus, "create_subscription", create_subscription)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/workspaces/deploys/deploy-1/progress")

    assert response.status_code == 200
    assert "event: workspace_deploy_progress" in response.text
    assert '"event": "complete"' in response.text
    assert '"status": "success"' in response.text
    assert calls == ["access_query", "subscribe", "snapshot_query", "cleanup"]
