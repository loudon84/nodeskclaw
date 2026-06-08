from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services import auth_service


class _ScalarResult:
    def __init__(self, value) -> None:
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _SequenceDb:
    def __init__(self, results: list) -> None:
        self._results = list(results)
        self.statements = []

    async def execute(self, stmt):
        self.statements.append(stmt)
        if not self._results:
            raise AssertionError("unexpected database execute")
        return self._results.pop(0)

    async def commit(self):
        return None


def _active_user(**overrides):
    defaults = dict(
        id="user-1",
        name="Alice",
        email="zhangsan@example.com",
        username="zhangsan",
        password_hash="salt$deadbeef",
        is_active=True,
        must_change_password=False,
        oauth_connections=[],
        last_login_at=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.fixture(autouse=True)
def clear_verification_codes():
    auth_service._verification_codes.clear()
    yield
    auth_service._verification_codes.clear()


@pytest.mark.asyncio
async def test_login_with_email_accepts_mixed_case(monkeypatch):
    user = _active_user()
    db = _SequenceDb([_ScalarResult(user)])
    monkeypatch.setattr(auth_service, "_verify_password", lambda *_: True)
    async def fake_issue_tokens(*_):
        return {"ok": True}

    monkeypatch.setattr(auth_service, "_issue_tokens", fake_issue_tokens)

    result = await auth_service.login_with_email("  ZhangSan@Example.com  ", "secret", db)

    assert result == {"ok": True}
    stmt = db.statements[0]
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "lower(users.email)" in compiled.lower()
    assert "zhangsan@example.com" in compiled


@pytest.mark.asyncio
async def test_login_with_account_username_case_insensitive(monkeypatch):
    user = _active_user()
    db = _SequenceDb([_ScalarResult(user)])
    monkeypatch.setattr(auth_service, "_verify_password", lambda *_: True)
    async def fake_issue_tokens(*_):
        return {"ok": True}

    monkeypatch.setattr(auth_service, "_issue_tokens", fake_issue_tokens)

    result = await auth_service.login_with_account(" ZhangSan ", "secret", db)

    assert result == {"ok": True}
    stmt = db.statements[0]
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "lower(users.username)" in compiled.lower()
    assert "zhangsan" in compiled


@pytest.mark.asyncio
async def test_send_verification_code_stores_lowercase_email(monkeypatch):
    async def fake_get_smtp_config(_db, _email):
        return object()

    async def fake_send_email(_email, _code, _config, _db):
        return None

    monkeypatch.setattr(
        "app.services.email_service.get_smtp_config_for_email",
        fake_get_smtp_config,
    )
    monkeypatch.setattr(
        "app.services.email_service.send_verification_email",
        fake_send_email,
    )

    db = SimpleNamespace()
    await auth_service.send_verification_code(" ZhangSan@Example.com ", db)

    assert "zhangsan@example.com" in auth_service._verification_codes
    assert "ZhangSan@Example.com" not in auth_service._verification_codes


@pytest.mark.asyncio
async def test_login_with_verification_code_accepts_mixed_case_email(monkeypatch):
    user = _active_user()
    db = _SequenceDb([_ScalarResult(user)])
    auth_service._verification_codes["zhangsan@example.com"] = ("123456", float("inf"))
    async def fake_issue_tokens(*_):
        return {"ok": True}

    monkeypatch.setattr(auth_service, "_issue_tokens", fake_issue_tokens)

    result = await auth_service.login_with_verification_code(
        " ZHANGSAN@EXAMPLE.COM ",
        "123456",
        db,
    )

    assert result == {"ok": True}
    stmt = db.statements[0]
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "lower(users.email)" in compiled.lower()
    assert "zhangsan@example.com" in compiled


@pytest.fixture
async def require_test_db():
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    test_database_url = "postgresql+asyncpg://nodeskclaw:nodeskclaw@localhost:5432/nodeskclaw_test"
    engine = create_async_engine(test_database_url, echo=False, poolclass=NullPool)
    try:
        async with engine.connect():
            yield
    except Exception:
        pytest.skip("PostgreSQL test database is not available")
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_create_human_member_rejects_case_insensitive_username_duplicate(require_test_db):
    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import NullPool

    from app.core.exceptions import ConflictError
    from app.models.organization import Organization
    from app.models.user import User
    from app.schemas.member import CreateHumanMemberRequest
    from app.services.org_service import create_human_member

    test_database_url = "postgresql+asyncpg://nodeskclaw:nodeskclaw@localhost:5432/nodeskclaw_test"
    engine = create_async_engine(test_database_url, echo=False, poolclass=NullPool)
    session_local = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_local() as db:
        org = Organization(id="org-ci-login", name="CI Login Org", slug="org-ci-login")
        actor = User(
            id="admin-ci-login",
            name="Admin",
            email="admin-ci-login@example.com",
            username="admin-ci-login",
        )
        existing = User(
            id="user-ci-login",
            name="Zhang",
            email="zhang-ci-login@example.com",
            username="zhangsan",
        )
        db.add_all([org, actor, existing])
        await db.commit()

        body = CreateHumanMemberRequest(
            name="Another",
            email="another-ci-login@example.com",
            username="ZhangSan",
            default_password="password1",
            role="member",
            must_change_password=False,
            skill_ids=[],
        )

        with pytest.raises(ConflictError, match="用户名已被占用"):
            await create_human_member(org.id, body, actor, db)

        dup = await db.execute(
            select(User).where(
                func.lower(User.username) == "zhangsan",
                User.deleted_at.is_(None),
            )
        )
        assert dup.scalar_one_or_none() is not None
