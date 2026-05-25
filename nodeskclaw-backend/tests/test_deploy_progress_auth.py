from collections.abc import AsyncGenerator
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api import deploy as admin_deploy_api
from app.api.portal import deploy as portal_deploy_api
from app.core.deps import get_db
from app.core.exceptions import ForbiddenError, NotFoundError, register_exception_handlers
from app.core.security import get_current_user
from app.schemas.deploy import DeployProgress
from app.services.k8s.event_bus import SSEEvent


def _make_app(router, prefix: str) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router, prefix=prefix)
    return app


async def _override_db() -> AsyncGenerator[SimpleNamespace, None]:
    yield SimpleNamespace()


def _user(**kwargs):
    return SimpleNamespace(
        id=kwargs.get("id", "user-1"),
        current_org_id=kwargs.get("current_org_id", "org-1"),
        is_active=True,
        must_change_password=False,
    )


def _success_snapshot(deploy_id: str = "deploy-1") -> DeployProgress:
    return DeployProgress(
        deploy_id=deploy_id,
        step=1,
        total_steps=1,
        current_step="完成",
        status="success",
        message="部署成功",
        percent=100,
        step_names=["完成"],
    )


@pytest.mark.asyncio
async def test_portal_progress_requires_auth(monkeypatch):
    app = _make_app(portal_deploy_api.router, "/deploy")
    called = False

    async def fail_if_called(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("access check should not run without auth")

    monkeypatch.setattr(
        portal_deploy_api.deploy_service,
        "require_deploy_progress_instance_access",
        fail_if_called,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/deploy/progress/deploy-1")

    assert response.status_code == 401
    assert called is False


@pytest.mark.asyncio
async def test_portal_progress_denies_user_without_instance_access(monkeypatch):
    app = _make_app(portal_deploy_api.router, "/deploy")
    app.dependency_overrides[get_current_user] = lambda: _user()
    app.dependency_overrides[get_db] = _override_db
    snapshot_called = False

    async def deny_access(*_args, **_kwargs):
        raise ForbiddenError("您没有该实例的访问权限", "errors.instance.no_access")

    async def fail_snapshot(*_args, **_kwargs):
        nonlocal snapshot_called
        snapshot_called = True
        return _success_snapshot()

    monkeypatch.setattr(
        portal_deploy_api.deploy_service,
        "require_deploy_progress_instance_access",
        deny_access,
    )
    monkeypatch.setattr(
        portal_deploy_api.deploy_service,
        "get_deploy_progress_snapshot",
        fail_snapshot,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/deploy/progress/deploy-1")

    assert response.status_code == 403
    assert snapshot_called is False


@pytest.mark.asyncio
async def test_portal_progress_replays_snapshot_for_viewer(monkeypatch):
    app = _make_app(portal_deploy_api.router, "/deploy")
    app.dependency_overrides[get_current_user] = lambda: _user()
    app.dependency_overrides[get_db] = _override_db

    async def allow_access(deploy_id, _db, user):
        assert deploy_id == "deploy-1"
        assert user.id == "user-1"
        return "instance-1"

    async def get_snapshot(deploy_id, _db):
        return _success_snapshot(deploy_id)

    monkeypatch.setattr(
        portal_deploy_api.deploy_service,
        "require_deploy_progress_instance_access",
        allow_access,
    )
    monkeypatch.setattr(
        portal_deploy_api.deploy_service,
        "get_deploy_progress_snapshot",
        get_snapshot,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/deploy/progress/deploy-1")

    assert response.status_code == 200
    assert "event: deploy_progress" in response.text
    assert '"status": "success"' in response.text


@pytest.mark.asyncio
async def test_admin_progress_returns_not_found_for_other_org(monkeypatch):
    app = _make_app(admin_deploy_api.router, "/admin/deploy")
    app.dependency_overrides[get_current_user] = lambda: _user(current_org_id="org-1")
    app.dependency_overrides[get_db] = _override_db
    snapshot_called = False

    async def deny_org_access(*_args, **_kwargs):
        raise NotFoundError("部署记录不存在", "errors.common.not_found")

    async def fail_snapshot(*_args, **_kwargs):
        nonlocal snapshot_called
        snapshot_called = True
        return _success_snapshot()

    monkeypatch.setattr(
        admin_deploy_api.deploy_service,
        "require_deploy_progress_org_access",
        deny_org_access,
    )
    monkeypatch.setattr(
        admin_deploy_api.deploy_service,
        "get_deploy_progress_snapshot",
        fail_snapshot,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/admin/deploy/progress/deploy-1")

    assert response.status_code == 404
    assert snapshot_called is False


@pytest.mark.asyncio
async def test_admin_progress_replays_snapshot_for_same_org(monkeypatch):
    app = _make_app(admin_deploy_api.router, "/admin/deploy")
    app.dependency_overrides[get_current_user] = lambda: _user(current_org_id="org-1")
    app.dependency_overrides[get_db] = _override_db

    async def allow_org_access(deploy_id, _db, org_id):
        assert deploy_id == "deploy-1"
        assert org_id == "org-1"
        return "instance-1"

    async def get_snapshot(deploy_id, _db):
        return _success_snapshot(deploy_id)

    monkeypatch.setattr(
        admin_deploy_api.deploy_service,
        "require_deploy_progress_org_access",
        allow_org_access,
    )
    monkeypatch.setattr(
        admin_deploy_api.deploy_service,
        "get_deploy_progress_snapshot",
        get_snapshot,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/admin/deploy/progress/deploy-1")

    assert response.status_code == 200
    assert "event: deploy_progress" in response.text
    assert '"status": "success"' in response.text


@pytest.mark.asyncio
async def test_progress_stream_subscribes_after_access_check_for_running_record(monkeypatch):
    app = _make_app(portal_deploy_api.router, "/deploy")
    app.dependency_overrides[get_current_user] = lambda: _user()
    app.dependency_overrides[get_db] = _override_db

    async def allow_access(*_args, **_kwargs):
        return "instance-1"

    async def no_snapshot(*_args, **_kwargs):
        return None

    async def subscribe(_topic):
        yield SSEEvent(
            event="deploy_progress",
            data={
                "deploy_id": "deploy-1",
                "step": 1,
                "total_steps": 1,
                "current_step": "完成",
                "status": "success",
                "message": "部署成功",
                "percent": 100,
            },
        )

    monkeypatch.setattr(
        portal_deploy_api.deploy_service,
        "require_deploy_progress_instance_access",
        allow_access,
    )
    monkeypatch.setattr(
        portal_deploy_api.deploy_service,
        "get_deploy_progress_snapshot",
        no_snapshot,
    )
    monkeypatch.setattr(portal_deploy_api.event_bus, "subscribe", subscribe)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/deploy/progress/deploy-1")

    assert response.status_code == 200
    assert "event: deploy_progress" in response.text
    assert '"deploy_id": "deploy-1"' in response.text
