"""Edge control channel unit tests."""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, PublicFormat, NoEncryption

from app.services.connector.edge_control_channel import EdgeControlChannel, canonical_payload_sha256
from app.services.connector.edge_node_service import EdgeNodeService, hash_edge_bootstrap


def _b64_private(key: Ed25519PrivateKey) -> str:
    return base64.b64encode(
        key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    ).decode("ascii")


def _b64_public(key: Ed25519PrivateKey) -> str:
    return base64.b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode("ascii")


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
    request = Request(scope)
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
