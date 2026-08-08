"""Opaque token helpers (identity authority is nodeskclaw-backend)."""

import hashlib


def token_cache_key(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
