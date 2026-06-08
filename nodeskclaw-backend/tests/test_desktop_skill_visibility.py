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

HERMES_MANIFEST = {
    "schema_version": "genehub.gene.v1",
    "slug": "contact-to-order",
    "version": "1.0.0",
    "name": "Contact To Order",
    "compatibility": [{"runtime": "hermes", "target": "desktop"}],
    "skill": {"name": "contact-to-order", "content": "---\nname: contact-to-order\n---\n"},
    "install": {"hermes_desktop": {"skill_dir": "~/.hermes/skills", "scripts_dir": "~/.hermes/scripts", "restart_required": True}},
}

OPENCLAW_MANIFEST = {
    "schema_version": "genehub.gene.v1",
    "slug": "openclaw-only",
    "version": "1.0.0",
    "name": "OpenClaw Only",
    "compatibility": [{"runtime": "openclaw", "target": "instance"}],
    "skill": {"name": "openclaw-only", "content": "---\nname: openclaw-only\n---\n"},
    "install": {"hermes_desktop": {"skill_dir": "~/.hermes/skills", "scripts_dir": "~/.hermes/scripts", "restart_required": True}},
}


@pytest.fixture
async def visibility_data(setup_db):
    suffix = uuid4().hex[:8]
    org = Organization(id=f"org-vis-{suffix}", name="Vis Org", slug=f"vis-org-{suffix}")
    entitled_user = User(
        id=f"user-vis-a-{suffix}",
        name="Entitled User",
        email=f"vis-a-{suffix}@example.com",
        username=f"vis-a-{suffix}",
        password_hash="x",
        current_org_id=org.id,
    )
    other_user = User(
        id=f"user-vis-b-{suffix}",
        name="Other User",
        email=f"vis-b-{suffix}@example.com",
        username=f"vis-b-{suffix}",
        password_hash="x",
        current_org_id=org.id,
    )
    hermes_gene = Gene(
        id=f"gene-vis-hermes-{suffix}",
        name="Contact To Order",
        slug="contact-to-order",
        version="1.0.0",
        manifest=json.dumps(HERMES_MANIFEST),
        source=GeneSource.manual,
        source_registry="local",
        review_status=GeneReviewStatus.approved,
        is_published=True,
        org_id=org.id,
        visibility=ContentVisibility.org_private,
    )
    openclaw_gene = Gene(
        id=f"gene-vis-openclaw-{suffix}",
        name="OpenClaw Only",
        slug="openclaw-only",
        version="1.0.0",
        manifest=json.dumps(OPENCLAW_MANIFEST),
        source=GeneSource.manual,
        source_registry="local",
        review_status=GeneReviewStatus.approved,
        is_published=True,
        org_id=org.id,
        visibility=ContentVisibility.org_private,
    )
    entitlement = GeneHubEntitlement(
        id=f"ent-vis-{suffix}",
        org_id=org.id,
        gene_id=hermes_gene.id,
        target_type="user",
        target_id=entitled_user.id,
        permission="view",
    )
    try:
        async with TestSessionLocal() as db:
            db.add_all([org, entitled_user, other_user, hermes_gene, openclaw_gene, entitlement])
            await db.commit()
    except Exception:
        pytest.skip("test database unavailable")
    return {
        "org": org,
        "entitled_user": entitled_user,
        "other_user": other_user,
        "hermes_gene": hermes_gene,
    }


async def _register_device_and_profile(client, user, org):
    app.dependency_overrides[get_current_org] = lambda: (user, org)
    device_resp = await client.post(
        "/api/v1/desktop/devices/register",
        json={
            "device_name": "Vis-PC",
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
async def test_entitled_user_sees_hermes_desktop_skill(client, visibility_data):
    user = visibility_data["entitled_user"]
    org = visibility_data["org"]
    try:
        profile_id = await _register_device_and_profile(client, user, org)
        response = await client.get(
            "/api/v1/desktop/genehub/skills",
            params={"profile_id": profile_id},
        )
        assert response.status_code == 200
        slugs = [item["slug"] for item in response.json()["data"]]
        assert "contact-to-order" in slugs
        assert "openclaw-only" not in slugs
    finally:
        app.dependency_overrides.pop(get_current_org, None)


@pytest.mark.asyncio
async def test_unentitled_user_sees_no_skills(client, visibility_data):
    user = visibility_data["other_user"]
    org = visibility_data["org"]
    try:
        profile_id = await _register_device_and_profile(client, user, org)
        response = await client.get(
            "/api/v1/desktop/genehub/skills",
            params={"profile_id": profile_id},
        )
        assert response.status_code == 200
        assert response.json()["data"] == []
    finally:
        app.dependency_overrides.pop(get_current_org, None)
