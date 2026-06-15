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
    "skill": {"name": "contact-to-order", "content": "---\nname: contact-to-order\n---\nbody"},
    "install": {"hermes_desktop": {"skill_dir": "~/.hermes/skills", "scripts_dir": "~/.hermes/scripts", "restart_required": True}},
}


@pytest.fixture
async def preview_flow_data(setup_db):
    suffix = uuid4().hex[:8]
    org = Organization(id=f"org-prev-{suffix}", name="Preview Org", slug=f"preview-org-{suffix}")
    user = User(
        id=f"user-prev-{suffix}",
        name="Preview User",
        email=f"preview-{suffix}@example.com",
        username=f"preview-{suffix}",
        password_hash="x",
        current_org_id=org.id,
    )
    gene = Gene(
        id=f"gene-prev-{suffix}",
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
        id=f"ent-prev-{suffix}",
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


async def _setup_profile(client, user, org):
    app.dependency_overrides[get_current_org] = lambda: (user, org)
    device_resp = await client.post(
        "/api/v1/desktop/devices/register",
        json={
            "device_name": "Preview-PC",
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
    return profile_resp.json()["data"]["profile_id"], device_id


@pytest.mark.asyncio
async def test_bundle_preview_pending_without_content(client, preview_flow_data, monkeypatch):
    user = preview_flow_data["user"]
    org = preview_flow_data["org"]
    monkeypatch.setattr("app.services.genehub_bundle_service.settings.GENEHUB_BUNDLE_SIGNATURE_ENABLED", False)

    try:
        profile_id, _ = await _setup_profile(client, user, org)

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

        preview_resp = await client.get(
            f"/api/v1/desktop/hermes/install-jobs/{job_id}/bundle-preview"
        )
        assert preview_resp.status_code == 200
        preview = preview_resp.json()["data"]
        assert preview["job_id"] == job_id
        assert preview["gene_slug"] == "contact-to-order"
        assert preview["files"]
        assert "content" not in preview["files"][0]
        assert preview["validation_preview"]["has_skill"] is True

        detail_resp = await client.get(f"/api/v1/desktop/hermes/install-jobs/{job_id}")
        assert detail_resp.json()["data"]["status"] == "pending"
    finally:
        app.dependency_overrides.pop(get_current_org, None)
