"""Casdoor desktop login against a fake identity provider."""

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import casdoor_auth
from app.core import hooks
from app.core.config import settings
from app.core.deps import get_db
from app.core.exceptions import register_exception_handlers
from app.core.security import get_current_user
from app.models.identity_binding import IdentityBinding
from app.models.oauth_login_transaction import OAuthLoginTransaction
from app.models.user import User
from app.schemas.auth import LoginResponse, UserInfo
from app.services.identity.casdoor_client import CasdoorClient
from app.services.identity.binding_service import (
    ACCOUNT_DISABLED,
    BINDING_CONFLICT,
    DOMAIN_NOT_ALLOWED,
    EMAIL_MISSING,
    EMAIL_UNVERIFIED,
    IDP_FAILED,
    LOGIN_EXPIRED,
    MEMBER_NOT_FOUND,
    ORG_MISSING,
)

RETURN_TO = "http://127.0.0.1:9/callback"


class _Idp:
    def __init__(self) -> None:
        self.profile: dict = {
            "sub": "user-1",
            "owner": "built-in",
            "email": "member@example.com",
            "email_verified": True,
        }
        self.calls: list[str] = []
        self.fail_token = False

    def transport(self) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            self.calls.append(str(request.url))
            path = request.url.path
            if path.endswith("/.well-known/openid-configuration"):
                return httpx.Response(
                    200,
                    json={
                        "authorization_endpoint": "https://idp.example/authorize",
                        "token_endpoint": "https://idp.example/token",
                        "userinfo_endpoint": "https://idp.example/userinfo",
                    },
                )
            if path.endswith("/token"):
                if self.fail_token:
                    return httpx.Response(400, json={"error": "invalid_grant"})
                body = request.content.decode()
                assert "grant_type=authorization_code" in body
                assert "client_secret=secret" in body
                assert "code_verifier=" in body
                assert "redirect_uri=" in body
                assert "authorization" not in {key.lower() for key in request.headers}
                return httpx.Response(200, json={"access_token": "casdoor-access"})
            if path.endswith("/userinfo"):
                assert request.headers["authorization"] == "Bearer casdoor-access"
                return httpx.Response(200, json=self.profile)
            return httpx.Response(404)
        return httpx.MockTransport(handler)


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(User.__table__.create)
        await conn.run_sync(IdentityBinding.__table__.create)
        await conn.run_sync(OAuthLoginTransaction.__table__.create)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        yield db
    await engine.dispose()


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(settings, "CASDOOR_ISSUER", "https://idp.example")
    monkeypatch.setattr(settings, "CASDOOR_CLIENT_ID", "client")
    monkeypatch.setattr(settings, "CASDOOR_CLIENT_SECRET", "secret")
    monkeypatch.setattr(settings, "CASDOOR_REDIRECT_URI", "https://api.example/callback")
    monkeypatch.setattr(settings, "LOGIN_EMAIL_WHITELIST", "")


@pytest.fixture
def audits(monkeypatch):
    seen: list[dict] = []

    async def emit(*_args, **kwargs):
        seen.append(kwargs)

    monkeypatch.setattr(hooks, "emit", emit)
    return seen


def _app(db, user: User | None = None) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(casdoor_auth.router, prefix="/api/v1/auth")

    async def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    if user is not None:
        app.dependency_overrides[get_current_user] = lambda: user
    return app


async def _client(db, idp: _Idp, user: User | None = None) -> AsyncClient:
    casdoor_auth._client = lambda: CasdoorClient(transport=idp.transport())
    transport = ASGITransport(app=_app(db, user))
    return AsyncClient(transport=transport, base_url="http://test")


async def _add_user(db, **overrides) -> User:
    values = dict(
        name="Member",
        email="member@example.com",
        password_hash="hash",
        is_active=True,
        must_change_password=True,
    )
    values.update(overrides)
    user = User(**values)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _login(client: AsyncClient, return_to: str = RETURN_TO) -> httpx.Response:
    return await client.get("/api/v1/auth/casdoor/login", params={"return_to": return_to})


def _state(location: str) -> str:
    return location.split("state=", 1)[1].split("&", 1)[0]


