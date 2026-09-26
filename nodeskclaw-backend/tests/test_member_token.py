"""Member model credential unit tests. These use mocks and never call a live NEW-API."""

import base64
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.config import settings
from app.services.credential_crypto import (
    MemberTokenError,
    decrypt_member_token,
    encrypt_member_token,
)
from app.services.member_token_models import normalize_models_document
from app.services import member_token_service
from app.services.member_token_service import (
    assert_membership_org,
    close_local_member_token,
    create_member_token,
    delete_member_token,
    mask_token,
    reveal_member_token,
    retry_revoke_member_token,
    token_name_from_email,
    _public,
    _provision_new_api,
)
from app.services.model_provider.new_api import NewApiClient, normalize_groups

KEY = base64.b64encode(b"0123456789abcdef0123456789abcdef").decode()


@pytest.fixture(autouse=True)
def _crypto_key(monkeypatch):
    monkeypatch.setattr(settings, "MODEL_TOKEN_ENCRYPTION_KEY", KEY)
    monkeypatch.setattr(settings, "ENCRYPTION_KEY", "not-the-member-token-key")
    monkeypatch.setattr(settings, "NEW_API_ADMIN_BASE_URL", "http://new-api.example")
    monkeypatch.setattr(settings, "NEW_API_SYSTEM_ACCESS_TOKEN", "test-system-token")
    monkeypatch.setattr(settings, "NEW_API_USER_ID", "1")
    monkeypatch.setattr(settings, "NEW_API_TIMEOUT_SECONDS", 5)
    monkeypatch.setattr(settings, "NEW_API_MODEL_BASE_URL", "http://new-api.example/v1")


def test_encrypt_roundtrip_and_aad_mismatch():
    stored = encrypt_member_token("secret-value-123456", token_id="t1", member_id="m1", provider="new-api")
    assert stored.startswith("enc:v1:")
    assert "secret-value" not in stored
    assert decrypt_member_token(stored, token_id="t1", member_id="m1", provider="new-api") == "secret-value-123456"
    with pytest.raises(MemberTokenError) as exc:
        decrypt_member_token(stored, token_id="t1", member_id="other", provider="new-api")
    assert exc.value.message_key == "errors.member_token.decrypt_failed"


def test_mask_uses_ends_without_returning_middle():
    assert mask_token("abcdefghijklmnop") == "abcd**********mnop"
    assert mask_token("shortkey") == "sh****ey"


def test_token_name_and_org_binding():
    assert token_name_from_email("Alice@Example.com") == "alice"
    with pytest.raises(MemberTokenError) as invalid:
        token_name_from_email("missing-at")
    assert invalid.value.message_key == "errors.member_token.name_invalid"
    member = SimpleNamespace(org_id="org-1", deleted_at=None)
    assert assert_membership_org(member, "org-1") is member
    with pytest.raises(MemberTokenError) as missing:
        assert_membership_org(member, "org-2")
    assert missing.value.message_key == "errors.member_token.member_not_found"


def test_models_document_rejects_unknown_keys():
    empty = normalize_models_document(None)
    assert empty["items"] == []
    with pytest.raises(MemberTokenError) as exc:
        normalize_models_document({"schema_version": "1.0", "items": [], "extra": True})
    assert exc.value.message_key == "errors.member_token.models_invalid"


class _FakeHttp:
    def __init__(self, handler):
        self.handler = handler

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def request(self, method, url, headers=None, json=None, params=None):
        return self.handler(method, url, headers, json, params)


@pytest.mark.asyncio
async def test_new_api_client_sends_both_headers_and_one_create(monkeypatch):
    calls = []

    def handler(method, url, headers, body, params):
        calls.append((method, url, headers, body))
        request = httpx.Request(method, url)
        if url.endswith("/api/user/self/groups"):
            return httpx.Response(
                200,
                json={"success": True, "data": {"default": {"desc": "d", "ratio": 1}, "auto": {"desc": "a", "ratio": 1}}},
                request=request,
            )
        if method == "POST" and url.endswith("/api/token/"):
            return httpx.Response(200, json={"success": True, "data": None}, request=request)
        if url.endswith("/api/token/search"):
            return httpx.Response(
                200,
                json={"success": True, "data": {"items": [{"id": 7, "name": "alice"}], "total": 1}},
                request=request,
            )
        if method == "GET" and "/api/token/9" in url:
            return httpx.Response(401, json={"success": False, "message": "unauthorized"}, request=request)
        return httpx.Response(500, json={"success": False}, request=request)

    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: _FakeHttp(handler))
    client = NewApiClient()
    groups = normalize_groups(await client.list_groups())
    assert [item["value"] for item in groups] == ["default"]
    matches = await client.search_exact("alice")
    assert matches[0]["id"] == 7
    await client.create_token("alice", "default")
    assert calls[0][2]["Authorization"] == "Bearer test-system-token"
    assert calls[0][2]["New-Api-User"] == "1"
    assert len([call for call in calls if call[0] == "POST" and call[1].endswith("/api/token/")]) == 1
    create_body = [call[3] for call in calls if call[0] == "POST" and call[1].endswith("/api/token/")][0]
    assert create_body["group"] == "default"
    assert "token" not in create_body
    with pytest.raises(MemberTokenError) as exc:
        await client.update_group("9", "vip")
    assert exc.value.message_key == "errors.member_token.new_api_auth_failed"


