from __future__ import annotations

import base64
import hashlib
import hmac
import time

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def body_sha256(raw_body: bytes) -> str:
    return hashlib.sha256(raw_body).hexdigest()


def sign_payload(*, secret: str, timestamp: str, nonce: str, body_digest: str) -> str:
    message = f"{timestamp}.{nonce}.{body_digest}".encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def verify_webhook_signature(
    *,
    secret: str,
    timestamp: str,
    nonce: str,
    signature: str,
    raw_body: bytes,
    now: float | None = None,
    skew_seconds: int = 300,
) -> str | None:
    if not timestamp or not nonce or not signature:
        return "WEBHOOK_AUTH_FAILED"
    try:
        ts = int(timestamp)
    except ValueError:
        return "WEBHOOK_AUTH_FAILED"
    current = int(now if now is not None else time.time())
    if abs(current - ts) > skew_seconds:
        return "WEBHOOK_AUTH_FAILED"
    digest = body_sha256(raw_body)
    expected = sign_payload(secret=secret, timestamp=timestamp, nonce=nonce, body_digest=digest)
    if not hmac.compare_digest(expected, signature):
        return "WEBHOOK_AUTH_FAILED"
    return None


def hash_webhook_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _fernet() -> Fernet:
    digest = hashlib.sha256(settings.JWT_SECRET.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def seal_webhook_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode("utf-8")).decode("utf-8")


def open_webhook_secret(ciphertext: str) -> str | None:
    try:
        return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None
