from uuid import uuid4

import pytest

from app.core.deps import get_current_org
from app.core.security import get_current_user
from app.main import app
from app.models.admin_membership import AdminMembership
from app.models.organization import Organization
from app.models.user import User
from tests.conftest import TestSessionLocal

SKILL_CONTENT = "---\nname: contact-to-order\ndescription: test\n---\n\n# Skill\n"
COMPATIBILITY = [{"runtime": "hermes", "target": "desktop", "min_version": "0.9.0"}]


@pytest.fixture
async def genehub_admin_data(setup_db):
    suffix = uuid4().hex[:8]
    org = Organization(id=f"org-gh-{suffix}", name="GeneHub Org", slug=f"genehub-org-{suffix}")
    user = User(
        id=f"user-gh-{suffix}",
        name="GeneHub Admin",
        email=f"genehub-{suffix}@example.com",
        username=f"genehub-{suffix}",
        password_hash="x",
        current_org_id=org.id,
    )
    membership = AdminMembership(
        id=f"admin-gh-{suffix}",
        user_id=user.id,
        org_id=org.id,
        role="admin",
    )
    try:
        async with TestSessionLocal() as db:
            db.add_all([org, user, membership])
            await db.commit()
    except Exception:
        pytest.skip("test database unavailable")
    return {"user": user, "org": org}


def _skill_payload(slug: str = "contact-to-order") -> dict:
    return {
        "name": "Contact To Order",
        "slug": slug,
        "description": "Convert contact/order files",
        "short_description": "Contact parser",
        "category": "business",
        "tags": ["hermes", "order"],
        "version": "1.0.0",
        "skill_content": SKILL_CONTENT,
        "scripts": {},
        "compatibility": COMPATIBILITY,
        "visibility": "org_private",
        "is_published": False,
    }


@pytest.mark.asyncio
async def test_admin_create_review_publish_flow(client, genehub_admin_data):
    user = genehub_admin_data["user"]
    org = genehub_admin_data["org"]
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_org] = lambda: (user, org)
    try:
        create_resp = await client.post("/api/v1/admin/genehub/skills", json=_skill_payload())
        assert create_resp.status_code == 200
        gene_id = create_resp.json()["data"]["id"]
        assert create_resp.json()["data"]["review_status"] == "pending_admin"
        assert create_resp.json()["data"]["is_published"] is False

        review_resp = await client.put(
            f"/api/v1/admin/genehub/skills/{gene_id}/review",
            json={"action": "approve", "reason": "ok"},
        )
        assert review_resp.status_code == 200
        assert review_resp.json()["data"]["review_status"] == "approved"

        publish_resp = await client.post(f"/api/v1/admin/genehub/skills/{gene_id}/publish")
        assert publish_resp.status_code == 200
        assert publish_resp.json()["data"]["is_published"] is True

        update_resp = await client.put(
            f"/api/v1/admin/genehub/skills/{gene_id}",
            json={"description": "updated"},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["data"]["is_published"] is False
        assert update_resp.json()["data"]["review_status"] == "pending_admin"
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_current_org, None)
