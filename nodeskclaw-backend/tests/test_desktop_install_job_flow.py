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
async def install_flow_data(setup_db):
    suffix = uuid4().hex[:8]
    org = Organization(id=f"org-flow-{suffix}", name="Flow Org", slug=f"flow-org-{suffix}")
    user = User(
        id=f"user-flow-{suffix}",
        name="Flow User",
        email=f"flow-{suffix}@example.com",
        username=f"flow-{suffix}",
        password_hash="x",
        current_org_id=org.id,
    )
    gene = Gene(
        id=f"gene-flow-{suffix}",
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
        id=f"ent-flow-{suffix}",
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
    return {"org": org, "user": user, "gene": gene}


async def _setup_profile(client, user, org):
    app.dependency_overrides[get_current_org] = lambda: (user, org)
    device_resp = await client.post(
        "/api/v1/desktop/devices/register",
        json={
            "device_name": "Flow-PC",
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
    return profile_resp.json()["data"]["profile_id"]


@pytest.mark.asyncio
async def test_self_service_install_job_flow(client, install_flow_data, monkeypatch):
    user = install_flow_data["user"]
    org = install_flow_data["org"]
    monkeypatch.setattr("app.services.genehub_bundle_service.settings.GENEHUB_BUNDLE_SIGNATURE_ENABLED", False)

    try:
        profile_id = await _setup_profile(client, user, org)

        create_resp = await client.post(
            "/api/v1/desktop/hermes/install-jobs",
            json={
                "profile_id": profile_id,
                "gene_slug": "contact-to-order",
                "version": "latest",
                "job_type": "install",
            },
        )
        assert create_resp.status_code == 200
        job_id = create_resp.json()["data"]["job_id"]
        assert create_resp.json()["data"]["status"] == "pending"

        pending_resp = await client.get(
            "/api/v1/desktop/hermes/install-jobs/pending",
            params={"profile_id": profile_id},
        )
        assert pending_resp.status_code == 200
        assert any(item["job_id"] == job_id for item in pending_resp.json()["data"])

        claim_resp = await client.post(f"/api/v1/desktop/hermes/install-jobs/{job_id}/claim")
        assert claim_resp.status_code == 200
        assert claim_resp.json()["data"]["status"] == "claimed"

        bundle_resp = await client.get(f"/api/v1/desktop/hermes/install-jobs/{job_id}/bundle")
        assert bundle_resp.status_code == 200
        assert bundle_resp.json()["data"]["schema_version"] == "genehub.bundle.v1"

        status_resp = await client.post(
            f"/api/v1/desktop/hermes/install-jobs/{job_id}/status",
            json={
                "status": "installed",
                "install_path": "~/.hermes/skills/contact-to-order",
                "gene_version": "1.0.0",
                "message": "installed",
            },
        )
        assert status_resp.status_code == 200
        assert status_resp.json()["data"]["status"] == "installed"
    finally:
        app.dependency_overrides.pop(get_current_org, None)