@pytest.mark.asyncio
async def test_delete_token_missing_uses_token_missing_key(monkeypatch):
    def handler(method, url, headers, body, params):
        request = httpx.Request(method, url)
        return httpx.Response(404, json={"success": False, "message": "not found"}, request=request)

    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: _FakeHttp(handler))
    with pytest.raises(MemberTokenError) as exc:
        await NewApiClient().delete_token("99")
    assert exc.value.message_key == "errors.member_token.new_api_token_missing"


@pytest.mark.asyncio
async def test_local_commit_failure_does_not_compensate_external_delete():
    membership = SimpleNamespace(
        id="m1",
        org_id="org-1",
        user=SimpleNamespace(email="alice@example.com"),
    )
    actor = SimpleNamespace(id="u1")
    client = MagicMock()
    client.list_groups = AsyncMock(return_value={"vip": {"desc": "v"}})
    client.search_exact = AsyncMock(side_effect=[[], [{"id": 28, "name": "alice"}]])
    client.create_token = AsyncMock()
    client.fetch_key = AsyncMock(return_value="sk-live-abcdefghabcdefgh")
    client.delete_token = AsyncMock()

    db = AsyncMock()
    db.commit = AsyncMock(side_effect=RuntimeError("db down"))
    db.rollback = AsyncMock()
    db.flush = AsyncMock()
    db.add = MagicMock()
    db.get_bind = MagicMock(return_value=SimpleNamespace(dialect=SimpleNamespace(name="sqlite")))

    with (
        patch.object(member_token_service, "NewApiClient", return_value=client),
        patch.object(member_token_service, "_insert_local", new=AsyncMock(return_value=SimpleNamespace(id="t1"))),
        patch.object(member_token_service, "_audit", new=AsyncMock()),
    ):
        with pytest.raises(RuntimeError, match="db down"):
            await _provision_new_api(
                db,
                membership=membership,
                actor=actor,
                existing=None,
                provider_group="vip",
                document={"schema_version": "1.0", "default_model": None, "items": []},
                is_default=False,
            )
    client.delete_token.assert_not_called()
    db.rollback.assert_awaited()


@pytest.mark.asyncio
async def test_delete_failure_marks_revoke_pending_and_keeps_row():
    row = SimpleNamespace(
        id="t1",
        provider="new-api",
        external_token_id="28",
        is_active=True,
        sync_status="synced",
        last_sync_error=None,
        soft_delete=MagicMock(),
    )
    membership = SimpleNamespace(id="m1", org_id="org-1", deleted_at=None)
    actor = SimpleNamespace(id="u1")
    db = AsyncMock()
    db.commit = AsyncMock()
    fake_client = MagicMock()
    fake_client.delete_token = AsyncMock(
        side_effect=MemberTokenError(502, "errors.member_token.new_api_delete_failed", "fail")
    )

    with (
        patch.object(member_token_service, "_load_membership", new=AsyncMock(return_value=membership)),
        patch.object(member_token_service, "_get_row", new=AsyncMock(return_value=row)),
        patch.object(member_token_service, "NewApiClient", return_value=fake_client),
        patch.object(member_token_service, "_audit", new=AsyncMock()),
    ):
        with pytest.raises(MemberTokenError) as exc:
            await delete_member_token(db, org_id="org-1", membership_id="m1", token_id="t1", actor=actor)
    assert exc.value.message_key == "errors.member_token.new_api_delete_failed"
    assert row.is_active is False
    assert row.sync_status == "revoke_pending"
    assert row.external_token_id == "28"
    row.soft_delete.assert_not_called()


