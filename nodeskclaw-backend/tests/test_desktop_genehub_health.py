from uuid import uuid4

import pytest

from app.core.deps import get_current_org
from app.main import app
from app.models.organization import Organization
from app.models.user import User
from tests.conftest import TestSessionLocal


@pytest.fixture
async def health_user_data(setup_db):
    suffix = uuid4().hex[:8]
    org = Organization(id=f"org-gh-h-{suffix}", name="Health Org", slug=f"health-org-{suffix}")
    user = User(
        id=f"user-gh-h-{suffix}",
        name="Health User",
        email=f"health-{suffix}@example.com",
        username=f"health-{suffix}",
        password_hash="x",
        current_org_id=org.id,
    )
    try:
        async with TestSessionLocal() as db:
            db.add_all([org, user])
            await db.commit()
    except Exception:
        pytest.skip("test database unavailable")
    return {"user": user, "org": org}


@pytest.mark.asyncio
async def test_genehub_health_requires_auth(client):
    resp = await client.get("/api/v1/desktop/genehub/health")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_genehub_health_ok_when_authenticated(client, health_user_data):
    user = health_user_data["user"]
    org = health_user_data["org"]
    app.dependency_overrides[get_current_org] = lambda: (user, org)
    try:
        resp = await client.get("/api/v1/desktop/genehub/health")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "ok"
        assert data["genehub_enabled"] is True
        assert data["org_id"] == org.id
        assert data["user_id"] == user.id
    finally:
        app.dependency_overrides.pop(get_current_org, None)


@pytest.mark.asyncio
async def test_genehub_health_disabled(client, health_user_data, monkeypatch):
    monkeypatch.setattr("app.api.desktop_genehub.settings.GENEHUB_DESKTOP_SYNC_ENABLED", False)
    user = health_user_data["user"]
    org = health_user_data["org"]
    app.dependency_overrides[get_current_org] = lambda: (user, org)
    try:
        resp = await client.get("/api/v1/desktop/genehub/health")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "disabled"
        assert data["genehub_enabled"] is False
    finally:
        app.dependency_overrides.pop(get_current_org, None)
