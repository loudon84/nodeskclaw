"""Correlation request context and structured logging smoke tests."""

import json
import logging

from app.core.logging import RequestIdFilter, SafeJsonFormatter
from app.core.request_context import (
    bind_connector_context,
    ensure_request_id,
    get_connector_id,
    get_ingestion_job_id,
    get_request_id,
    get_sync_run_id,
    reset_request_id,
    set_request_id,
)


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


def test_connector_context_bound():
    with bind_connector_context(connector_id="c1", sync_run_id="r1", ingestion_job_id="j1"):
        assert get_connector_id() == "c1"
        assert get_sync_run_id() == "r1"
        assert get_ingestion_job_id() == "j1"
    assert get_connector_id() is None


def test_json_formatter_includes_request_id_and_redacts_token():
    token = set_request_id("corr-1")
    try:
        with bind_connector_context(connector_id="conn-9", sync_run_id="run-9"):
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname=__file__,
                lineno=1,
                msg="Authorization Bearer secret-token should hide aws_secret_access_key=abc",
                args=(),
                exc_info=None,
            )
            RequestIdFilter().filter(record)
            line = SafeJsonFormatter().format(record)
            payload = json.loads(line)
            assert payload["request_id"] == "corr-1"
            assert payload["connector_id"] == "conn-9"
            assert payload["sync_run_id"] == "run-9"
            assert "secret-token" not in payload["msg"]
            assert "[REDACTED]" in payload["msg"]
    finally:
        reset_request_id(token)
