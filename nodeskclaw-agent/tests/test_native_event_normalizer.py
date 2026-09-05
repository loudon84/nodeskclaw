from __future__ import annotations

from app.services.native_event_normalizer import NativeEventNormalizer


def _norm(attempt_id: str = "att-1") -> NativeEventNormalizer:
    return NativeEventNormalizer(attempt_id=attempt_id, source_prefix=f"hermes:{attempt_id}")


def test_order_flushes_assistant_before_tool_started():
    n = _norm()
    events = []
    events.extend(n.ingest({"type": "message.delta", "text": "你好"}))
    events.extend(n.ingest({"type": "message.delta", "text": "世界"}))
    events.extend(n.ingest({"event": "tool.started", "tool": "search", "preview": "secret"}))
    types = [e["event_type"] for e in events]
    assert types[:2] == ["assistant.message", "tool.call"]
    assert events[0]["payload"]["text"] == "你好世界"
    assert events[1]["payload"]["status"] == "started"
    assert "preview" not in events[1]["payload"]
    assert "correlation_confidence" not in events[1]["payload"]


def test_call_id_is_stable_across_started_and_completed():
    n = _norm("att-call")
    started = n.ingest({"type": "tool.started", "tool": "search"})
    completed = n.ingest({"type": "tool.completed", "tool": "search", "error": False})
    assert started[0]["payload"]["call_id"] == completed[0]["payload"]["call_id"]
    assert started[0]["payload"]["call_id"] == "att-call:search:1"
    assert completed[0]["payload"]["status"] == "completed"


def test_parallel_same_name_is_low_and_not_public():
    n = _norm("att-p")
    first = n.ingest({"type": "tool.started", "tool": "search"})
    second = n.ingest({"type": "tool.started", "tool": "search"})
    public_payloads = [first[0]["payload"], second[0]["payload"]]
    assert all("correlation_confidence" not in p for p in public_payloads)
    traces = [t for t in n.internal_traces if t["event_type"] == "tool.correlation"]
    assert any(t["payload"]["correlation_confidence"] == "low" for t in traces)
    assert first[0]["payload"]["call_id"] != second[0]["payload"]["call_id"]


def test_unpaired_tool_start_closed_at_terminal():
    n = _norm("att-u")
    n.ingest({"type": "tool.started", "tool": "browser"})
    closed = n.close(terminal_status="failed")
    assert closed[0]["event_type"] == "tool.call"
    assert closed[0]["payload"]["status"] == "failed"
    assert closed[0]["payload"]["tool_name"] == "browser"
    assert n.observability_gaps
    assert n.observability_gaps[0]["kind"] == "unpaired_tool_start"


def test_reasoning_available_does_not_emit_summary():
    n = _norm()
    events = n.ingest({"type": "reasoning.available", "text": "raw chain of thought"})
    assert events == []
    assert all(e["event_type"] != "reasoning.summary" for e in events)
    assert n.internal_traces


def test_subagent_stays_internal_without_sensitive_fields():
    n = _norm()
    events = n.ingest(
        {
            "type": "subagent.start",
            "child_session_id": "child-1",
            "output_tail": "secret-tail",
            "cost_usd": 1.2,
            "goal": "delegate",
        }
    )
    assert events == []
    assert n.internal_traces
    dumped = str(n.internal_traces)
    assert "output_tail" not in dumped
    assert "child_session_id" not in dumped
    assert "cost_usd" not in dumped


def test_approval_request_maps_to_requested():
    n = _norm("att-a")
    events = n.ingest({"type": "approval.request", "id": "appr-9", "text": "delete file"})
    assert events[0]["event_type"] == "approval.requested"
    assert events[0]["payload"] == {"approval_id": "appr-9", "summary": "delete file"}
