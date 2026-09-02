from __future__ import annotations

import base64
import hashlib
import json
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ForbiddenError
from app.models.connector.edge_control_nonce import EdgeControlNonce
from app.models.connector.edge_node import EdgeNode


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


def _b64_public_key(key: Ed25519PublicKey) -> str:
    return base64.b64encode(key.public_bytes(Encoding.Raw, PublicFormat.Raw)).decode("ascii")


def _load_private_key(raw: str) -> Ed25519PrivateKey:
    value = raw.strip()
    if not value:
        raise ValueError("empty private key")
    try:
        if value.startswith("-----BEGIN"):
            from cryptography.hazmat.primitives.serialization import load_pem_private_key

            loaded = load_pem_private_key(value.encode("utf-8"), password=None)
            if not isinstance(loaded, Ed25519PrivateKey):
                raise ValueError("not Ed25519")
            return loaded
        padded = value + "=" * (-len(value) % 4)
        seed = base64.b64decode(padded)
        return Ed25519PrivateKey.from_private_bytes(seed)
    except Exception as exc:
        raise ValueError("invalid Ed25519 private key") from exc


def _load_public_key(raw: str) -> Ed25519PublicKey:
    value = raw.strip()
    if not value:
        raise ValueError("empty public key")
    try:
        if value.startswith("-----BEGIN"):
            from cryptography.hazmat.primitives.serialization import load_pem_public_key

            loaded = load_pem_public_key(value.encode("utf-8"))
            if not isinstance(loaded, Ed25519PublicKey):
                raise ValueError("not Ed25519")
            return loaded
        padded = value + "=" * (-len(value) % 4)
        key_bytes = base64.b64decode(padded)
        return Ed25519PublicKey.from_public_bytes(key_bytes)
    except Exception as exc:
        raise ValueError("invalid Ed25519 public key") from exc


@dataclass(frozen=True)
class IssuerTrustBundle:
    issuer_key_id: str
    issuer_public_key: str
    previous_issuer_key_id: str | None
    previous_issuer_public_key: str | None
    issuer_rotation_expires_at: datetime | None


