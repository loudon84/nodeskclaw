import json
from uuid import uuid4

import pytest

from app.core.deps import get_current_org
from app.main import app
from app.models.gene import ContentVisibility, Gene, GeneReviewStatus, GeneSource
from app.models.genehub_entitlement import GeneHubEntitlement
from app.models.organization import Organization
from app.models.user import User
from tests.conftest import TestSessionLocal

MANIFEST = {
    "schema_version": "genehub.gene.v1",
    "slug": "contact-to-order",
    "version": "1.0.0",
    "name": "Contact To Order",
    "compatibility": [{"runtime": "hermes", "target": "desktop"}],
    "skill": {"name": "contact-to-order", "content": "---\nname: contact-to-order\n---\n"},
    "install": {"hermes_desktop": {"skill_dir": "~/.hermes/skills", "scripts_dir": "~/.hermes/scripts", "restart_required": True}},
}


@pytest.fixture
async def sync_flow_data(setup_db):
    suffix = uuid4().hex[:8]
    org = Organization(id=f"org-sync-{suffix}", name="Sync Org", slug=f"sync-org-{suffix}")
    user = User(
        id=f"user-sync-{suffix}",
        name="Sync User",
        email=f"sync-{suffix}@example.com",
        username=f"sync-{suffix}",
        password_hash="x",
        current_org_id=org.id,
    )
    gene = Gene(
        id=f"gene-sync-{suffix}",
        name="Contact To Order",
        slug="contact-to-order",
        version="1.0.0",
        manifest=json.dumps(MANIFEST),
        source=GeneSource.manual,
        source_registry="local",
        review_status=GeneReviewStatus.approved,
        is_published=True,
        org_id=org.id,
        visibility=ContentVisibility.org_private,
    )
    entitlement = GeneHubEntitlement(
        id=f"ent-sync-{suffix}",
        org_id=org.id,
        gene_id=gene.id,
        target_type="user",
        target_id=user.id,
        permission="install",
    )
    try:
        async with TestSessionLocal() as db:
            db.add_all([org, user, gene, entitlement])
            await db.commit()
    except Exception:
        pytest.skip("test database unavailable")
    return {"org": org, "user": user}


@pytest.mark.asyncio
async def test_sync_rejects_unknown_profile_id(client, sync_flow_data):
    user = sync_flow_data["user"]
    org = sync_flow_data["org"]
    app.dependency_overrides[get_current_org] = lambda: (user, org)
    try:
        resp = await client.post(
            "/api/v1/desktop/hermes/installed-skills/sync",
            json={
                "profile_id": "local-profile-id",
                "skills": [],
            },
        )
        assert resp.status_code == 404
        assert resp.json()["error_code"] == "errors.desktop.profile_not_found"
    finally:
        app.dependency_overrides.pop(get_current_org, None)


@pytest.mark.asyncio
async def test_sync_rejects_mismatched_device_id(client, sync_flow_data):
    user = sync_flow_data["user"]
    org = sync_flow_data["org"]
    app.dependency_overrides[get_current_org] = lambda: (user, org)
    try:
        device_resp = await client.post(
            "/api/v1/desktop/devices/register",
            json={
                "device_name": "Sync-PC",
                "device_fingerprint": f"fp-{user.id}",
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
            },
        )
        profile_id = profile_resp.json()["data"]["profile_id"]

        resp = await client.post(
            "/api/v1/desktop/hermes/installed-skills/sync",
            json={
                "profile_id": profile_id,
                "device_id": "other-device-id",
                "skills": [],
            },
        )
        assert resp.status_code == 403
        assert resp.json()["error_code"] == "errors.desktop.profile_forbidden"
    finally:
        app.dependency_overrides.pop(get_current_org, None)
