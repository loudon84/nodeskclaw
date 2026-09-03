"""Edge control channel unit tests."""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, PublicFormat, NoEncryption

from app.services.connector.edge_control_channel import EdgeControlChannel, bind_request_digest, canonical_payload_sha256
from app.services.connector.edge_node_service import EdgeNodeService, hash_edge_bootstrap


def _b64_private(key: Ed25519PrivateKey) -> str:
    return base64.b64encode(
        key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    ).decode("ascii")


def _b64_public(key: Ed25519PrivateKey) -> str:
    return base64.b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode("ascii")


def _empty_receive(body: bytes = b""):
    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    return receive


@pytest.fixture
def issuer_keys():
    key = Ed25519PrivateKey.generate()
    return {
        "id": "issuer-test-1",
        "private": _b64_private(key),
        "public": _b64_public(key),
    }


def test_canonical_payload_sha256_empty():
    assert canonical_payload_sha256(b"") == canonical_payload_sha256(None)


def test_bind_request_digest_uses_canonical_json_and_query():
    unordered = b'{"b":2,"a":1}'
    canonical = b'{"a":1,"b":2}'
    assert bind_request_digest(body=unordered) == bind_request_digest(body=canonical)
    empty = bind_request_digest(body=b"", query="")
    with_query = bind_request_digest(body=b"", query="generation=3")
    assert with_query != empty
    assert with_query == bind_request_digest(body=b"", query="generation=3")


def test_sign_command_envelope(issuer_keys):
    db = AsyncMock()
    with patch("app.services.connector.edge_control_channel.settings") as mock_settings:
        mock_settings.EDGE_CONTROL_ISSUER_KEY_ID = issuer_keys["id"]
        mock_settings.EDGE_CONTROL_ISSUER_PRIVATE_KEY = issuer_keys["private"]
        mock_settings.EDGE_CONTROL_ISSUER_KEY_ID_PREVIOUS = ""
        mock_settings.EDGE_CONTROL_ISSUER_PRIVATE_KEY_PREVIOUS = ""
        mock_settings.EDGE_CONTROL_ISSUER_ROTATION_EXPIRES_AT = ""
        mock_settings.EDGE_CONTROL_COMMAND_TTL_SECONDS = 300
        channel = EdgeControlChannel(db)
        wrapped = channel.sign_command_envelope(
            org_id="org-1",
            node_id="node-1",
            purpose="job.claim",
            payload={"id": "job-1"},
        )
    assert wrapped["envelope"]["issuer_key_id"] == issuer_keys["id"]
    assert wrapped["payload"]["id"] == "job-1"
    assert wrapped["envelope"]["sig"]


@pytest.mark.asyncio
async def test_bind_identity_rejects_reused_bootstrap():
    from app.core.exceptions import ForbiddenError
    from app.models.connector.edge_node import EdgeNode

    db = AsyncMock()
    service = EdgeNodeService(db)
    node = EdgeNode(
        id="node-1",
        org_id="org-1",
        name="edge-1",
        status="pending",
        token_hash=hash_edge_bootstrap("bootstrap-1"),
        bootstrap_consumed_at=datetime.now(timezone.utc),
        bootstrap_expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    service.get = AsyncMock(return_value=node)
    with pytest.raises(ForbiddenError):
        await service.bind_identity(
            org_id="org-1",
            node_id="node-1",
            bootstrap="bootstrap-1",
            public_key="abc",
        )


@pytest.mark.asyncio
async def test_authenticate_edge_rejects_forged_proof():
    from app.api import internal_edge
    from app.core.exceptions import ForbiddenError
    from fastapi import Request

    db = AsyncMock()
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/internal/edge/jobs",
        "query_string": b"",
        "headers": [
            (b"x-edge-node-id", b"node-1"),
            (b"x-edge-identity-version", b"1"),
            (b"x-edge-timestamp", b"1"),
            (b"x-edge-nonce", b"n1"),
            (b"x-edge-seq", b"1"),
            (b"x-edge-payload-sha256", canonical_payload_sha256(b"").encode()),
            (b"x-edge-signature", b"invalid"),
        ],
    }
    request = Request(scope, _empty_receive())
    node = MagicMock()
    node.id = "node-1"
    node.org_id = "org-1"
    node.public_key = "abc"
    node.identity_version = 1
    node.identity_revoked_at = None
    node.status = "online"
    node.deleted_at = None
    with patch.object(EdgeControlChannel, "get_node_for_proof", AsyncMock(return_value=node)), patch.object(
        EdgeControlChannel,
        "verify_request_proof",
        AsyncMock(side_effect=ForbiddenError("bad sig", "errors.connector.edge_request_signature_invalid")),
    ):
        with pytest.raises(ForbiddenError):
            await internal_edge._authenticate_edge(db, request)


