"""AES-256-GCM for member model credentials.

The key comes only from MODEL_TOKEN_ENCRYPTION_KEY. KubeConfig ENCRYPTION_KEY is not used.
"""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings
from app.core.exceptions import AppException

_PREFIX = "enc:v1:"


class MemberTokenError(AppException):
    def __init__(self, status_code: int, message_key: str, message: str):
        super().__init__(
            code=status_code * 100,
            message=message,
            status_code=status_code,
            message_key=message_key,
            error_code=status_code * 100,
        )


def load_model_token_key() -> bytes:
    raw = (settings.MODEL_TOKEN_ENCRYPTION_KEY or "").strip()
    if not raw:
        raise MemberTokenError(
            503,
            "errors.member_token.encryption_not_configured",
            "模型凭证加密密钥未配置，请在 backend 环境变量中设置 MODEL_TOKEN_ENCRYPTION_KEY",
        )
    try:
        key = base64.b64decode(raw, validate=True)
    except Exception as exc:
        raise MemberTokenError(
            503,
            "errors.member_token.encryption_not_configured",
            "MODEL_TOKEN_ENCRYPTION_KEY 不是合法的 base64",
        ) from exc
    if len(key) != 32:
        raise MemberTokenError(
            503,
            "errors.member_token.encryption_not_configured",
            "MODEL_TOKEN_ENCRYPTION_KEY 解码后必须是 32 字节",
        )
    return key


def credential_aad(token_id: str, member_id: str, provider: str) -> bytes:
    return f"member_token:v1:{token_id}:{member_id}:{provider}".encode()


def fingerprint_token(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def encrypt_member_token(
    plaintext: str,
    *,
    token_id: str,
    member_id: str,
    provider: str,
) -> str:
    if plaintext is None or plaintext == "":
        raise MemberTokenError(400, "errors.member_token.token_required", "模型凭证不能为空")
    aesgcm = AESGCM(load_model_token_key())
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(
        nonce,
        plaintext.encode("utf-8"),
        credential_aad(token_id, member_id, provider),
    )
    blob = base64.b64encode(nonce + ciphertext).decode("ascii")
    return f"{_PREFIX}{blob}"


def decrypt_member_token(
    stored: str,
    *,
    token_id: str,
    member_id: str,
    provider: str,
) -> str:
    if not stored.startswith(_PREFIX):
        raise MemberTokenError(
            500,
            "errors.member_token.decrypt_failed",
            "模型凭证密文格式无法识别",
        )
    try:
        raw = base64.b64decode(stored[len(_PREFIX):], validate=True)
        nonce, ciphertext = raw[:12], raw[12:]
        plaintext = AESGCM(load_model_token_key()).decrypt(
            nonce,
            ciphertext,
            credential_aad(token_id, member_id, provider),
        )
    except MemberTokenError:
        raise
    except Exception as exc:
        raise MemberTokenError(
            500,
            "errors.member_token.decrypt_failed",
            "模型凭证解密失败",
        ) from exc
    return plaintext.decode("utf-8")
