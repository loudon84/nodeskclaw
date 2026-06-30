import pytest
from app.services.mcp_skill_gateway.handler import (
    _generate_request_trace_id,
    _build_request_snapshot,
)


def test_generate_request_trace_id_prefix():
    trace_id = _generate_request_trace_id()
    assert trace_id.startswith("req_")
    assert len(trace_id) > 10


def test_generate_request_trace_id_unique():
    ids = {_generate_request_trace_id() for _ in range(100)}
    assert len(ids) == 100


def test_build_request_snapshot_basic():
    snapshot = _build_request_snapshot(
        trace_id="req_test",
        tool_name="hermes_xieyi__customer-profiling",
        arguments={"prompt": "分析客户画像"},
        headers={"x-client-name": "copilot-desktop", "x-client-version": "v7.5"},
        auth_ctx=None,
    )
    assert snapshot["trace_id"] == "req_test"
    assert snapshot["entrypoint"] == "mcp_skill_gateway"
    assert snapshot["tool_name"] == "hermes_xieyi__customer-profiling"
    assert snapshot["arguments"]["prompt_preview"] == "分析客户画像"
    assert len(snapshot["arguments"]["prompt_sha256"]) == 64
    assert snapshot["headers_safe"]["x-client-name"] == "copilot-desktop"


def test_build_request_snapshot_sanitizes_auth_headers():
    snapshot = _build_request_snapshot(
        trace_id="req_test",
        tool_name="tool",
        arguments={"prompt": "hi"},
        headers={
            "authorization": "Bearer secret-token",
            "cookie": "session=abc",
            "x-client-name": "copilot-desktop",
        },
        auth_ctx=None,
    )
    assert "authorization" not in snapshot["headers_safe"]
    assert "cookie" not in snapshot["headers_safe"]
    assert snapshot["headers_safe"]["x-client-name"] == "copilot-desktop"


def test_build_request_snapshot_detects_forbidden_keys():
    snapshot = _build_request_snapshot(
        trace_id="req_test",
        tool_name="tool",
        arguments={"prompt": "hi", "_routing": {"agent_id": "x"}, "route_config": {}},
        headers={},
        auth_ctx=None,
    )
    forbidden = snapshot["arguments"]["forbidden_keys"]
    assert "_routing" in forbidden
    assert "route_config" in forbidden


def test_build_request_snapshot_truncates_large_context():
    large_context = {"data": "x" * 50_000}
    snapshot = _build_request_snapshot(
        trace_id="req_test",
        tool_name="tool",
        arguments={"prompt": "hi", "context": large_context},
        headers={},
        auth_ctx=None,
    )
    assert snapshot.get("truncated") is True
    assert snapshot["arguments"]["context"] == {"truncated": True}
