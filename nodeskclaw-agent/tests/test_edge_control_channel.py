"""Agent edge control channel tests."""

from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, PublicFormat, NoEncryption

from app.services.edge_control_channel import (
    EdgeControlChannel,
    EdgeIdentityState,
    bind_request_digest,
    canonical_payload_sha256,
)


def _b64_private(key: Ed25519PrivateKey) -> str:
    return base64.b64encode(
        key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    ).decode("ascii")


def _b64_public(key: Ed25519PrivateKey) -> str:
    return base64.b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode("ascii")


def _bound_state(tmp_path: Path, issuer_key: Ed25519PrivateKey, **overrides) -> tuple[EdgeControlChannel, EdgeIdentityState]:
    node_key = Ed25519PrivateKey.generate()
    channel = EdgeControlChannel(tmp_path)
    values = {
        "node_id": "node-1",
        "org_id": "org-1",
        "identity_version": 1,
        "private_key": _b64_private(node_key),
        "public_key": _b64_public(node_key),
        "issuer_key_id": "issuer-1",
        "issuer_public_key": _b64_public(issuer_key),
        "previous_issuer_key_id": None,
        "previous_issuer_public_key": None,
        "issuer_rotation_expires_at": None,
        "request_seq": 0,
        "consumed_commands": {},
        "consumed_nonces": {},
        "last_command_seq": 0,
    }
    values.update(overrides)
    state = EdgeIdentityState(**values)
    channel.save(state)
    return channel, state


def _wrap(issuer_key: Ed25519PrivateKey, payload: dict, *, purpose: str, command_id: str, nonce: str, command_seq: int) -> dict:
    envelope_body = {
        "org_id": "org-1",
        "node_id": "node-1",
        "purpose": purpose,
        "command_id": command_id,
        "nonce": nonce,
        "command_seq": command_seq,
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
        "payload_sha256": canonical_payload_sha256(payload),
        "issuer_key_id": "issuer-1",
    }
    message = json.dumps(envelope_body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sig = issuer_key.sign(message)
    return {
        "envelope": {**envelope_body, "sig": base64.b64encode(sig).decode("ascii")},
        "payload": payload,
    }


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


def test_verify_command_envelope_rejects_unknown_purpose(tmp_path: Path):
    issuer_key = Ed25519PrivateKey.generate()
    channel, state = _bound_state(tmp_path, issuer_key)
    wrapped = _wrap(
        issuer_key,
        {"id": "job-1"},
        purpose="job.forged",
        command_id="cmd-2",
        nonce="nonce-2",
        command_seq=1,
    )
    assert channel.verify_command_envelope(state, wrapped) is None


def test_verify_command_envelope_rejects_purpose_mismatch(tmp_path: Path):
    issuer_key = Ed25519PrivateKey.generate()
    channel, state = _bound_state(tmp_path, issuer_key)
    wrapped = _wrap(
        issuer_key,
        {"id": "job-1"},
        purpose="job.cancel.check",
        command_id="cmd-2",
        nonce="nonce-2",
        command_seq=1,
    )
    assert channel.verify_command_envelope(state, wrapped, expected_purpose="job.claim") is None


def test_verify_command_envelope_rejects_reused_nonce(tmp_path: Path):
    issuer_key = Ed25519PrivateKey.generate()
    channel, state = _bound_state(
        tmp_path,
        issuer_key,
        consumed_nonces={"nonce-1": 1},
        last_command_seq=1,
    )
    wrapped = _wrap(
        issuer_key,
        {"id": "job-2"},
        purpose="job.claim",
        command_id="cmd-2",
        nonce="nonce-1",
        command_seq=2,
    )
    assert channel.verify_command_envelope(state, wrapped, expected_purpose="job.claim") is None


def test_verify_command_envelope_rejects_stale_global_seq(tmp_path: Path):
    issuer_key = Ed25519PrivateKey.generate()
    channel, state = _bound_state(tmp_path, issuer_key, last_command_seq=5)
    wrapped = _wrap(
        issuer_key,
        {"id": "job-2"},
        purpose="job.claim",
        command_id="cmd-new",
        nonce="nonce-new",
        command_seq=4,
    )
    assert channel.verify_command_envelope(state, wrapped, expected_purpose="job.claim") is None


def test_identity_secrets_are_not_written_plaintext(tmp_path: Path):
    issuer_key = Ed25519PrivateKey.generate()
    channel, state = _bound_state(tmp_path, issuer_key, bootstrap="boot-secret")
    raw = json.loads((tmp_path / "edge-identity.json").read_text(encoding="utf-8"))
    assert "private_key" not in raw
    assert "bootstrap" not in raw
    assert raw.get("secrets_blob")
    assert (tmp_path / "edge-identity.key").exists()
    loaded = channel.load()
    assert loaded is not None
    assert loaded.private_key == state.private_key
    assert loaded.bootstrap == "boot-secret"


def test_identity_migrates_legacy_plaintext_file(tmp_path: Path):
    issuer_key = Ed25519PrivateKey.generate()
    node_key = Ed25519PrivateKey.generate()
    private_key = _b64_private(node_key)
    legacy = {
        "node_id": "node-1",
        "org_id": "org-1",
        "identity_version": 1,
        "private_key": private_key,
        "public_key": _b64_public(node_key),
        "issuer_key_id": "issuer-1",
        "issuer_public_key": _b64_public(issuer_key),
        "previous_issuer_key_id": None,
        "previous_issuer_public_key": None,
        "issuer_rotation_expires_at": None,
        "bootstrap": "boot-legacy",
        "request_seq": 0,
        "consumed_commands": {},
    }
    (tmp_path / "edge-identity.json").write_text(json.dumps(legacy), encoding="utf-8")
    channel = EdgeControlChannel(tmp_path)
    loaded = channel.load()
    assert loaded is not None
    assert loaded.private_key == private_key
    assert loaded.bootstrap == "boot-legacy"
    raw = json.loads((tmp_path / "edge-identity.json").read_text(encoding="utf-8"))
    assert "private_key" not in raw
    assert "bootstrap" not in raw
    assert raw.get("secrets_blob")


def test_sign_request_headers_binds_query(tmp_path: Path):
    issuer_key = Ed25519PrivateKey.generate()
    channel, state = _bound_state(tmp_path, issuer_key)
    headers, _updated = channel.sign_request_headers(
        state,
        method="GET",
        path="/api/v1/internal/edge/installations/inst-1/bundle",
        payload=b"",
        query="generation=9",
    )
    assert headers["X-Edge-Payload-Sha256"] == bind_request_digest(body=b"", query="generation=9")
