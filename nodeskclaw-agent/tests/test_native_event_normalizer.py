from __future__ import annotations

from app.services.assistant_delta_coalescer import AssistantDeltaCoalescer
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
    traces = n.drain_internal_traces()
    assert traces == [
        {
            "event_type": "internal.runtime.trace",
            "payload": {"runtime_event_type": "subagent.start", "category": "subagent"},
            "source": "agent",
            "source_event_id": traces[0]["source_event_id"],
        }
    ]
    assert n.drain_internal_traces() == []
    assert traces[0]["source_event_id"] == "hermes:att-1:1"
    trace_dump = str(traces)
    assert "child_session_id" not in trace_dump
    assert "output_tail" not in trace_dump
    assert "cost_usd" not in trace_dump
    assert "goal" not in traces[0]["payload"]


# @lat: [[architecture/skill-agent#Hermes Engine Adapter#Runtime Semantic Event Fidelity]]
def test_source_event_id_is_bounded_without_run_or_call_id():
    attempt_id = "183551be-15cc-40f0-8f1a-9b784cf3e345"
    run_id = "d5c83bc0-462f-421c-b5c6-7e275d652510"
    long_call_id = "call-" + ("x" * 200)
    n = NativeEventNormalizer(attempt_id=attempt_id, source_prefix=f"hermes:{attempt_id}")
    started = n.ingest(
        {
            "type": "tool.started",
            "tool": "hermes_marketing__live-tool-call",
            "call_id": long_call_id,
        }
    )
    completed = n.ingest(
        {
            "type": "tool.completed",
            "tool": "hermes_marketing__live-tool-call",
            "call_id": long_call_id,
        }
    )
    assert started[0]["source_event_id"] == f"hermes:{attempt_id}:1"
    assert completed[0]["source_event_id"] == f"hermes:{attempt_id}:2"
    for event in (*started, *completed):
        source_event_id = event["source_event_id"]
        assert len(source_event_id) <= 512
        assert run_id not in source_event_id
        assert long_call_id not in source_event_id
        assert "hermes_marketing__live-tool-call" not in source_event_id
    assert started[0]["payload"]["call_id"] == long_call_id


def test_approval_request_maps_to_requested():
    n = _norm("att-a")
    events = n.ingest({"type": "approval.request", "id": "appr-9", "text": "delete file"})
    assert events[0]["event_type"] == "approval.requested"
    assert events[0]["payload"] == {"approval_id": "appr-9", "summary": "delete file"}


# @lat: [[architecture/skill-agent#Hermes Engine Adapter#Runtime Semantic Event Fidelity]]
def test_run_completed_output_becomes_assistant_message():
    n = _norm("att-out")
    events = n.ingest({"event": "run.completed", "output": "完整中文回复"})
    assert [e["event_type"] for e in events] == ["assistant.message"]
    assert events[0]["payload"]["text"] == "完整中文回复"


# @lat: [[architecture/skill-agent#Hermes Engine Adapter#Runtime Semantic Event Fidelity]]
def test_run_completed_does_not_duplicate_existing_assistant_text():
    n = _norm("att-keep")
    n.ingest({"type": "message.delta", "text": "流上文本"})
    events = n.ingest({"event": "run.completed", "output": "状态回填文本"})
    messages = [e for e in events if e["event_type"] == "assistant.message"]
    assert [e["payload"]["text"] for e in messages] == ["流上文本"]


# @lat: [[architecture/skill-agent#Hermes Engine Adapter#Runtime Semantic Event Fidelity]]
def test_streaming_assistant_message_coalesces_until_close():
    n = _norm("att-stream")
    events = []
    events.extend(n.ingest({"type": "assistant.message", "text": "你好"}))
    events.extend(n.ingest({"type": "assistant.message", "text": "世界"}))
    assert events == []
    closed = n.close(terminal_status="completed")
    messages = [e for e in closed if e["event_type"] == "assistant.message"]
    assert [e["payload"]["text"] for e in messages] == ["你好世界"]


# @lat: [[architecture/skill-agent#Hermes Engine Adapter#Runtime Semantic Event Fidelity]]
def test_long_assistant_text_does_not_flush_until_close():
    n = _norm("att-long")
    chunk = "字" * 200 + "段\n\n落"
    assert n.ingest({"type": "assistant.message", "text": chunk}) == []
    closed = n.close(terminal_status="completed")
    messages = [e for e in closed if e["event_type"] == "assistant.message"]
    assert [e["payload"]["text"] for e in messages] == [chunk]


# @lat: [[architecture/skill-agent#Hermes Engine Adapter#Runtime Semantic Event Fidelity]]
def test_assistant_message_snapshot_does_not_duplicate_deltas():
    n = _norm("att-snap")
    n.ingest({"type": "message.delta", "text": "你好"})
    n.ingest({"type": "message.delta", "text": "世界"})
    assert n.ingest({"type": "assistant.message", "text": "你好世界"}) == []
    closed = n.close(terminal_status="completed")
    messages = [e for e in closed if e["event_type"] == "assistant.message"]
    assert [e["payload"]["text"] for e in messages] == ["你好世界"]


# @lat: [[architecture/skill-agent#Hermes Engine Adapter#Runtime Semantic Event Fidelity]]
def test_emit_assistant_snapshot_is_one_message_and_dedupes():
    n = _norm("att-shot")
    long_text = "字" * 200
    first = n.emit_assistant_snapshot(long_text)
    assert [e["payload"]["text"] for e in first] == [long_text]
    assert n.emit_assistant_snapshot(long_text) == []


# @lat: [[architecture/skill-agent#Hermes Engine Adapter#Runtime Semantic Event Fidelity]]
def test_flush_due_to_latency_waits_one_second():
    clock = {"ms": 0}
    n = NativeEventNormalizer(
        attempt_id="att-lat",
        source_prefix="hermes:att-lat",
        coalescer=AssistantDeltaCoalescer(clock_ms=lambda: clock["ms"]),
    )
    assert n.ingest({"type": "message.delta", "text": "ab"}) == []
    clock["ms"] = 100
    assert n.flush_due_to_latency() == []
    clock["ms"] = 1000
    flushed = n.flush_due_to_latency()
    assert [e["payload"]["text"] for e in flushed] == ["ab"]
