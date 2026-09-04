from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, PublicFormat, NoEncryption

COMMAND_PURPOSES = frozenset(
    {"job.claim", "install.desired", "artifact.on_demand", "job.cancel.check"}
)


def canonical_payload_sha256(payload: Any) -> str:
    if payload is None:
        raw = b""
    elif isinstance(payload, (bytes, bytearray)):
        raw = bytes(payload)
    elif isinstance(payload, str):
        raw = payload.encode("utf-8")
    else:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def canonical_query(query: str) -> str:
    if not query:
        return ""
    pairs = parse_qsl(query, keep_blank_values=True)
    return urlencode(sorted(pairs), doseq=True)


def bind_request_digest(*, body: bytes | None = None, query: str = "") -> str:
    raw = body or b""
    if raw:
        try:
            body_digest = canonical_payload_sha256(json.loads(raw))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            body_digest = canonical_payload_sha256(raw)
    else:
        body_digest = canonical_payload_sha256(b"")
    canon_q = canonical_query(query)
    if not canon_q:
        return body_digest
    return canonical_payload_sha256({"query": canon_q, "body_sha256": body_digest})


def _b64_public_key(key: Ed25519PublicKey) -> str:
    return base64.b64encode(key.public_bytes(Encoding.Raw, PublicFormat.Raw)).decode("ascii")


def _b64_private_key(key: Ed25519PrivateKey) -> str:
    return base64.b64encode(key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())).decode("ascii")


def _load_public_key(raw: str) -> Ed25519PublicKey:
    padded = raw.strip() + "=" * (-len(raw.strip()) % 4)
    return Ed25519PublicKey.from_public_bytes(base64.b64decode(padded))


def _load_private_key(raw: str) -> Ed25519PrivateKey:
    padded = raw.strip() + "=" * (-len(raw.strip()) % 4)
    return Ed25519PrivateKey.from_private_bytes(base64.b64decode(padded))


def _payload_bytes(payload: Any) -> bytes:
    if payload is None:
        return b""
    if isinstance(payload, (bytes, bytearray)):
        return bytes(payload)
    if isinstance(payload, str):
        return payload.encode("utf-8")
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass
class EdgeIdentityState:
    node_id: str
    org_id: str
    identity_version: int
    private_key: str
    public_key: str
    issuer_key_id: str
    issuer_public_key: str
    previous_issuer_key_id: str | None
    previous_issuer_public_key: str | None
    issuer_rotation_expires_at: str | None
    bootstrap: str | None = None
    request_seq: int = 0
    consumed_commands: dict[str, int] | None = None
    consumed_nonces: dict[str, int] | None = None
    last_command_seq: int = 0

    def public_to_json(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "org_id": self.org_id,
            "identity_version": self.identity_version,
            "public_key": self.public_key,
            "issuer_key_id": self.issuer_key_id,
            "issuer_public_key": self.issuer_public_key,
            "previous_issuer_key_id": self.previous_issuer_key_id,
            "previous_issuer_public_key": self.previous_issuer_public_key,
            "issuer_rotation_expires_at": self.issuer_rotation_expires_at,
            "request_seq": self.request_seq,
            "consumed_commands": self.consumed_commands or {},
            "consumed_nonces": self.consumed_nonces or {},
            "last_command_seq": self.last_command_seq,
        }

    def secrets_to_json(self) -> dict[str, Any]:
        blob: dict[str, Any] = {"private_key": self.private_key}
        if self.bootstrap:
            blob["bootstrap"] = self.bootstrap
        return blob

    @classmethod
    def from_json(cls, data: dict[str, Any], *, secrets: dict[str, Any] | None = None) -> EdgeIdentityState:
        secret_data = secrets or {}
        private_key = str(secret_data.get("private_key") or data.get("private_key") or "")
        bootstrap = secret_data.get("bootstrap")
        if bootstrap is None:
            bootstrap = data.get("bootstrap")
        return cls(
            node_id=str(data["node_id"]),
            org_id=str(data["org_id"]),
            identity_version=int(data.get("identity_version") or 0),
            private_key=private_key,
            public_key=str(data["public_key"]),
            issuer_key_id=str(data["issuer_key_id"]),
            issuer_public_key=str(data["issuer_public_key"]),
            previous_issuer_key_id=data.get("previous_issuer_key_id"),
            previous_issuer_public_key=data.get("previous_issuer_public_key"),
            issuer_rotation_expires_at=data.get("issuer_rotation_expires_at"),
            bootstrap=bootstrap,
            request_seq=int(data.get("request_seq") or 0),
            consumed_commands=dict(data.get("consumed_commands") or {}),
            consumed_nonces=dict(data.get("consumed_nonces") or {}),
            last_command_seq=int(data.get("last_command_seq") or 0),
        )


