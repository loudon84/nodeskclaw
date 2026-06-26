from datetime import datetime, timezone
from types import SimpleNamespace

from app.models.hermes_skill.hermes_task import EventType
from app.services.hermes_skill.task_event_stream_formatter import (
    build_sse_data,
    format_sse_message,
    resolve_sse_event_name,
    should_enrich_completed,
)


def _event(event_type: EventType, payload: dict | None = None, seq: int = 1):
    return SimpleNamespace(
        event_type=event_type,
        event_seq=seq,
        payload=payload or {},
        created_at=datetime.now(timezone.utc),
    )


def test_resolve_sse_event_name_maps_delta_to_progress():
    event = _event(EventType.HERMES_RUN_DELTA, {"stage": "产品业务"})
    assert resolve_sse_event_name(event) == "task.progress"


def test_resolve_sse_event_name_uses_mcp_event_override():
    event = _event(EventType.HERMES_RUN_DELTA, {"mcp_event": "task.progress", "stage": "芯片推断"})
    assert resolve_sse_event_name(event) == "task.progress"


def test_format_sse_message_completed_with_result():
    event = _event(
        EventType.TASK_COMPLETED,
        {
            "mcp_event": "task.completed",
            "result": {"summary": "完成", "artifacts": [{"name": "report.md"}]},
        },
    )
    message = format_sse_message(event, "task-1")
    assert "event: task.completed" in message
    assert "report.md" in message
    assert "id: task-1-1" in message


def test_should_enrich_completed_when_summary_missing():
    event = _event(EventType.TASK_COMPLETED, {"status": "completed"})
    assert should_enrich_completed(event) is True

    enriched_event = _event(
        EventType.TASK_COMPLETED,
        {"mcp_event": "task.completed", "result": {"summary": "done"}},
    )
    assert should_enrich_completed(enriched_event) is False


def test_build_sse_data_failed_event():
    event = _event(EventType.TASK_FAILED, {"error_message": "boom"})
    data = build_sse_data(event, "task-1")
    assert data["event"] == "task.failed"
    assert data["error"] == "boom"
