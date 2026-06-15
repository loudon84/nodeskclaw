import json
from uuid import uuid4

import pytest

from app.core.deps import get_current_org
from app.main import app
from app.models.gene import ContentVisibility, Gene, GeneReviewStatus, GeneSource
from app.models.genehub_entitlement import GeneHubEntitlement
from app.models.organization import Organization
from app.models.user import User
from app.services import genehub_service
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
async def pending_schema_data(setup_db):
    suffix = uuid4().hex[:8]
    org = Organization(id=f"org-pend-{suffix}", name="Pending Org", slug=f"pending-org-{suffix}")
    user = User(
        id=f"user-pend-{suffix}",
        name="Pending User",
        email=f"pending-{suffix}@example.com",
        username=f"pending-{suffix}",
        password_hash="x",
        current_org_id=org.id,
    )
    gene = Gene(
        id=f"gene-pend-{suffix}",
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
        id=f"ent-pend-{suffix}",
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
async def test_pending_jobs_return_mcp_agent_request_fields(client, pending_schema_data):
    user = pending_schema_data["user"]
    org = pending_schema_data["org"]
    app.dependency_overrides[get_current_org] = lambda: (user, org)
    try:
        device_resp = await client.post(
            "/api/v1/desktop/devices/register",
            json={
                "device_name": "Pending-PC",
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

        async with TestSessionLocal() as db:
            result = await genehub_service.create_mcp_registration_job(
                db,
                org_id=org.id,
                user_id=user.id,
                profile_id=profile_id,
                gene_slug="contact-to-order",
            )
            await db.commit()
            job_id = result.job_id

        pending_resp = await client.get(
            "/api/v1/desktop/hermes/install-jobs/pending",
            params={"profile_id": profile_id},
        )
        assert pending_resp.status_code == 200
        job = next(item for item in pending_resp.json()["data"] if item["job_id"] == job_id)
        assert job["source"] == "mcp_agent_request"
        assert job["profile_id"] == profile_id
        assert job["profile_name"] == "default"
        assert job["requested_by"] == user.id
        assert job["created_at"] is not None
        assert job["assigned_at"] is not None
    finally:
        app.dependency_overrides.pop(get_current_org, None)