@pytest.mark.asyncio
async def test_retry_revoke_keeps_pending_when_external_missing():
    row = SimpleNamespace(
        id="t1",
        provider="new-api",
        external_token_id="28",
        is_active=False,
        sync_status="revoke_pending",
        last_sync_error=None,
        soft_delete=MagicMock(),
    )
    membership = SimpleNamespace(id="m1", org_id="org-1", deleted_at="gone")
    actor = SimpleNamespace(id="u1")
    db = AsyncMock()
    db.commit = AsyncMock()
    fake_client = MagicMock()
    fake_client.delete_token = AsyncMock(
        side_effect=MemberTokenError(502, "errors.member_token.new_api_token_missing", "missing")
    )

    with (
        patch.object(member_token_service, "_load_membership", new=AsyncMock(return_value=membership)),
        patch.object(member_token_service, "_get_row", new=AsyncMock(return_value=row)),
        patch.object(member_token_service, "NewApiClient", return_value=fake_client),
        patch.object(member_token_service, "_audit", new=AsyncMock()),
    ):
        with pytest.raises(MemberTokenError) as exc:
            await retry_revoke_member_token(db, org_id="org-1", membership_id="m1", token_id="t1", actor=actor)
    assert exc.value.message_key == "errors.member_token.new_api_token_missing"
    assert row.sync_status == "revoke_pending"
    row.soft_delete.assert_not_called()


@pytest.mark.asyncio
async def test_close_local_does_not_call_new_api():
    row = SimpleNamespace(
        id="t1",
        provider="new-api",
        external_token_id="28",
        is_active=False,
        sync_status="revoke_pending",
        soft_delete=MagicMock(),
    )
    membership = SimpleNamespace(id="m1", org_id="org-1", deleted_at=None)
    actor = SimpleNamespace(id="u1")
    db = AsyncMock()
    db.commit = AsyncMock()
    fake_client = MagicMock()
    fake_client.delete_token = AsyncMock()
    audit = AsyncMock()

    with (
        patch.object(member_token_service, "_load_membership", new=AsyncMock(return_value=membership)),
        patch.object(member_token_service, "_get_row", new=AsyncMock(return_value=row)),
        patch.object(member_token_service, "NewApiClient", return_value=fake_client),
        patch.object(member_token_service, "_audit", new=audit),
    ):
        result = await close_local_member_token(
            db, org_id="org-1", membership_id="m1", token_id="t1", actor=actor
        )
    assert result["closed"] is True
    fake_client.delete_token.assert_not_called()
    row.soft_delete.assert_called_once()
    assert audit.await_args.args[2] == "member_token.closed_local"
    assert audit.await_args.kwargs["external_revoke_confirmed"] is False


@pytest.mark.asyncio
async def test_manual_new_api_has_no_external_id_or_token_name():
    membership = SimpleNamespace(
        id="m1",
        org_id="org-1",
        deleted_at=None,
        user=SimpleNamespace(email="alice@example.com"),
    )
    actor = SimpleNamespace(id="u1")
    captured = {}

    async def fake_insert(db, **kwargs):
        captured.update(kwargs)
        row = SimpleNamespace(
            id="t-manual",
            member_id="m1",
            provider="new-api",
            base_url=kwargs["base_url"],
            token=encrypt_member_token(
                kwargs["plaintext"], token_id="t-manual", member_id="m1", provider="new-api"
            ),
            token_name=kwargs["token_name"],
            provider_group=kwargs["provider_group"],
            models=kwargs["document"],
            source=kwargs["source"],
            is_active=True,
            is_default=False,
            sync_status=kwargs["sync_status"],
            last_sync_error=None,
            external_token_id=kwargs["external_token_id"],
        )
        return row

    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.get_bind = MagicMock(return_value=SimpleNamespace(dialect=SimpleNamespace(name="sqlite")))

    with (
        patch.object(member_token_service, "_load_membership", new=AsyncMock(return_value=membership)),
        patch.object(member_token_service, "_find_provider_row", new=AsyncMock(return_value=None)),
        patch.object(member_token_service, "_insert_local", new=fake_insert),
        patch.object(member_token_service, "_audit", new=AsyncMock()),
        patch.object(member_token_service, "NewApiClient") as client_cls,
    ):
        result = await create_member_token(
            db,
            org_id="org-1",
            membership_id="m1",
            actor=actor,
            provider="new-api",
            provider_group=None,
            base_url="http://example.com/v1",
            plaintext="manual-secret-key-1234",
            models=None,
            is_default=False,
            fields_set={"provider", "base_url", "token"},
        )
    client_cls.assert_not_called()
    assert captured["external_token_id"] is None
    assert captured["token_name"] is None
    assert captured["source"] == "manual"
    assert captured["sync_status"] == "manual"
    assert result["plaintext_token"] is None
    assert "manual-secret" not in str(result)


