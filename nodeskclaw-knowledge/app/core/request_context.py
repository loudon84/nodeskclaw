"""Request correlation contextvars."""

from __future__ import annotations

import contextvars
import uuid
from collections.abc import Iterator
from contextlib import contextmanager


REQUEST_ID_HEADER = "X-Request-Id"

_request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)
_connector_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("connector_id", default=None)
_sync_run_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("sync_run_id", default=None)
_sync_item_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("sync_item_id", default=None)
_source_object_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("source_object_id", default=None)
_ingestion_job_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "ingestion_job_id", default=None
)


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


def get_connector_id() -> str | None:
    return _connector_id_var.get()


def get_sync_run_id() -> str | None:
    return _sync_run_id_var.get()


def get_sync_item_id() -> str | None:
    return _sync_item_id_var.get()


def get_source_object_id() -> str | None:
    return _source_object_id_var.get()


def get_ingestion_job_id() -> str | None:
    return _ingestion_job_id_var.get()


@contextmanager
def bind_connector_context(
    *,
    connector_id: str | None = None,
    sync_run_id: str | None = None,
    sync_item_id: str | None = None,
    source_object_id: str | None = None,
    ingestion_job_id: str | None = None,
) -> Iterator[None]:
    tokens = []
    if connector_id is not None:
        tokens.append((_connector_id_var, _connector_id_var.set(connector_id)))
    if sync_run_id is not None:
        tokens.append((_sync_run_id_var, _sync_run_id_var.set(sync_run_id)))
    if sync_item_id is not None:
        tokens.append((_sync_item_id_var, _sync_item_id_var.set(sync_item_id)))
    if source_object_id is not None:
        tokens.append((_source_object_id_var, _source_object_id_var.set(source_object_id)))
    if ingestion_job_id is not None:
        tokens.append((_ingestion_job_id_var, _ingestion_job_id_var.set(ingestion_job_id)))
    try:
        yield
    finally:
        for var, token in reversed(tokens):
            var.reset(token)
