"""AES-256-GCM credential storage for connectors. Secrets never returned via API."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Protocol

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.base import not_deleted
from app.models.connector import ConnectorCredential


class CredentialProvider(Protocol):
    async def put(self, db: AsyncSession, *, connector_id: str, payload: dict[str, Any], member_id: str) -> ConnectorCredential:
        ...

    async def get(self, db: AsyncSession, *, connector_id: str) -> dict[str, Any]:
        ...

    async def delete(self, db: AsyncSession, *, connector_id: str) -> None:
        ...

    async def rotate(self, db: AsyncSession, *, connector_id: str, payload: dict[str, Any], member_id: str) -> ConnectorCredential:
        ...


def _master_key_bytes() -> bytes:
    raw = (settings.KNOWLEDGE_CONNECTOR_MASTER_KEY or "").strip()
    if not raw:
        raise BadRequestError(
            message="未配置 Connector 主密钥",
            message_key="errors.knowledge.connector_master_key_missing",
        )
    # Accept hex (64 chars) or raw utf-8 padded/truncated to 32 bytes
    if len(raw) == 64:
        try:
            return bytes.fromhex(raw)
        except ValueError:
            pass
    key = raw.encode("utf-8")
    if len(key) < 32:
        key = key.ljust(32, b"\0")
    return key[:32]


def encrypt_payload(payload: dict[str, Any], *, key_version: int = 1) -> tuple[bytes, bytes, int]:
    key = _master_key_bytes()
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    plaintext = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return ciphertext, nonce, key_version


def decrypt_payload(ciphertext: bytes, nonce: bytes, *, key_version: int = 1) -> dict[str, Any]:
    del key_version  # single active key for v1.3
    key = _master_key_bytes()
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    data = json.loads(plaintext.decode("utf-8"))
    if not isinstance(data, dict):
        raise BadRequestError(message="Credential 格式无效", message_key="errors.knowledge.connector_credential_invalid")
    return data


@dataclass
class EncryptedDbCredentialProvider:
    key_version: int = 1

    async def put(
        self,
        db: AsyncSession,
        *,
        connector_id: str,
        payload: dict[str, Any],
        member_id: str,
    ) -> ConnectorCredential:
        ciphertext, nonce, key_version = encrypt_payload(payload, key_version=self.key_version)
        result = await db.execute(
            select(ConnectorCredential).where(
                ConnectorCredential.connector_id == connector_id,
                not_deleted(ConnectorCredential),
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = ConnectorCredential(
                connector_id=connector_id,
                ciphertext=ciphertext,
                nonce=nonce,
                key_version=key_version,
                updated_by_member_id=member_id,
            )
            db.add(row)
        else:
            row.ciphertext = ciphertext
            row.nonce = nonce
            row.key_version = key_version
            row.updated_by_member_id = member_id
        await db.flush()
        return row

    async def get(self, db: AsyncSession, *, connector_id: str) -> dict[str, Any]:
        result = await db.execute(
            select(ConnectorCredential).where(
                ConnectorCredential.connector_id == connector_id,
                not_deleted(ConnectorCredential),
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise NotFoundError(
                message="Connector Credential 不存在",
                message_key="errors.knowledge.connector_credential_not_found",
            )
        return decrypt_payload(row.ciphertext, row.nonce, key_version=row.key_version)

    async def delete(self, db: AsyncSession, *, connector_id: str) -> None:
        result = await db.execute(
            select(ConnectorCredential).where(
                ConnectorCredential.connector_id == connector_id,
                not_deleted(ConnectorCredential),
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return
        row.soft_delete()
        await db.flush()

    async def rotate(
        self,
        db: AsyncSession,
        *,
        connector_id: str,
        payload: dict[str, Any],
        member_id: str,
    ) -> ConnectorCredential:
        return await self.put(db, connector_id=connector_id, payload=payload, member_id=member_id)


def get_credential_provider() -> EncryptedDbCredentialProvider:
    return EncryptedDbCredentialProvider()
