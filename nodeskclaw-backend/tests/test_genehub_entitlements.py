import json
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.deps import get_current_org
from app.core.security import get_current_user
from app.main import app
from app.models.admin_membership import AdminMembership
from app.models.gene import ContentVisibility, Gene, GeneReviewStatus, GeneSource
from app.models.genehub_entitlement import GeneHubEntitlement
from app.models.organization import Organization
from app.models.user import User
from app.services.genehub_service import resolve_user_gene_permissions
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
async def entitlement_data(setup_db):
    suffix = uuid4().hex[:8]
    org = Organization(id=f"org-ent-{suffix}", name="Ent Org", slug=f"ent-org-{suffix}")
    admin = User(
        id=f"admin-ent-{suffix}",
        name="Ent Admin",
        email=f"ent-admin-{suffix}@example.com",
        username=f"ent-admin-{suffix}",
        password_hash="x",
        current_org_id=org.id,
    )
    member = User(
        id=f"user-ent-{suffix}",
        name="Ent Member",
        email=f"ent-user-{suffix}@example.com",
        username=f"ent-user-{suffix}",
        password_hash="x",
        current_org_id=org.id,
    )
    membership = AdminMembership(
        id=f"admin-membership-{suffix}",
        user_id=admin.id,
        org_id=org.id,
        role="admin",
    )
    gene = Gene(
        id=f"gene-ent-{suffix}",
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
        created_by=admin.id,
    )
    try:
        async with TestSessionLocal() as db:
            db.add_all([org, admin, member, membership, gene])
            await db.commit()
    except Exception:
        pytest.skip("test database unavailable")
    return {"org": org, "admin": admin, "member": member, "gene": gene}


@pytest.mark.asyncio
async def test_grant_entitlements_idempotent(client, entitlement_data):
    admin = entitlement_data["admin"]
    org = entitlement_data["org"]
    gene = entitlement_data["gene"]
    member = entitlement_data["member"]

    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[get_current_org] = lambda: (admin, org)
    payload = {
        "gene_id": gene.id,
        "targets": [
            {
                "target_type": "user",
                "target_id": member.id,
                "permissions": ["view", "install"],
                "profile_scope": None,
            }
        ],
    }
    try:
        first = await client.post("/api/v1/admin/genehub/entitlements", json=payload)
        second = await client.post("/api/v1/admin/genehub/entitlements", json=payload)
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["data"]["created"] == 2
        assert second.json()["data"]["created"] == 0
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_current_org, None)


@pytest.mark.asyncio
async def test_resolve_user_gene_permissions(entitlement_data):
    org = entitlement_data["org"]
    member = entitlement_data["member"]
    gene = entitlement_data["gene"]

    async with TestSessionLocal() as db:
        db.add(
            GeneHubEntitlement(
                id=f"ent-{uuid4().hex[:8]}",
                org_id=org.id,
                gene_id=gene.id,
                target_type="user",
                target_id=member.id,
                permission="install",
            )
        )
        await db.commit()

        permissions = await resolve_user_gene_permissions(
            db,
            org_id=org.id,
            user_id=member.id,
            gene_id=gene.id,
        )
        assert "install" in permissions
        assert "view" in permissions

        result = await db.execute(
            select(GeneHubEntitlement).where(GeneHubEntitlement.gene_id == gene.id)
        )
        assert len(result.scalars().all()) >= 1
