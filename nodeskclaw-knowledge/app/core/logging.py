"""Structured JSON logging without secrets or document bodies."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

from app.core.request_context import (
    get_connector_id,
    get_ingestion_job_id,
    get_request_id,
    get_source_object_id,
    get_sync_item_id,
    get_sync_run_id,
)

_SENSITIVE_KEY_RE = re.compile(
    r"(authorization|api[_-]?key|token|password|secret|bearer|ragflow.?key|service.?token|"
    r"access_key|secret_key|aws_secret|credential)",
    re.IGNORECASE,
)
_REDACT = "[REDACTED]"

_CONTEXT_KEYS = (
    "query_id",
    "session_id",
    "message_id",
    "job_id",
    "member_id",
    "org_id",
    "connector_id",
    "sync_run_id",
    "sync_item_id",
    "source_object_id",
    "ingestion_job_id",
)


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"
        record.connector_id = getattr(record, "connector_id", None) or get_connector_id()
        record.sync_run_id = getattr(record, "sync_run_id", None) or get_sync_run_id()
        record.sync_item_id = getattr(record, "sync_item_id", None) or get_sync_item_id()
        record.source_object_id = getattr(record, "source_object_id", None) or get_source_object_id()
        record.ingestion_job_id = getattr(record, "ingestion_job_id", None) or get_ingestion_job_id()
        return True


class SafeJsonFormatter(logging.Formatter):
    """Emit one JSON object per line; never log tokens/keys/full document text."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": self._safe_message(record),
            "request_id": getattr(record, "request_id", None) or get_request_id() or "-",
        }
        for key in _CONTEXT_KEYS:
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exc_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
        return json.dumps(payload, ensure_ascii=False, default=str)

    def _safe_message(self, record: logging.LogRecord) -> str:
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(record.msg)
        if _SENSITIVE_KEY_RE.search(msg):
            return _SENSITIVE_KEY_RE.sub(_REDACT, msg)
        if len(msg) > 2000:
            return msg[:2000] + "...[truncated]"
        return msg


def configure_structured_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(SafeJsonFormatter())
    handler.addFilter(RequestIdFilter())
    root.addHandler(handler)
    root.setLevel(level)
    logging.getLogger("uvicorn.access").addFilter(RequestIdFilter())
    logging.getLogger("uvicorn.error").addFilter(RequestIdFilter())
