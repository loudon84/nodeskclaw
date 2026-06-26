from app.services.mcp_skill_gateway.handler import _build_hermes_skill_text, _redact_event_stream


def test_build_hermes_skill_text_async_event():
    text = _build_hermes_skill_text({
        "task_no": "TASK-001",
        "status": "running",
        "execution_mode": "async_event",
    })
    assert "TASK-001" in text
    assert "不要重复调用" in text
    assert "事件流" in text


def test_redact_event_stream_masks_token():
    redacted = _redact_event_stream(
        "/api/v1/hermes/tasks/task-1/events?token=sse_secret"
    )
    assert redacted.endswith("?token=***")
    assert "sse_secret" not in redacted
