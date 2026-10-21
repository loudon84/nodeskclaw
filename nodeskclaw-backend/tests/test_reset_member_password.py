import uuid

import pytest
from pydantic import ValidationError

from app.schemas.organization import ResetPasswordRequest
from app.services.auth_service import _verify_password, admin_reset_password


@pytest.fixture
async def require_test_db():
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(
        "postgresql+asyncpg://nodeskclaw:nodeskclaw@localhost:5432/nodeskclaw_test",
        echo=False,
    )
    try:
        async with engine.connect():
            yield
    except Exception:
        pytest.skip("PostgreSQL test database is not available")
    finally:
        await engine.dispose()


# @lat: [[architecture/portal#Page Domains]]
def test_reset_password_request_accepts_custom_password():
    body = ResetPasswordRequest(password="custom-pass")
    assert body.password == "custom-pass"


# @lat: [[architecture/portal#Page Domains]]
def test_reset_password_request_password_optional():
    body = ResetPasswordRequest()
    assert body.password is None


# @lat: [[architecture/portal#Page Domains]]
def test_reset_password_request_rejects_short_password():
    with pytest.raises(ValidationError):
        ResetPasswordRequest(password="12345")


@pytest.mark.asyncio
async def test_admin_reset_password_uses_provided_password(require_test_db):
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import NullPool

    from app.models.user import User

    engine = create_async_engine(
        "postgresql+asyncpg://nodeskclaw:nodeskclaw@localhost:5432/nodeskclaw_test",
        echo=False,
        poolclass=NullPool,
    )
    session_local = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    suffix = uuid.uuid4().hex[:12]
    user_id = f"reset-pwd-{suffix}"
    async with session_local() as db:
        user = User(
            id=user_id,
            name="Reset Target",
            email=f"reset-{suffix}@example.com",
            username=f"reset{suffix}",
            is_active=True,
        )
        db.add(user)
        await db.commit()

        plain = await admin_reset_password(user_id, db, password="HandEdit#2026")
        assert plain == "HandEdit#2026"

        saved = (await db.get(User, user_id))
        assert saved is not None
        assert _verify_password("HandEdit#2026", saved.password_hash)
