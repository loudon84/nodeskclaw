"""Structured JSON logging without secrets or document bodies."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

from app.core.request_context import get_request_id

_SENSITIVE_KEY_RE = re.compile(
    r"(authorization|api[_-]?key|token|password|secret|bearer|ragflow.?key|service.?token)",
    re.IGNORECASE,
)
_REDACT = "[REDACTED]"


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"
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
        for key in ("query_id", "session_id", "message_id", "job_id", "member_id", "org_id"):
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