@pytest.mark.asyncio
async def test_login_redirects_to_casdoor_with_pkce(session, configured, audits):
    idp = _Idp()
    async with await _client(session, idp) as client:
        response = await _login(client)
    assert response.status_code == 302
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    location = response.headers["location"]
    assert location.startswith("https://idp.example/authorize?")
    assert "response_type=code" in location
    assert "code_challenge_method=S256" in location
    assert "scope=openid+profile+email" in location
    assert "prompt" not in location
    assert audits == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "return_to",
    [
        "https://127.0.0.1:9/callback",
        "http://127.0.0.1/callback",
        "http://127.0.0.1:9/callback?next=1",
        "http://127.0.0.1:9/callback/",
        "http://[::1]:9/callback",
        "http://localhost:9/callback/extra",
    ],
)
async def test_invalid_return_to_does_not_create_transaction(session, configured, return_to):
    idp = _Idp()
    async with await _client(session, idp) as client:
        response = await _login(client, return_to)
    assert response.status_code == 400
    assert response.json()["message_key"] == "errors.auth.casdoor_return_to_invalid"
    assert idp.calls == []
    rows = (await session.execute(OAuthLoginTransaction.__table__.select())).all()
    assert rows == []


@pytest.mark.asyncio
async def test_unconfigured_login_does_not_call_network(session, monkeypatch):
    monkeypatch.setattr(settings, "CASDOOR_ISSUER", "")
    monkeypatch.setattr(settings, "CASDOOR_CLIENT_ID", "")
    monkeypatch.setattr(settings, "CASDOOR_CLIENT_SECRET", "")
    monkeypatch.setattr(settings, "CASDOOR_REDIRECT_URI", "")
    idp = _Idp()
    async with await _client(session, idp) as client:
        response = await _login(client)
    assert response.json()["message_key"] == "errors.auth.casdoor_not_configured"
    assert response.json()["message"] == "企业单点登录未配置"
    assert idp.calls == []


@pytest.mark.asyncio
async def test_callback_binds_and_exchange_issues_existing_login_shape(session, configured, audits, monkeypatch):
    user = await _add_user(session)
    issued: list = []

    async def fake_issue(member, _db):
        issued.append(member.id)
        return LoginResponse(
            access_token="access-token",
            refresh_token="refresh-token",
            user=UserInfo(id=member.id, name=member.name, email=member.email, role="user", current_org_id="org-1"),
        )

    monkeypatch.setattr("app.services.identity.binding_service.auth_service.issue_login_response", fake_issue)
    idp = _Idp()
    async with await _client(session, idp) as client:
        started = await _login(client)
        state = _state(started.headers["location"])
        callback = await client.get("/api/v1/auth/casdoor/callback", params={"state": state, "code": "auth-code"})
        assert callback.status_code == 302
        assert callback.headers["cache-control"] == "no-store"
        assert "access-token" not in callback.text
        assert "casdoor-access" not in callback.headers["location"]
        code = callback.headers["location"].split("code=", 1)[1]
        replayed = await client.get(
            "/api/v1/auth/casdoor/callback",
            params={"state": state, "code": "auth-code"},
        )
        assert replayed.headers["location"].endswith(f"error={LOGIN_EXPIRED}")
        assert audits == []
        binding = (await session.execute(IdentityBinding.__table__.select())).one()
        assert binding.member_user_id == user.id
        assert binding.email == "member@example.com"
        assert binding.last_login_at is None
        exchanged = await client.post("/api/v1/auth/casdoor/exchange", json={"code": code})
    body = exchanged.json()
    assert body["code"] == 0
    assert body["data"]["access_token"] == "access-token"
    assert body["data"]["refresh_token"] == "refresh-token"
    assert issued == [user.id]
    assert audits == [
        {
            "action": "auth.login",
            "target_type": "user",
            "target_id": user.id,
            "actor_id": user.id,
            "org_id": "org-1",
            "details": {"method": "casdoor"},
        }
    ]
    await session.refresh(user)
    assert user.last_login_at is not None
    assert user.must_change_password is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("profile", "machine_code"),
    [
        ({"sub": "user-1", "owner": "built-in", "email_verified": True}, EMAIL_MISSING),
        ({"sub": "user-1", "owner": "built-in", "email": "member@example.com", "email_verified": "true"}, EMAIL_UNVERIFIED),
        ({"sub": "user-1", "owner": "  ", "email": "member@example.com", "email_verified": True}, ORG_MISSING),
        ({"sub": "built-in/user", "owner": "built-in", "email": "member@example.com", "email_verified": True}, IDP_FAILED),
        ({"sub": "user-1", "owner": "built-in", "email": "missing@example.com", "email_verified": True}, MEMBER_NOT_FOUND),
    ],
)
async def test_callback_rejects_identity(session, configured, profile, machine_code):
    await _add_user(session)
    idp = _Idp()
    idp.profile = profile
    async with await _client(session, idp) as client:
        started = await _login(client)
        callback = await client.get(
            "/api/v1/auth/casdoor/callback",
            params={"state": _state(started.headers["location"]), "code": "auth-code"},
        )
    assert callback.status_code == 302
    assert callback.headers["location"].endswith(f"error={machine_code}")
    bindings = (await session.execute(IdentityBinding.__table__.select())).all()
    assert bindings == []


