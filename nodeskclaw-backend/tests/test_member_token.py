"""Member model credential unit tests. These use mocks and never call a live NEW-API."""

import base64
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from app.core.config import settings
from app.services.credential_crypto import (
    MemberTokenError,
    decrypt_member_token,
    encrypt_member_token,
)
from app.services.member_token_models import normalize_models_document
from app.services.member_token_service import (
    _compensate_external_token,
    assert_membership_org,
    mask_token,
    token_name_from_email,
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
async def test_compensation_deletes_external_token_once():
    deleted = []

    class FakeClient:
        async def delete_token(self, external_id: str) -> None:
            deleted.append(external_id)

    await _compensate_external_token(FakeClient(), "28")
    assert deleted == ["28"]


@pytest.mark.asyncio
async def test_compensation_failure_keeps_catalog_key():
    class FakeClient:
        async def delete_token(self, external_id: str) -> None:
            raise MemberTokenError(502, "errors.member_token.new_api_delete_failed", "delete failed")

    with pytest.raises(MemberTokenError) as exc:
        await _compensate_external_token(FakeClient(), "28")
    assert exc.value.message_key == "errors.member_token.new_api_compensation_failed"


def test_member_token_code_does_not_touch_user_llm_configs():
    root = Path(__file__).resolve().parents[1]
    service = (root / "app" / "services" / "member_token_service.py").read_text(encoding="utf-8")
    api = (root / "app" / "api" / "member_tokens.py").read_text(encoding="utf-8")
    model = (root / "app" / "models" / "member_token.py").read_text(encoding="utf-8")
    implementation = "\n".join(line for line in service.splitlines() if not line.strip().startswith('"""') and "user_llm_configs is not written" not in line)
    assert "UserLlmConfig" not in implementation
    assert "user_llm_configs" not in implementation
    assert "user_llm_configs" not in api
    assert "user_llm_configs" not in model
