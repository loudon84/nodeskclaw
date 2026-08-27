import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.models.org_membership import OrgMembership, OrgRole
from app.models.organization import Organization
from app.models.user import User
from app.schemas.member import CreateHumanMemberRequest, UpdateMemberProfileRequest
from app.schemas.organization import MemberInfo
from app.services.org_service import (
    _build_member_info,
    create_human_member,
    list_members,
    update_member_profile,
)

TEST_DATABASE_URL = "postgresql+asyncpg://nodeskclaw:nodeskclaw@localhost:5432/nodeskclaw_test"
engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
TestSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def require_test_db():
    try:
        async with engine.connect():
            yield
    except Exception:
        pytest.skip("PostgreSQL test database is not available")


def test_create_human_member_request_accepts_is_task_admin():
    body = CreateHumanMemberRequest(
        name="Task Admin",
        email="task-admin@example.com",
        default_password="password1",
        is_task_admin=True,
    )
    assert body.is_task_admin is True


def test_create_human_member_request_defaults_is_task_admin_false():
    body = CreateHumanMemberRequest(
        name="Regular",
        email="regular@example.com",
        default_password="password1",
    )
    assert body.is_task_admin is False


def test_update_member_profile_request_accepts_is_task_admin():
    body = UpdateMemberProfileRequest(is_task_admin=True)
    assert body.is_task_admin is True


def test_build_member_info_includes_is_task_admin():
    now = datetime.now(timezone.utc)
    membership = OrgMembership(
        id="mem-task-admin",
        user_id="user-task-admin",
        org_id="org-task-admin",
        role=OrgRole.member,
        created_at=now,
    )
    user = User(
        id="user-task-admin",
        name="Task Admin",
        email="task-admin@example.com",
        username="taskadmin",
        is_super_admin=False,
        is_active=True,
        must_change_password=False,
        is_task_admin=True,
    )
    info = _build_member_info(membership, user)
    assert info.is_task_admin is True


def test_member_info_defaults_is_task_admin_false():
    info = MemberInfo(
        id="mem-1",
        user_id="user-1",
        org_id="org-1",
        role="member",
        created_at=datetime.now(timezone.utc),
    )
    assert info.is_task_admin is False


def _ids(prefix: str) -> dict[str, str]:
    suffix = uuid.uuid4().hex[:12]
    return {
        "org": f"{prefix}-org-{suffix}",
        "actor": f"{prefix}-actor-{suffix}",
        "user": f"{prefix}-user-{suffix}",
        "membership": f"{prefix}-mem-{suffix}",
        "email": f"{prefix}-{suffix}@example.com",
        "username": f"{prefix}{suffix}",
    }


@pytest.mark.asyncio
async def test_create_human_member_persists_is_task_admin(require_test_db):
    ids = _ids("cta")
    async with TestSessionLocal() as db:
        org = Organization(id=ids["org"], name="Task Admin Org", slug=ids["org"])
        actor = User(
            id=ids["actor"],
            name="Admin",
            email=f"admin-{ids['email']}",
            username=f"admin-{ids['username']}",
        )
        db.add_all([org, actor])
        await db.commit()

        body = CreateHumanMemberRequest(
            name="Task Admin",
            email=ids["email"],
            username=ids["username"],
            default_password="password1",
            role="member",
            must_change_password=False,
            skill_ids=[],
            is_task_admin=True,
        )

        member = await create_human_member(org.id, body, actor, db)

        assert member.is_task_admin is True


@pytest.mark.asyncio
async def test_create_human_member_defaults_is_task_admin_false(require_test_db):
    ids = _ids("ctd")
    async with TestSessionLocal() as db:
        org = Organization(id=ids["org"], name="Task Admin Default Org", slug=ids["org"])
        actor = User(
            id=ids["actor"],
            name="Admin",
            email=f"admin-{ids['email']}",
            username=f"admin-{ids['username']}",
        )
        db.add_all([org, actor])
        await db.commit()

        body = CreateHumanMemberRequest(
            name="Regular",
            email=ids["email"],
            username=ids["username"],
            default_password="password1",
            role="member",
            must_change_password=False,
            skill_ids=[],
        )

        member = await create_human_member(org.id, body, actor, db)

        assert member.is_task_admin is False


@pytest.mark.asyncio
async def test_update_member_profile_sets_is_task_admin(require_test_db):
    ids = _ids("uta")
    async with TestSessionLocal() as db:
        org = Organization(id=ids["org"], name="Task Admin Update Org", slug=ids["org"])
        user = User(
            id=ids["user"],
            name="Regular",
            email=ids["email"],
            username=ids["username"],
            is_task_admin=False,
        )
        membership = OrgMembership(
            id=ids["membership"],
            user_id=user.id,
            org_id=org.id,
            role=OrgRole.member,
        )
        db.add_all([org, user, membership])
        await db.commit()

        updated = await update_member_profile(
            org.id,
            membership.id,
            UpdateMemberProfileRequest(is_task_admin=True),
            db,
        )

        assert updated.is_task_admin is True


@pytest.mark.asyncio
async def test_list_members_includes_is_task_admin(require_test_db):
    ids = _ids("lta")
    async with TestSessionLocal() as db:
        org = Organization(id=ids["org"], name="Task Admin List Org", slug=ids["org"])
        user = User(
            id=ids["user"],
            name="Task Admin",
            email=ids["email"],
            username=ids["username"],
            is_task_admin=True,
        )
        membership = OrgMembership(
            id=ids["membership"],
            user_id=user.id,
            org_id=org.id,
            role=OrgRole.member,
        )
        db.add_all([org, user, membership])
        await db.commit()

        members = await list_members(org.id, db)

        assert members[0].is_task_admin is True
