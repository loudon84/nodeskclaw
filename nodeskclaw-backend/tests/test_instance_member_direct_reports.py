from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.core.exceptions import NotFoundError
from app.models.org_membership import OrgMembership, OrgRole
from app.models.organization import Organization
from app.models.user import User
from app.services import auth_service, org_service

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


async def _seed_subordinates_fixture(db: AsyncSession):
    org = Organization(id="org-subordinates", name="Subordinates Org", slug="org-subordinates")
    supervisor_user = User(
        id="user-supervisor",
        name="Supervisor",
        username="supervisor",
        email="supervisor@example.com",
    )
    report_a = User(
        id="user-report-a",
        name="Alice Report",
        username="alice",
        email="alice@example.com",
    )
    report_b = User(
        id="user-report-b",
        name="Bob Report",
        username="bob",
        email="bob@example.com",
    )
    deleted_report = User(
        id="user-report-deleted",
        name="Deleted Report",
        username="deleted",
        email="deleted@example.com",
        deleted_at=datetime.now(timezone.utc),
    )
    supervisor_membership = OrgMembership(
        id="membership-supervisor",
        user_id=supervisor_user.id,
        org_id=org.id,
        role=OrgRole.member,
    )
    report_a_membership = OrgMembership(
        id="membership-report-a",
        user_id=report_a.id,
        org_id=org.id,
        role=OrgRole.member,
        supervisor_membership_id=supervisor_membership.id,
    )
    report_b_membership = OrgMembership(
        id="membership-report-b",
        user_id=report_b.id,
        org_id=org.id,
        role=OrgRole.member,
        supervisor_membership_id=supervisor_membership.id,
    )
    deleted_report_membership = OrgMembership(
        id="membership-report-deleted",
        user_id=deleted_report.id,
        org_id=org.id,
        role=OrgRole.member,
        supervisor_membership_id=supervisor_membership.id,
    )
    db.add_all([
        org,
        supervisor_user,
        report_a,
        report_b,
        deleted_report,
        supervisor_membership,
        report_a_membership,
        report_b_membership,
        deleted_report_membership,
    ])
    await db.commit()
    return supervisor_user


@pytest.mark.asyncio
async def test_list_subordinates_returns_reports(require_test_db):
    async with TestSessionLocal() as db:
        supervisor = await _seed_subordinates_fixture(db)

        reports = await org_service.list_subordinates(supervisor.id, db)

        assert [item["id"] for item in reports] == [
            "user-report-a",
            "user-report-b",
            "user-supervisor",
        ]
        assert reports[0] == {
            "id": "user-report-a",
            "name": "Alice Report",
            "email": "alice@example.com",
            "username": "alice",
            "is_active": True,
        }


@pytest.mark.asyncio
async def test_list_subordinates_returns_empty_when_no_reports(require_test_db):
    async with TestSessionLocal() as db:
        org = Organization(id="org-no-subordinates", name="No Sub Org", slug="org-no-subordinates")
        lone_user = User(id="user-lone", name="Lone", username="lone")
        lone_membership = OrgMembership(
            id="membership-lone",
            user_id=lone_user.id,
            org_id=org.id,
            role=OrgRole.member,
        )
        db.add_all([org, lone_user, lone_membership])
        await db.commit()

        reports = await org_service.list_subordinates(lone_user.id, db)

        assert [item["id"] for item in reports] == ["user-lone"]
        assert reports[0]["is_active"] is True


@pytest.mark.asyncio
async def test_list_subordinates_raises_when_user_not_found(require_test_db):
    async with TestSessionLocal() as db:
        with pytest.raises(NotFoundError, match="用户不存在"):
            await org_service.list_subordinates("missing-user", db)


@pytest.mark.asyncio
async def test_list_subordinates_excludes_soft_deleted_users(require_test_db):
    async with TestSessionLocal() as db:
        supervisor = await _seed_subordinates_fixture(db)

        reports = await org_service.list_subordinates(supervisor.id, db)

        assert "user-report-deleted" not in {item["id"] for item in reports}


def test_direct_report_payload_includes_is_active():
    user = User(
        id="u-payload-inactive",
        name="Inactive",
        email="inactive@example.com",
        username="inactive",
        is_active=False,
        is_super_admin=False,
        is_task_admin=False,
        must_change_password=False,
    )
    payload = org_service._direct_report_payload(user)
    assert payload == {
        "id": "u-payload-inactive",
        "name": "Inactive",
        "email": "inactive@example.com",
        "username": "inactive",
        "is_active": False,
    }


@pytest.mark.asyncio
async def test_list_subordinates_task_admin_returns_all_users(require_test_db):
    suffix = uuid.uuid4().hex[:12]
    async with TestSessionLocal() as db:
        admin = User(
            id=f"ta-admin-{suffix}",
            name="Task Admin All",
            username=f"taadmin{suffix}",
            email=f"taadmin-{suffix}@example.com",
            is_task_admin=True,
            is_active=True,
        )
        outsider = User(
            id=f"ta-out-{suffix}",
            name="Outsider",
            username=f"taout{suffix}",
            email=f"taout-{suffix}@example.com",
            is_active=False,
        )
        db.add_all([admin, outsider])
        await db.commit()

        reports = await org_service.list_subordinates(admin.id, db)
        ids = {item["id"] for item in reports}

        assert admin.id in ids
        assert outsider.id in ids
        outsider_row = next(item for item in reports if item["id"] == outsider.id)
        assert outsider_row["is_active"] is False


@pytest.mark.asyncio
async def test_list_subordinates_super_admin_returns_all_users(require_test_db):
    suffix = uuid.uuid4().hex[:12]
    async with TestSessionLocal() as db:
        admin = User(
            id=f"sa-admin-{suffix}",
            name="Super Admin All",
            username=f"saadmin{suffix}",
            email=f"saadmin-{suffix}@example.com",
            is_super_admin=True,
            is_active=True,
        )
        outsider = User(
            id=f"sa-out-{suffix}",
            name="Super Outsider",
            username=f"saout{suffix}",
            email=f"saout-{suffix}@example.com",
            is_active=True,
        )
        db.add_all([admin, outsider])
        await db.commit()

        reports = await org_service.list_subordinates(admin.id, db)
        ids = {item["id"] for item in reports}

        assert admin.id in ids
        assert outsider.id in ids


@pytest.mark.asyncio
async def test_build_user_info_includes_is_task_admin(require_test_db):
    async with TestSessionLocal() as db:
        user = User(
            id="user-task-admin",
            name="Task Admin",
            username="taskadmin",
            is_task_admin=True,
        )
        db.add(user)
        await db.commit()

        info = await auth_service._build_user_info(user, db)

        assert info.is_task_admin is True


@pytest.mark.asyncio
async def test_build_user_info_defaults_is_task_admin_false(require_test_db):
    async with TestSessionLocal() as db:
        user = User(
            id="user-not-task-admin",
            name="Regular User",
            username="regular",
        )
        db.add(user)
        await db.commit()

        info = await auth_service._build_user_info(user, db)

        assert info.is_task_admin is False
