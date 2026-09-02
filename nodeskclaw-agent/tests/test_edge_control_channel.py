"""Agent edge control channel tests."""

from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, PublicFormat, NoEncryption

from app.services.edge_control_channel import EdgeControlChannel, EdgeIdentityState, canonical_payload_sha256


def _b64_private(key: Ed25519PrivateKey) -> str:
    return base64.b64encode(
        key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    ).decode("ascii")


def _b64_public(key: Ed25519PrivateKey) -> str:
    return base64.b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode("ascii")


def test_verify_command_envelope_accepts_valid_command(tmp_path: Path):
    node_key = Ed25519PrivateKey.generate()
    issuer_key = Ed25519PrivateKey.generate()
    channel = EdgeControlChannel(tmp_path)
    state = EdgeIdentityState(
        node_id="node-1",
        org_id="org-1",
        identity_version=1,
        private_key=_b64_private(node_key),
        public_key=_b64_public(node_key),
        issuer_key_id="issuer-1",
        issuer_public_key=_b64_public(issuer_key),
        previous_issuer_key_id=None,
        previous_issuer_public_key=None,
        issuer_rotation_expires_at=None,
        request_seq=0,
        consumed_commands={},
    )
    channel.save(state)
    payload = {"job_id": "job-1", "cancel_requested": True, "cancelled": True}
    envelope_body = {
        "org_id": "org-1",
        "node_id": "node-1",
        "purpose": "job.cancel.check",
        "command_id": "cmd-1",
        "nonce": "nonce-1",
        "command_seq": 1,
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
        "payload_sha256": canonical_payload_sha256(payload),
        "issuer_key_id": "issuer-1",
    }
    message = json.dumps(envelope_body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sig = issuer_key.sign(message)
    wrapped = {
        "envelope": {**envelope_body, "sig": base64.b64encode(sig).decode("ascii")},
        "payload": payload,
    }
    verified = channel.verify_command_envelope(state, wrapped)
    assert verified == payload


def test_verify_command_envelope_rejects_replay(tmp_path: Path):
    node_key = Ed25519PrivateKey.generate()
    issuer_key = Ed25519PrivateKey.generate()
    channel = EdgeControlChannel(tmp_path)
    state = EdgeIdentityState(
        node_id="node-1",
        org_id="org-1",
        identity_version=1,
        private_key=_b64_private(node_key),
        public_key=_b64_public(node_key),
        issuer_key_id="issuer-1",
        issuer_public_key=_b64_public(issuer_key),
        previous_issuer_key_id=None,
        previous_issuer_public_key=None,
        issuer_rotation_expires_at=None,
        request_seq=0,
        consumed_commands={"cmd-1": 1},
    )
    channel.save(state)
    payload = {"job_id": "job-1", "cancel_requested": True}
    envelope_body = {
        "org_id": "org-1",
        "node_id": "node-1",
        "purpose": "job.cancel.check",
        "command_id": "cmd-1",
        "nonce": "nonce-1",
        "command_seq": 1,
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
        "payload_sha256": canonical_payload_sha256(payload),
        "issuer_key_id": "issuer-1",
    }
    message = json.dumps(envelope_body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sig = issuer_key.sign(message)
    wrapped = {
        "envelope": {**envelope_body, "sig": base64.b64encode(sig).decode("ascii")},
        "payload": payload,
    }
    assert channel.verify_command_envelope(state, wrapped) is None
