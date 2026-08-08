"""Request correlation contextvars."""

from __future__ import annotations

import contextvars
import uuid

REQUEST_ID_HEADER = "X-Request-Id"

_request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    return _request_id_var.get()


def set_request_id(request_id: str) -> contextvars.Token[str | None]:
    return _request_id_var.set(request_id)


def reset_request_id(token: contextvars.Token[str | None]) -> None:
    _request_id_var.reset(token)


def ensure_request_id(raw: str | None) -> str:
    value = (raw or "").strip()
    if value:
        return value[:128]
    return str(uuid.uuid4())
