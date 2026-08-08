"""Correlation request context and structured logging smoke tests."""

import json
import logging

from app.core.logging import RequestIdFilter, SafeJsonFormatter
from app.core.request_context import ensure_request_id, get_request_id, reset_request_id, set_request_id


def test_request_id_context_roundtrip():
    token = set_request_id("req-123")
    try:
        assert get_request_id() == "req-123"
    finally:
        reset_request_id(token)
    assert get_request_id() is None


def test_ensure_request_id_generates_when_missing():
    value = ensure_request_id(None)
    assert len(value) >= 8


def test_ensure_request_id_preserves_incoming():
    assert ensure_request_id("  client-corr-9  ") == "client-corr-9"


def test_json_formatter_includes_request_id_and_redacts_token():
    token = set_request_id("corr-1")
    try:
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="Authorization Bearer secret-token should hide",
            args=(),
            exc_info=None,
        )
        RequestIdFilter().filter(record)
        line = SafeJsonFormatter().format(record)
        payload = json.loads(line)
        assert payload["request_id"] == "corr-1"
        assert "secret-token" not in payload["msg"]
        assert "[REDACTED]" in payload["msg"]
    finally:
        reset_request_id(token)