class EdgeControlChannel:
    def __init__(self, store_root: str | Path) -> None:
        self._root = Path(store_root)
        self._identity_path = self._root / "edge-identity.json"
        self._wrap_key_path = self._root / "edge-identity.key"
        self._root.mkdir(parents=True, exist_ok=True)

    def _chmod_private(self, path: Path) -> None:
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

    def _atomic_write_bytes(self, path: Path, data: bytes) -> None:
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_bytes(data)
        self._chmod_private(tmp)
        tmp.replace(path)
        self._chmod_private(path)

    def _atomic_write_text(self, path: Path, text: str) -> None:
        self._atomic_write_bytes(path, text.encode("utf-8"))

    def _load_or_create_fernet(self) -> Fernet:
        if self._wrap_key_path.exists():
            raw = self._wrap_key_path.read_bytes().strip()
            return Fernet(raw)
        key = Fernet.generate_key()
        self._atomic_write_bytes(self._wrap_key_path, key)
        return Fernet(key)

    def load(self) -> EdgeIdentityState | None:
        if not self._identity_path.exists():
            return None
        data = json.loads(self._identity_path.read_text(encoding="utf-8"))
        secrets_blob = data.get("secrets_blob")
        secret_data: dict[str, Any] | None = None
        if secrets_blob:
            if not self._wrap_key_path.exists():
                raise RuntimeError("edge identity wrap key missing")
            try:
                fernet = Fernet(self._wrap_key_path.read_bytes().strip())
                secret_data = json.loads(fernet.decrypt(str(secrets_blob).encode("ascii")))
            except (InvalidToken, ValueError, json.JSONDecodeError) as exc:
                raise RuntimeError("edge identity secrets unreadable") from exc
        state = EdgeIdentityState.from_json(data, secrets=secret_data)
        if not state.private_key:
            raise RuntimeError("edge identity private key missing")
        if secrets_blob is None and (data.get("private_key") or data.get("bootstrap")):
            self.save(state)
        return state

    def save(self, state: EdgeIdentityState) -> None:
        fernet = self._load_or_create_fernet()
        public = state.public_to_json()
        encrypted = fernet.encrypt(
            json.dumps(state.secrets_to_json(), separators=(",", ":")).encode("utf-8")
        ).decode("ascii")
        public["secrets_blob"] = encrypted
        self._atomic_write_text(
            self._identity_path,
            json.dumps(public, indent=2, sort_keys=True),
        )

    def ensure_bootstrap_identity(self, *, node_id: str, org_id: str, bootstrap: str) -> EdgeIdentityState:
        existing = self.load()
        if existing and existing.node_id == node_id:
            existing.bootstrap = bootstrap
            self.save(existing)
            return existing
        private_key = Ed25519PrivateKey.generate()
        state = EdgeIdentityState(
            node_id=node_id,
            org_id=org_id,
            identity_version=0,
            private_key=_b64_private_key(private_key),
            public_key=_b64_public_key(private_key.public_key()),
            issuer_key_id="",
            issuer_public_key="",
            previous_issuer_key_id=None,
            previous_issuer_public_key=None,
            issuer_rotation_expires_at=None,
            bootstrap=bootstrap,
            request_seq=0,
            consumed_commands={},
            consumed_nonces={},
            last_command_seq=0,
        )
        self.save(state)
        return state

    def apply_bind_response(self, state: EdgeIdentityState, data: dict[str, Any]) -> EdgeIdentityState:
        state.identity_version = int(data["identity_version"])
        state.org_id = str(data.get("org_id") or state.org_id)
        state.issuer_key_id = str(data["issuer_key_id"])
        state.issuer_public_key = str(data["issuer_public_key"])
        state.previous_issuer_key_id = data.get("previous_issuer_key_id")
        state.previous_issuer_public_key = data.get("previous_issuer_public_key")
        state.issuer_rotation_expires_at = data.get("issuer_rotation_expires_at")
        state.bootstrap = None
        state.request_seq = 0
        self.save(state)
        return state

    def build_request_message(
        self,
        state: EdgeIdentityState,
        *,
        method: str,
        path: str,
        payload_sha256: str,
        timestamp: int,
        nonce: str,
        seq: int,
    ) -> bytes:
        body = {
            "node_id": state.node_id,
            "identity_version": state.identity_version,
            "method": method.upper(),
            "path": path,
            "payload_sha256": payload_sha256,
            "timestamp": timestamp,
            "nonce": nonce,
            "seq": seq,
        }
        return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def sign_request_headers(
        self,
        state: EdgeIdentityState,
        *,
        method: str,
        path: str,
        payload: Any = b"",
        query: str = "",
    ) -> tuple[dict[str, str], EdgeIdentityState]:
        if state.identity_version <= 0 or not state.issuer_key_id:
            raise RuntimeError("edge identity not bound")
        state.request_seq += 1
        seq = state.request_seq
        nonce = secrets.token_urlsafe(16)
        timestamp = int(datetime.now(timezone.utc).timestamp())
        payload_sha256 = bind_request_digest(body=_payload_bytes(payload), query=query)
        message = self.build_request_message(
            state,
            method=method,
            path=path,
            payload_sha256=payload_sha256,
            timestamp=timestamp,
            nonce=nonce,
            seq=seq,
        )
        private_key = _load_private_key(state.private_key)
        signature = private_key.sign(message)
        headers = {
            "X-Edge-Node-Id": state.node_id,
            "X-Edge-Identity-Version": str(state.identity_version),
            "X-Edge-Timestamp": str(timestamp),
            "X-Edge-Nonce": nonce,
            "X-Edge-Seq": str(seq),
            "X-Edge-Payload-Sha256": payload_sha256,
            "X-Edge-Signature": base64.b64encode(signature).decode("ascii"),
        }
        self.save(state)
        return headers, state

    def _issuer_keys(self, state: EdgeIdentityState) -> dict[str, str]:
        keys = {state.issuer_key_id: state.issuer_public_key}
        if state.previous_issuer_key_id and state.previous_issuer_public_key:
            if state.issuer_rotation_expires_at:
                expires = datetime.fromisoformat(state.issuer_rotation_expires_at.replace("Z", "+00:00"))
                if expires >= datetime.now(timezone.utc):
                    keys[state.previous_issuer_key_id] = state.previous_issuer_public_key
        return keys

    def verify_command_envelope(
        self,
        state: EdgeIdentityState,
        wrapped: dict[str, Any],
        expected_purpose: str | None = None,
    ) -> dict[str, Any] | None:
        envelope = wrapped.get("envelope")
        payload = wrapped.get("payload")
        if not isinstance(envelope, dict) or not isinstance(payload, dict):
            return None
        if envelope.get("node_id") != state.node_id or envelope.get("org_id") != state.org_id:
            return None
        if canonical_payload_sha256(payload) != envelope.get("payload_sha256"):
            return None
        purpose = str(envelope.get("purpose") or "")
        if purpose not in COMMAND_PURPOSES:
            return None
        if expected_purpose is not None and purpose != expected_purpose:
            return None
        expires_raw = envelope.get("expires_at")
        if expires_raw:
            expires = datetime.fromisoformat(str(expires_raw).replace("Z", "+00:00"))
            if expires < datetime.now(timezone.utc):
                return None
        issuer_keys = self._issuer_keys(state)
        issuer_key_id = envelope.get("issuer_key_id")
        if issuer_key_id not in issuer_keys:
            return None
        envelope_copy = {k: v for k, v in envelope.items() if k != "sig"}
        message = json.dumps(envelope_copy, sort_keys=True, separators=(",", ":")).encode("utf-8")
        sig = envelope.get("sig")
        if not isinstance(sig, str):
            return None
        try:
            public_key = _load_public_key(issuer_keys[str(issuer_key_id)])
            public_key.verify(base64.b64decode(sig + "=" * (-len(sig) % 4)), message)
        except Exception:
            return None
        command_id = str(envelope.get("command_id") or "")
        nonce = str(envelope.get("nonce") or "")
        if not command_id or not nonce:
            return None
        command_seq = int(envelope.get("command_seq") or 0)
        consumed = state.consumed_commands or {}
        consumed_nonces = state.consumed_nonces or {}
        if command_id in consumed:
            return None
        if nonce in consumed_nonces:
            return None
        if command_seq <= int(state.last_command_seq or 0):
            return None
        consumed[command_id] = command_seq
        consumed_nonces[nonce] = command_seq
        state.consumed_commands = consumed
        state.consumed_nonces = consumed_nonces
        state.last_command_seq = command_seq
        self.save(state)
        return payload

    def unwrap_or_none(
        self,
        state: EdgeIdentityState,
        wrapped: Any,
        expected_purpose: str | None = None,
    ) -> dict[str, Any] | None:
        if not isinstance(wrapped, dict):
            return None
        if "envelope" in wrapped and "payload" in wrapped:
            return self.verify_command_envelope(state, wrapped, expected_purpose=expected_purpose)
        return None
