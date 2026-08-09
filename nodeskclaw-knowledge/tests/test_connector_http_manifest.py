"""Credential encryption, SSRF guard, and HTTP manifest connector tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.connectors.http_manifest.connector import HttpManifestConnector
from app.connectors.models import SourceDescriptor
from app.connectors.registry import get_connector_class
from app.core.exceptions import ValidationError
from app.services.connector_credential_service import decrypt_payload, encrypt_payload
from app.services.http_egress_guard import SafeRedirectGuard, resolve_and_validate_url


def test_http_manifest_registered():
    assert get_connector_class("http_manifest") is HttpManifestConnector


def test_credential_encrypt_roundtrip(monkeypatch):
    monkeypatch.setenv("KNOWLEDGE_CONNECTOR_MASTER_KEY", "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef")
    from app.core.config import settings

    settings.KNOWLEDGE_CONNECTOR_MASTER_KEY = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    payload = {"token": "secret-token", "auth_mode": "bearer"}
    ciphertext, nonce, key_version = encrypt_payload(payload)
    assert key_version == 1
    assert ciphertext != b"secret-token"
    restored = decrypt_payload(ciphertext, nonce, key_version=key_version)
    assert restored == payload


def test_ssrf_blocks_loopback():
    with pytest.raises(ValidationError) as exc:
        resolve_and_validate_url("http://127.0.0.1/secret")
    assert exc.value.message_key == "errors.knowledge.http_url_blocked"


def test_ssrf_blocks_metadata_ip():
    with pytest.raises(ValidationError):
        resolve_and_validate_url("http://169.254.169.254/latest/meta-data")


def test_ssrf_allows_private_when_allowlisted(monkeypatch):
    with patch("app.services.http_egress_guard.socket.getaddrinfo") as gai:
        gai.return_value = [(None, None, None, None, ("10.1.2.3", 80))]
        url = resolve_and_validate_url(
            "http://intranet.example.com/manifest",
            allow_private_networks={"10.0.0.0/8"},
        )
        assert "intranet.example.com" in url


def test_ssrf_blocks_private_without_allowlist(monkeypatch):
    with patch("app.services.http_egress_guard.socket.getaddrinfo") as gai:
        gai.return_value = [(None, None, None, None, ("10.1.2.3", 80))]
        with pytest.raises(ValidationError):
            resolve_and_validate_url("http://intranet.example.com/manifest", allow_private_networks=set())


def test_redirect_guard_blocks_escape():
    guard = SafeRedirectGuard(allow_private_networks=set())
    with pytest.raises(ValidationError):
        guard.on_redirect("http://127.0.0.1/now-internal")


@pytest.mark.asyncio
async def test_http_manifest_discover_and_fetch(monkeypatch):
    monkeypatch.setenv("KNOWLEDGE_CONNECTOR_MASTER_KEY", "x" * 32)

    manifest = {
        "items": [
            {
                "id": "ERP-1",
                "name": "a.pdf",
                "revision": "r1",
                "download_url": "https://files.example.com/a.pdf",
                "mime_type": "application/pdf",
                "size": 5,
                "metadata": {"department": "ops"},
            }
        ],
        "next_cursor": None,
    }

    client = AsyncMock()

    manifest_resp = MagicMock()
    manifest_resp.is_redirect = False
    manifest_resp.raise_for_status = MagicMock()
    manifest_resp.json.return_value = manifest

    file_resp = MagicMock()
    file_resp.is_redirect = False
    file_resp.raise_for_status = MagicMock()
    file_resp.content = b"hello"
    file_resp.headers = {"content-type": "application/pdf"}

    client.request = AsyncMock(side_effect=[manifest_resp, file_resp])
    client.aclose = AsyncMock()

    with patch("app.connectors.http_manifest.connector.resolve_and_validate_url", side_effect=lambda u, **kw: u):
        connector = HttpManifestConnector(
            {"manifest_url": "https://api.example.com/manifest", "auth_mode": "bearer"},
            credentials={"token": "t"},
            client=client,
        )
        page = await connector.discover()
        assert len(page.objects) == 1
        assert page.objects[0].external_object_id == "ERP-1"
        fetched = await connector.fetch(page.objects[0])
        assert fetched.sha256
        assert fetched.size == 5
        await connector.close()