@pytest.mark.asyncio
async def test_callback_conflict_when_member_already_bound(session, configured):
    user = await _add_user(session)
    session.add(
        IdentityBinding(
            member_user_id=user.id,
            provider="casdoor",
            provider_org="other",
            provider_user_id="other-user",
            email="member@example.com",
        )
    )
    await session.commit()
    idp = _Idp()
    async with await _client(session, idp) as client:
        started = await _login(client)
        callback = await client.get(
            "/api/v1/auth/casdoor/callback",
            params={"state": _state(started.headers["location"]), "code": "auth-code"},
        )
    assert callback.headers["location"].endswith(f"error={BINDING_CONFLICT}")


@pytest.mark.asyncio
async def test_callback_disabled_and_deleted_member_do_not_rebind(session, configured):
    disabled = await _add_user(session, email="disabled@example.com", is_active=False)
    session.add(
        IdentityBinding(
            member_user_id=disabled.id,
            provider="casdoor",
            provider_org="built-in",
            provider_user_id="disabled-user",
            email="disabled@example.com",
        )
    )
    deleted = await _add_user(session, email="gone@example.com", deleted_at=datetime.now(timezone.utc))
    session.add(
        IdentityBinding(
            member_user_id=deleted.id,
            provider="casdoor",
            provider_org="built-in",
            provider_user_id="gone-user",
            email="gone@example.com",
        )
    )
    await session.commit()
    idp = _Idp()
    async with await _client(session, idp) as client:
        started = await _login(client)
        state = _state(started.headers["location"])
        idp.profile = {
            "sub": "disabled-user",
            "owner": "built-in",
            "email": "member@example.com",
            "email_verified": True,
        }
        disabled_response = await client.get(
            "/api/v1/auth/casdoor/callback",
            params={"state": state, "code": "auth-code"},
        )
        started_again = await _login(client)
        idp.profile = {
            "sub": "gone-user",
            "owner": "built-in",
            "email": "member@example.com",
            "email_verified": True,
        }
        deleted_response = await client.get(
            "/api/v1/auth/casdoor/callback",
            params={"state": _state(started_again.headers["location"]), "code": "auth-code"},
        )
    assert disabled_response.headers["location"].endswith(f"error={ACCOUNT_DISABLED}")
    assert deleted_response.headers["location"].endswith(f"error={ACCOUNT_DISABLED}")


@pytest.mark.asyncio
async def test_domain_not_allowed_before_exchange_code(session, configured, monkeypatch):
    await _add_user(session)
    monkeypatch.setattr(settings, "LOGIN_EMAIL_WHITELIST", "other.com")
    idp = _Idp()
    async with await _client(session, idp) as client:
        started = await _login(client)
        callback = await client.get(
            "/api/v1/auth/casdoor/callback",
            params={"state": _state(started.headers["location"]), "code": "auth-code"},
        )
    assert callback.headers["location"].endswith(f"error={DOMAIN_NOT_ALLOWED}")
    row = (await session.execute(OAuthLoginTransaction.__table__.select())).one()
    assert row.exchange_code_hash is None


