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
async def contract_data(setup_db):
    suffix = uuid4().hex[:8]
    org = Organization(id=f"org-ct-{suffix}", name="Contract Org", slug=f"contract-org-{suffix}")
    user = User(
        id=f"user-ct-{suffix}",
        name="Contract User",
        email=f"contract-{suffix}@example.com",
        username=f"contract-{suffix}",
        password_hash="x",
        current_org_id=org.id,
    )
    gene = Gene(
        id=f"gene-ct-{suffix}",
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
        id=f"ent-ct-{suffix}",
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


async def _register_device(client):
    return await client.post(
        "/api/v1/desktop/devices/register",
        json={
            "device_name": "Contract-PC",
            "device_fingerprint": "fp-contract",
            "os_type": "windows",
        },
    )


@pytest.mark.asyncio
async def test_profile_register_missing_desktop_device_id_returns_422(client, contract_data):
    user = contract_data["user"]
    org = contract_data["org"]
    app.dependency_overrides[get_current_org] = lambda: (user, org)
    try:
        resp = await client.post(
            "/api/v1/desktop/hermes/profiles/register",
            json={
                "profile_name": "default",
                "hermes_home": "C:\\Users\\alice\\.hermes",
            },
        )
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.pop(get_current_org, None)


@pytest.mark.asyncio
async def test_create_install_job_supports_job_type_and_action_alias(client, contract_data, monkeypatch):
    user = contract_data["user"]
    org = contract_data["org"]
    app.dependency_overrides[get_current_org] = lambda: (user, org)
    try:
        device_resp = await _register_device(client)
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

        job_type_resp = await client.post(
            "/api/v1/desktop/hermes/install-jobs",
            json={
                "profile_id": profile_id,
                "gene_slug": "contact-to-order",
                "job_type": "install",
            },
        )
        assert job_type_resp.status_code == 200

        action_resp = await client.post(
            "/api/v1/desktop/hermes/install-jobs",
            json={
                "profile_id": profile_id,
                "gene_slug": "contact-to-order",
                "action": "update",
            },
        )
        assert action_resp.status_code == 200
    finally:
        app.dependency_overrides.pop(get_current_org, None)


@pytest.mark.asyncio
async def test_skill_list_returns_enhanced_fields(client, contract_data):
    user = contract_data["user"]
    org = contract_data["org"]
    app.dependency_overrides[get_current_org] = lambda: (user, org)
    try:
        device_resp = await _register_device(client)
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

        resp = await client.get(
            "/api/v1/desktop/genehub/skills",
            params={"profile_id": profile_id},
        )
        assert resp.status_code == 200
        items = resp.json()["data"]
        assert len(items) >= 1
        skill = next(item for item in items if item["slug"] == "contact-to-order")
        assert skill["gene_slug"] == "contact-to-order"
        assert skill["gene_version"] == "1.0.0"
        assert skill["skill_name"] == "contact-to-order"
        assert skill["display_name"] == "Contact To Order"
        assert skill["installed"] is False
    finally:
        app.dependency_overrides.pop(get_current_org, None)


@pytest.mark.asyncio
async def test_pending_jobs_return_action(client, contract_data):
    user = contract_data["user"]
    org = contract_data["org"]
    app.dependency_overrides[get_current_org] = lambda: (user, org)
    try:
        device_resp = await _register_device(client)
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

        create_resp = await client.post(
            "/api/v1/desktop/hermes/install-jobs",
            json={
                "profile_id": profile_id,
                "gene_slug": "contact-to-order",
                "job_type": "install",
            },
        )
        job_id = create_resp.json()["data"]["job_id"]

        pending_resp = await client.get(
            "/api/v1/desktop/hermes/install-jobs/pending",
            params={"profile_id": profile_id},
        )
        assert pending_resp.status_code == 200
        job = next(item for item in pending_resp.json()["data"] if item["job_id"] == job_id)
        assert job["action"] == "install"
        assert job["job_type"] == "install"
        assert job["profile_id"] == profile_id
    finally:
        app.dependency_overrides.pop(get_current_org, None)


@pytest.mark.asyncio
async def test_status_update_rejects_claimed(client, contract_data):
    user = contract_data["user"]
    org = contract_data["org"]
    app.dependency_overrides[get_current_org] = lambda: (user, org)
    try:
        device_resp = await _register_device(client)
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

        create_resp = await client.post(
            "/api/v1/desktop/hermes/install-jobs",
            json={
                "profile_id": profile_id,
                "gene_slug": "contact-to-order",
                "job_type": "install",
            },
        )
        job_id = create_resp.json()["data"]["job_id"]
        await client.post(f"/api/v1/desktop/hermes/install-jobs/{job_id}/claim")

        status_resp = await client.post(
            f"/api/v1/desktop/hermes/install-jobs/{job_id}/status",
            json={"status": "claimed"},
        )
        assert status_resp.status_code == 422
    finally:
        app.dependency_overrides.pop(get_current_org, None)