@pytest.mark.asyncio
async def test_auto_create_rejects_token_or_base_url_presence():
    membership = SimpleNamespace(id="m1", org_id="org-1", deleted_at=None, user=SimpleNamespace(email="a@b.com"))
    actor = SimpleNamespace(id="u1")
    db = AsyncMock()
    db.get_bind = MagicMock(return_value=SimpleNamespace(dialect=SimpleNamespace(name="sqlite")))

    with (
        patch.object(member_token_service, "_load_membership", new=AsyncMock(return_value=membership)),
        patch.object(member_token_service, "_find_provider_row", new=AsyncMock(return_value=None)),
    ):
        with pytest.raises(MemberTokenError) as exc:
            await create_member_token(
                db,
                org_id="org-1",
                membership_id="m1",
                actor=actor,
                provider="new-api",
                provider_group="vip",
                base_url="",
                plaintext=None,
                models=None,
                is_default=False,
                fields_set={"provider", "provider_group", "base_url"},
            )
    assert exc.value.message_key == "errors.member_token.managed_field_forbidden"


@pytest.mark.asyncio
async def test_reveal_allows_self_and_forbids_other_member():
    membership = SimpleNamespace(id="m1", org_id="org-1", deleted_at=None, user_id="owner")
    row = SimpleNamespace(
        id="t1",
        member_id="m1",
        provider="new-api",
        token=encrypt_member_token("secret-reveal-key-9999", token_id="t1", member_id="m1", provider="new-api"),
        base_url="http://x",
        token_name=None,
        provider_group=None,
        models={"items": []},
        source="manual",
        is_active=True,
        is_default=False,
        sync_status="manual",
        last_sync_error=None,
    )
    db = AsyncMock()
    self_user = SimpleNamespace(id="owner", is_super_admin=False)
    other_user = SimpleNamespace(id="other", is_super_admin=False)
    audit = AsyncMock()

    with (
        patch.object(member_token_service, "_load_membership", new=AsyncMock(return_value=membership)),
        patch.object(member_token_service, "_get_row", new=AsyncMock(return_value=row)),
        patch.object(member_token_service, "_audit", new=audit),
    ):
        data = await reveal_member_token(
            db, org_id="org-1", membership_id="m1", token_id="t1", caller=self_user
        )
        assert data["plaintext_token"] == "secret-reveal-key-9999"
        assert audit.await_args.args[2] == "member_token.revealed"
        assert audit.await_args.kwargs.get("provider") == "new-api"
        assert "plaintext_token" not in audit.await_args.kwargs
        assert "token" not in audit.await_args.kwargs

        empty = MagicMock()
        empty.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=empty)
        with pytest.raises(MemberTokenError) as forbidden:
            await reveal_member_token(
                db, org_id="org-1", membership_id="m1", token_id="t1", caller=other_user
            )
    assert forbidden.value.message_key == "errors.member_token.reveal_forbidden"


def test_public_payload_has_mask_not_plaintext():
    row = SimpleNamespace(
        id="t1",
        member_id="m1",
        provider="new-api",
        token=encrypt_member_token("secret-reveal-key-9999", token_id="t1", member_id="m1", provider="new-api"),
        base_url="http://x",
        token_name="alice",
        provider_group="vip",
        models={"items": []},
        source="auto",
        is_active=True,
        is_default=False,
        sync_status="synced",
        last_sync_error=None,
    )
    public = _public(row)
    assert public["token_masked"].startswith("secr")
    assert public["plaintext_token"] is None
    assert "secret-reveal-key-9999" not in str(public)


def test_member_token_code_does_not_touch_user_llm_configs():
    root = Path(__file__).resolve().parents[1]
    service = (root / "app" / "services" / "member_token_service.py").read_text(encoding="utf-8")
    api = (root / "app" / "api" / "member_tokens.py").read_text(encoding="utf-8")
    model = (root / "app" / "models" / "member_token.py").read_text(encoding="utf-8")
    implementation = "\n".join(
        line
        for line in service.splitlines()
        if not line.strip().startswith('"""') and "user_llm_configs is not written" not in line
    )
    assert "UserLlmConfig" not in implementation
    assert "user_llm_configs" not in implementation
    assert "user_llm_configs" not in api
    assert "user_llm_configs" not in model
    assert "_compensate_external_token" not in service