class EdgeControlChannel:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def clock_skew_seconds() -> int:
        return int(getattr(settings, "EDGE_CONTROL_CLOCK_SKEW_SECONDS", 60))

    @staticmethod
    def bootstrap_ttl_seconds() -> int:
        return int(getattr(settings, "EDGE_CONTROL_BOOTSTRAP_TTL_SECONDS", 900))

    @staticmethod
    def rotation_window_seconds() -> int:
        return int(getattr(settings, "EDGE_CONTROL_ROTATION_WINDOW_SECONDS", 3600))

    @staticmethod
    def command_ttl_seconds() -> int:
        return int(getattr(settings, "EDGE_CONTROL_COMMAND_TTL_SECONDS", 300))

    def issuer_bundle(self) -> IssuerTrustBundle:
        current_id = settings.EDGE_CONTROL_ISSUER_KEY_ID
        current_key = settings.EDGE_CONTROL_ISSUER_PRIVATE_KEY
        if not current_id or not current_key:
            raise ForbiddenError(
                "Edge 控制通道签发密钥未配置",
                "errors.connector.edge_control_issuer_not_configured",
            )
        current_pub = _b64_public_key(_load_private_key(current_key).public_key())
        prev_id = settings.EDGE_CONTROL_ISSUER_KEY_ID_PREVIOUS or None
        prev_key = settings.EDGE_CONTROL_ISSUER_PRIVATE_KEY_PREVIOUS or ""
        prev_pub = _b64_public_key(_load_private_key(prev_key).public_key()) if prev_key else None
        expires_raw = settings.EDGE_CONTROL_ISSUER_ROTATION_EXPIRES_AT or ""
        rotation_expires = None
        if expires_raw:
            rotation_expires = datetime.fromisoformat(expires_raw.replace("Z", "+00:00"))
        return IssuerTrustBundle(
            issuer_key_id=current_id,
            issuer_public_key=current_pub,
            previous_issuer_key_id=prev_id,
            previous_issuer_public_key=prev_pub,
            issuer_rotation_expires_at=rotation_expires,
        )

    def build_request_message(
        self,
        *,
        node_id: str,
        identity_version: int,
        method: str,
        path: str,
        payload_sha256: str,
        timestamp: int,
        nonce: str,
        seq: int,
    ) -> bytes:
        body = {
            "node_id": node_id,
            "identity_version": identity_version,
            "method": method.upper(),
            "path": path,
            "payload_sha256": payload_sha256,
            "timestamp": timestamp,
            "nonce": nonce,
            "seq": seq,
        }
        return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def verify_node_signature(self, public_key_b64: str, message: bytes, signature_b64: str) -> bool:
        try:
            public_key = _load_public_key(public_key_b64)
            signature = base64.b64decode(signature_b64 + "=" * (-len(signature_b64) % 4))
            public_key.verify(signature, message)
            return True
        except Exception:
            return False

    def _resolve_node_public_keys(self, node: EdgeNode) -> list[str]:
        keys: list[str] = []
        if node.public_key:
            keys.append(node.public_key)
        now = datetime.now(timezone.utc)
        if (
            node.previous_public_key
            and node.identity_rotation_expires_at
            and node.identity_rotation_expires_at >= now
        ):
            keys.append(node.previous_public_key)
        return keys

    async def verify_request_proof(
        self,
        node: EdgeNode,
        *,
        method: str,
        path: str,
        payload_sha256: str,
        timestamp_raw: str | None,
        nonce: str | None,
        seq_raw: str | None,
        identity_version_raw: str | None,
        signature_b64: str | None,
    ) -> None:
        if node.identity_revoked_at is not None:
            raise ForbiddenError("Edge 身份已撤销", "errors.connector.edge_identity_revoked")
        if not node.public_key:
            raise ForbiddenError("Edge 节点尚未绑定身份", "errors.connector.edge_identity_not_bound")
        if not timestamp_raw or not nonce or not seq_raw or not identity_version_raw or not signature_b64:
            raise ForbiddenError("Edge 请求证明缺失", "errors.connector.edge_request_proof_missing")
        try:
            timestamp = int(timestamp_raw)
            seq = int(seq_raw)
            identity_version = int(identity_version_raw)
        except ValueError as exc:
            raise ForbiddenError("Edge 请求证明格式无效", "errors.connector.edge_request_proof_invalid") from exc
        if identity_version != (node.identity_version or 0):
            raise ForbiddenError("Edge 身份版本不匹配", "errors.connector.edge_identity_version_mismatch")
        now = datetime.now(timezone.utc)
        req_time = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        if abs((now - req_time).total_seconds()) > self.clock_skew_seconds():
            raise ForbiddenError("Edge 请求已过期", "errors.connector.edge_request_expired")
        message = self.build_request_message(
            node_id=node.id,
            identity_version=identity_version,
            method=method,
            path=path,
            payload_sha256=payload_sha256,
            timestamp=timestamp,
            nonce=nonce,
            seq=seq,
        )
        if not any(
            self.verify_node_signature(key, message, signature_b64)
            for key in self._resolve_node_public_keys(node)
        ):
            raise ForbiddenError("Edge 请求签名无效", "errors.connector.edge_request_signature_invalid")
        if seq <= (node.last_request_seq or 0):
            raise ForbiddenError("Edge 请求序列乱序", "errors.connector.edge_request_seq_reordered")
        nonce_row = EdgeControlNonce(
            id=str(uuid.uuid4()),
            node_id=node.id,
            identity_version=identity_version,
            nonce=nonce,
        )
        self.db.add(nonce_row)
        try:
            await self.db.flush()
        except Exception as exc:
            raise ForbiddenError("Edge 请求 Nonce 已消费", "errors.connector.edge_request_nonce_reused") from exc
        result = await self.db.execute(
            update(EdgeNode)
            .where(
                EdgeNode.id == node.id,
                EdgeNode.identity_version == identity_version,
                EdgeNode.last_request_seq < seq,
            )
            .values(last_request_seq=seq)
        )
        if result.rowcount != 1:
            raise ForbiddenError("Edge 请求序列冲突", "errors.connector.edge_request_seq_conflict")

    def sign_command_envelope(
        self,
        *,
        org_id: str,
        node_id: str,
        purpose: str,
        payload: dict[str, Any],
        command_seq: int | None = None,
    ) -> dict[str, Any]:
        bundle = self.issuer_bundle()
        private_key = _load_private_key(settings.EDGE_CONTROL_ISSUER_PRIVATE_KEY)
        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=self.command_ttl_seconds())
        payload_sha256 = canonical_payload_sha256(payload)
        command_id = secrets.token_urlsafe(16)
        nonce = secrets.token_urlsafe(16)
        seq = command_seq if command_seq is not None else int(now.timestamp())
        envelope_body = {
            "org_id": org_id,
            "node_id": node_id,
            "purpose": purpose,
            "command_id": command_id,
            "nonce": nonce,
            "command_seq": seq,
            "issued_at": now.isoformat(),
            "expires_at": expires.isoformat(),
            "payload_sha256": payload_sha256,
            "issuer_key_id": bundle.issuer_key_id,
        }
        message = json.dumps(envelope_body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        signature = private_key.sign(message)
        envelope = {
            **envelope_body,
            "sig": base64.b64encode(signature).decode("ascii"),
        }
        return {"envelope": envelope, "payload": payload}

    async def get_node_for_proof(self, node_id: str) -> EdgeNode:
        result = await self.db.execute(select(EdgeNode).where(EdgeNode.id == node_id))
        node = result.scalar_one_or_none()
        if not node or node.deleted_at is not None:
            raise ForbiddenError("Edge 节点不存在", "errors.connector.edge_node_not_found")
        if node.status == "disabled":
            raise ForbiddenError("Edge 节点已禁用", "errors.connector.edge_node_disabled")
        return node
