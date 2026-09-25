from __future__ import annotations

from app.schemas import MAX_TOOL_EVENT_JSON_DEPTH, MAX_TOOL_EVENT_UTF8_BYTES, validate_semantic_event_payload
from app.services.native_event_normalizer import NativeEventNormalizer


def _norm(attempt_id: str = "att-rich") -> NativeEventNormalizer:
    return NativeEventNormalizer(attempt_id=attempt_id, source_prefix=f"hermes:{attempt_id}")


def _payload_size(payload: dict) -> int:
    import json

    return len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def test_started_arguments_object_or_null():
    n = _norm()
    started = n.ingest(
        {
            "type": "tool.started",
            "tool": "search",
            "call_id": "call-1",
            "arguments": {"q": "example"},
        }
    )
    payload = started[0]["payload"]
    assert started[0]["event_type"] == "tool.call"
    assert payload["status"] == "started"
    assert payload["arguments"] == {"q": "example"}
    assert payload["redacted"] is False
    assert payload["truncated"] is False
    assert validate_semantic_event_payload("tool.call", payload) is None

    empty = _norm("att-null").ingest({"type": "tool.started", "tool": "search", "call_id": "call-2"})
    assert empty[0]["payload"]["arguments"] is None
    assert validate_semantic_event_payload("tool.call", empty[0]["payload"]) is None


def test_started_arguments_redacts_secret_and_host_path():
    n = _norm()
    started = n.ingest(
        {
            "type": "tool.started",
            "tool": "fetch",
            "call_id": "call-secret",
            "arguments": {
                "q": "keep",
                "api_key": "sk-live-example",
                "token": "secret-token",
                "path": "/home/user/.ssh/id_rsa",
                "url": "https://example.com/file?signature=abcd&q=ok",
            },
        }
    )
    payload = started[0]["payload"]
    arguments = payload["arguments"]
    assert arguments["q"] == "keep"
    assert "api_key" not in arguments
    assert "token" not in arguments
    assert arguments["path"] == "id_rsa"
    assert "signature=" not in arguments["url"]
    assert "q=ok" in arguments["url"]
    assert payload["redacted"] is True
    assert validate_semantic_event_payload("tool.call", payload) is None


def test_omit_arguments_on_terminal_tool_call():
    n = _norm()
    n.ingest({"type": "tool.started", "tool": "search", "call_id": "call-1", "arguments": {"q": "keep"}})
    completed = n.ingest(
        {
            "type": "tool.completed",
            "tool": "search",
            "call_id": "call-1",
            "arguments": {"q": "keep"},
            "content": "3 results",
        }
    )
    terminal = completed[0]
    assert terminal["event_type"] == "tool.call"
    assert terminal["payload"]["status"] == "completed"
    assert "arguments" not in terminal["payload"]
    assert validate_semantic_event_payload("tool.call", terminal["payload"]) is None


def test_tool_result_exactly_one_per_terminal_and_stable_call_id():
    n = _norm()
    started = n.ingest({"type": "tool.started", "tool": "search", "call_id": "call-1", "arguments": {"q": "keep"}})
    completed = n.ingest(
        {
            "type": "tool.completed",
            "tool": "search",
            "call_id": "call-1",
            "content": "3 results",
            "structured_content": {"n": 3},
        }
    )
    assert started[0]["payload"]["call_id"] == "call-1"
    assert [event["event_type"] for event in completed] == ["tool.call", "tool.result"]
    result = completed[1]
    assert result["payload"]["call_id"] == "call-1"
    assert result["payload"]["status"] == "completed"
    assert result["payload"]["content"] == "3 results"
    assert result["payload"]["structured_content"] == {"n": 3}
    assert validate_semantic_event_payload("tool.result", result["payload"]) is None
    assert sum(1 for event in completed if event["event_type"] == "tool.result") == 1


def test_tool_result_failed_has_error_code():
    n = _norm()
    n.ingest({"type": "tool.started", "tool": "search", "call_id": "call-fail"})
    failed = n.ingest({"type": "tool.failed", "tool": "search", "call_id": "call-fail", "error": "boom"})
    result = next(event for event in failed if event["event_type"] == "tool.result")
    assert result["payload"]["status"] == "failed"
    assert result["payload"]["error_code"]
    assert validate_semantic_event_payload("tool.result", result["payload"]) is None


def test_truncate_oversize_payload_sets_truncated_and_size_limit():
    n = _norm()
    huge = "x" * (MAX_TOOL_EVENT_UTF8_BYTES + 2048)
    started = n.ingest(
        {
            "type": "tool.started",
            "tool": "search",
            "call_id": "call-size",
            "arguments": {"blob": huge},
        }
    )
    payload = started[0]["payload"]
    assert payload["truncated"] is True
    assert _payload_size(payload) <= MAX_TOOL_EVENT_UTF8_BYTES
    assert validate_semantic_event_payload("tool.call", payload) is None


def test_depth_over_limit_sets_truncated():
    n = _norm()
    nested: dict = {"leaf": "ok"}
    for _ in range(MAX_TOOL_EVENT_JSON_DEPTH + 2):
        nested = {"child": nested}
    started = n.ingest(
        {
            "type": "tool.started",
            "tool": "search",
            "call_id": "call-depth",
            "arguments": nested,
        }
    )
    payload = started[0]["payload"]
    assert payload["truncated"] is True
    assert validate_semantic_event_payload("tool.call", payload) is None
