from uuid import uuid4

import pytest

from app.core.deps import get_current_org
from app.main import app
from app.models.organization import Organization
from app.models.user import User
from tests.conftest import TestSessionLocal


@pytest.fixture
async def desktop_user_data(setup_db):
    suffix = uuid4().hex[:8]
    org = Organization(id=f"org-desk-{suffix}", name="Desktop Org", slug=f"desktop-org-{suffix}")
    user = User(
        id=f"user-desk-{suffix}",
        name="Desktop User",
        email=f"desktop-{suffix}@example.com",
        username=f"desktop-{suffix}",
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
async def test_device_register_is_idempotent(client, desktop_user_data):
    user = desktop_user_data["user"]
    org = desktop_user_data["org"]
    app.dependency_overrides[get_current_org] = lambda: (user, org)
    payload = {
        "device_name": "Alice-PC",
        "device_fingerprint": "fp-001",
        "os_type": "windows",
        "os_version": "Windows 11",
        "app_version": "6.5.0",
    }
    try:
        first = await client.post("/api/v1/desktop/devices/register", json=payload)
        second = await client.post("/api/v1/desktop/devices/register", json=payload)
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["data"]["desktop_device_id"] == second.json()["data"]["desktop_device_id"]
    finally:
        app.dependency_overrides.pop(get_current_org, None)


@pytest.mark.asyncio
async def test_profile_register_and_heartbeat(client, desktop_user_data):
    user = desktop_user_data["user"]
    org = desktop_user_data["org"]
    app.dependency_overrides[get_current_org] = lambda: (user, org)
    try:
        device_resp = await client.post(
            "/api/v1/desktop/devices/register",
            json={
                "device_name": "Alice-PC",
                "device_fingerprint": "fp-002",
                "os_type": "windows",
            },
        )
        device_id = device_resp.json()["data"]["desktop_device_id"]

        profile_resp = await client.post(
            "/api/v1/desktop/hermes/profiles/register",
            json={
                "desktop_device_id": device_id,
                "profile_name": "default",
                "hermes_home": "C:\\Users\\alice\\.hermes",
                "runtime_version": "0.12.0",
            },
        )
        assert profile_resp.status_code == 200
        profile_id = profile_resp.json()["data"]["profile_id"]

        heartbeat_resp = await client.post(
            "/api/v1/desktop/heartbeat",
            json={
                "desktop_device_id": device_id,
                "profiles": [{"profile_id": profile_id, "profile_name": "default", "status": "active"}],
            },
        )
        assert heartbeat_resp.status_code == 200
        assert heartbeat_resp.json()["data"]["genehub_enabled"] is True
    finally:
        app.dependency_overrides.pop(get_current_org, None)