@pytest.mark.asyncio
async def test_authenticate_edge_hashes_real_body_not_header():
    from app.api import internal_edge
    from app.core.exceptions import ForbiddenError
    from fastapi import Request

    body = b'{"node_id":"node-1","status_meta":{"role":"edge"}}'
    captured: dict[str, str] = {}

    async def capture_verify(self, node, **kwargs):
        captured["payload_sha256"] = kwargs["payload_sha256"]

    db = AsyncMock()
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/internal/edge/heartbeat",
        "query_string": b"",
        "headers": [
            (b"x-edge-node-id", b"node-1"),
            (b"x-edge-identity-version", b"1"),
            (b"x-edge-timestamp", b"1"),
            (b"x-edge-nonce", b"n1"),
            (b"x-edge-seq", b"1"),
            (b"content-length", str(len(body)).encode()),
        ],
    }
    request = Request(scope, _empty_receive(body))
    node = MagicMock()
    node.id = "node-1"
    node.org_id = "org-1"
    node.public_key = "abc"
    node.identity_version = 1
    node.identity_revoked_at = None
    node.status = "online"
    node.deleted_at = None
    with patch.object(EdgeControlChannel, "get_node_for_proof", AsyncMock(return_value=node)), patch.object(
        EdgeControlChannel,
        "verify_request_proof",
        capture_verify,
    ):
        await internal_edge._authenticate_edge(db, request)
    assert captured["payload_sha256"] == bind_request_digest(body=body, query="")
    assert captured["payload_sha256"] != canonical_payload_sha256(b"")


@pytest.mark.asyncio
async def test_authenticate_edge_rejects_claimed_digest_mismatch():
    from app.api import internal_edge
    from app.core.exceptions import ForbiddenError
    from fastapi import Request

    body = b'{"node_id":"node-1"}'
    db = AsyncMock()
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/internal/edge/heartbeat",
        "query_string": b"",
        "headers": [
            (b"x-edge-node-id", b"node-1"),
            (b"x-edge-payload-sha256", canonical_payload_sha256(b"").encode()),
        ],
    }
    request = Request(scope, _empty_receive(body))
    node = MagicMock()
    node.id = "node-1"
    node.org_id = "org-1"
    node.public_key = "abc"
    node.identity_version = 1
    node.identity_revoked_at = None
    node.status = "online"
    node.deleted_at = None
    with patch.object(EdgeControlChannel, "get_node_for_proof", AsyncMock(return_value=node)):
        with pytest.raises(ForbiddenError) as exc:
            await internal_edge._authenticate_edge(db, request)
    assert exc.value.message_key == "errors.connector.edge_payload_digest_mismatch"


@pytest.mark.asyncio
async def test_authenticate_edge_binds_query_into_digest():
    from app.api import internal_edge
    from fastapi import Request

    captured: dict[str, str] = {}

    async def capture_verify(self, node, **kwargs):
        captured["payload_sha256"] = kwargs["payload_sha256"]

    db = AsyncMock()
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/internal/edge/installations/inst-1/bundle",
        "query_string": b"generation=7",
        "headers": [
            (b"x-edge-node-id", b"node-1"),
        ],
    }
    request = Request(scope, _empty_receive())
    node = MagicMock()
    node.id = "node-1"
    node.org_id = "org-1"
    node.public_key = "abc"
    node.identity_version = 1
    node.identity_revoked_at = None
    node.status = "online"
    node.deleted_at = None
    with patch.object(EdgeControlChannel, "get_node_for_proof", AsyncMock(return_value=node)), patch.object(
        EdgeControlChannel,
        "verify_request_proof",
        capture_verify,
    ):
        await internal_edge._authenticate_edge(db, request)
    assert captured["payload_sha256"] == bind_request_digest(body=b"", query="generation=7")


def test_sign_command_envelope_rejects_unknown_purpose(issuer_keys):
    db = AsyncMock()
    with patch("app.services.connector.edge_control_channel.settings") as mock_settings:
        mock_settings.EDGE_CONTROL_ISSUER_KEY_ID = issuer_keys["id"]
        mock_settings.EDGE_CONTROL_ISSUER_PRIVATE_KEY = issuer_keys["private"]
        mock_settings.EDGE_CONTROL_ISSUER_KEY_ID_PREVIOUS = ""
        mock_settings.EDGE_CONTROL_ISSUER_PRIVATE_KEY_PREVIOUS = ""
        mock_settings.EDGE_CONTROL_ISSUER_ROTATION_EXPIRES_AT = ""
        mock_settings.EDGE_CONTROL_COMMAND_TTL_SECONDS = 300
        channel = EdgeControlChannel(db)
        with pytest.raises(ValueError):
            channel.sign_command_envelope(
                org_id="org-1",
                node_id="node-1",
                purpose="job.forged",
                payload={"id": "job-1"},
            )