@pytest.mark.asyncio
async def test_callback_idp_error_and_missing_code(session, configured):
    idp = _Idp()
    async with await _client(session, idp) as client:
        started = await _login(client)
        state = _state(started.headers["location"])
        denied = await client.get(
            "/api/v1/auth/casdoor/callback",
            params={"state": state, "error": "access_denied"},
        )
        assert denied.headers["location"].endswith(f"error={IDP_FAILED}")
        assert "error_description" not in denied.headers["location"]
        missing = await client.get("/api/v1/auth/casdoor/callback", params={"code": "auth-code"})
    assert missing.status_code == 400
    assert "location" not in missing.headers


@pytest.mark.asyncio
async def test_expired_and_replayed_callback(session, configured):
    idp = _Idp()
    async with await _client(session, idp) as client:
        started = await _login(client)
        state = _state(started.headers["location"])
        row = (await session.execute(OAuthLoginTransaction.__table__.select())).one()
        await session.execute(
            OAuthLoginTransaction.__table__.update()
            .where(OAuthLoginTransaction.id == row.id)
            .values(expires_at=datetime.now(timezone.utc) - timedelta(minutes=1))
        )
        await session.commit()
        expired = await client.get(
            "/api/v1/auth/casdoor/callback",
            params={"state": state, "code": "auth-code"},
        )
        assert expired.headers["location"].endswith(f"error={LOGIN_EXPIRED}")
        assert not any(call.endswith("/token") for call in idp.calls)


@pytest.mark.asyncio
async def test_exchange_replay_and_expiry(session, configured, monkeypatch):
    user = await _add_user(session)

    async def fake_issue(member, _db):
        return LoginResponse(
            access_token="access-token",
            refresh_token="refresh-token",
            user=UserInfo(id=member.id, name=member.name, role="user"),
        )

    monkeypatch.setattr("app.services.identity.binding_service.auth_service.issue_login_response", fake_issue)
    idp = _Idp()
    async with await _client(session, idp) as client:
        started = await _login(client)
        callback = await client.get(
            "/api/v1/auth/casdoor/callback",
            params={"state": _state(started.headers["location"]), "code": "auth-code"},
        )
        code = callback.headers["location"].split("code=", 1)[1]
        replay_setup = await client.post("/api/v1/auth/casdoor/exchange", json={"code": code})
        assert replay_setup.status_code == 200
        replay = await client.post("/api/v1/auth/casdoor/exchange", json={"code": code})
        assert replay.json()["message_key"] == "errors.auth.casdoor_login_expired"
        started_again = await _login(client)
        callback_again = await client.get(
            "/api/v1/auth/casdoor/callback",
            params={"state": _state(started_again.headers["location"]), "code": "auth-code"},
        )
        fresh = callback_again.headers["location"].split("code=", 1)[1]
        await session.execute(
            OAuthLoginTransaction.__table__.update()
            .where(OAuthLoginTransaction.exchange_code_hash.is_not(None), OAuthLoginTransaction.exchange_used_at.is_(None))
            .values(exchange_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        )
        await session.commit()
        expired = await client.post("/api/v1/auth/casdoor/exchange", json={"code": fresh})
    assert expired.json()["message"] == "登录已失效，请重新发起登录"
    assert user.id


@pytest.mark.asyncio
async def test_unbind_requires_password_and_missing_binding_succeeds(session, configured):
    without_password = await _add_user(session, password_hash=None)
    idp = _Idp()
    async with await _client(session, idp, without_password) as client:
        rejected = await client.delete("/api/v1/auth/casdoor/binding")
    assert rejected.json()["message_key"] == "errors.auth.casdoor_password_required"
    assert rejected.json()["message"] == "请先设置密码后再解除绑定"
    with_password = await _add_user(session, email="other@example.com")
    async with await _client(session, idp, with_password) as client:
        missing = await client.delete("/api/v1/auth/casdoor/binding")
        session.add(
            IdentityBinding(
                member_user_id=with_password.id,
                provider="casdoor",
                provider_org="built-in",
                provider_user_id="other",
                email="other@example.com",
            )
        )
        await session.commit()
        removed = await client.delete("/api/v1/auth/casdoor/binding")
    assert missing.json()["code"] == 0
    assert missing.json()["data"] is None
    assert removed.json()["code"] == 0
    binding = (
        await session.execute(
            IdentityBinding.__table__.select().where(IdentityBinding.member_user_id == with_password.id)
        )
    ).one()
    assert binding.deleted_at is not None
