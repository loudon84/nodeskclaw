"""Hermes Native Run Adapter behaviour."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.hermes_engine import (
    REQUIRED_FEATURES,
    RUNTIME_CAPABILITY_MISSING,
    RUNTIME_INTERRUPTED,
    RUNTIME_UNREACHABLE,
    RUNTIME_VERSION_UNSUPPORTED,
    build_native_run_payload,
    execute_hermes_run,
    hermes_version_for_floor,
    parse_hermes_version,
)

FLOOR_CAPS = {
    "version": "v2026.8.31",
    "features": {name: True for name in REQUIRED_FEATURES},
}


@pytest.fixture(autouse=True)
def _stub_binding(monkeypatch):
    async def _gen(_attempt_id: str) -> int:
        return 1

    async def _persist(**kwargs):
        return {
            "runtime_run_id": kwargs["runtime_run_id"],
            "generation": kwargs["generation"],
            "runtime_capability_snapshot": kwargs.get("runtime_capability_snapshot"),
            "runtime_idempotency_key": kwargs.get("runtime_idempotency_key"),
        }

    async def _load(_attempt_id: str):
        return {"runtime_run_id": "rr-1", "generation": 1}

    async def _terminal(**kwargs):
        return None

    monkeypatch.setattr("app.services.hermes_engine.load_attempt_generation", _gen)
    monkeypatch.setattr("app.services.hermes_engine.persist_native_binding", _persist)
    monkeypatch.setattr("app.services.hermes_engine.load_runtime_binding", _load)
    monkeypatch.setattr("app.services.hermes_engine.mark_native_terminal", _terminal)


def _json_response(payload: dict, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = {"content-type": "application/json"}
    resp.json.return_value = payload
    resp.raise_for_status = MagicMock()
    return resp


def _sse_response(lines: list[str], status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = {"content-type": "text/event-stream"}
    resp.raise_for_status = MagicMock()

    async def fake_lines():
        for line in lines:
            yield line

    resp.aiter_lines = fake_lines
    return resp


def _native_client(
    *,
    caps: dict | None = None,
    health: dict | None = None,
    start: dict | None = None,
    status: dict | list | None = None,
    event_lines: list[str] | None = None,
    stop_status: int = 200,
    approval_status: int = 200,
    assistant_text: str = "ok",
):
    caps = caps if caps is not None else FLOOR_CAPS
    start = start if start is not None else {"id": "rr-1", "status": "running"}
    if status is None:
        status_queue: list[dict] = [{"id": "rr-1", "status": "completed"}]
    elif isinstance(status, list):
        status_queue = list(status)
    else:
        status_queue = [status]
    if event_lines is None:
        event_lines = [
            "data: " + json.dumps({"type": "assistant.message", "text": assistant_text}),
            "data: [DONE]",
        ]

    probe_resp = MagicMock()
    probe_resp.status_code = 404
    caps_resp = _json_response(caps)
    health_resp = _json_response(health) if health is not None else probe_resp
    start_resp = _json_response(start)
    stop_resp = MagicMock()
    stop_resp.status_code = stop_status
    approval_resp = MagicMock()
    approval_resp.status_code = approval_status
    sse_resp = _sse_response(event_lines)

    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None

    async def fake_get(url, **kwargs):
        text = str(url)
        if text.rstrip("/").endswith("/v1/capabilities"):
            return caps_resp
        if text.rstrip("/").endswith("/health") or text.rstrip("/").endswith("/health/detailed"):
            return health_resp
        if "/v1/runs/" in text and not text.endswith("/events"):
            payload = status_queue.pop(0) if len(status_queue) > 1 else status_queue[0]
            return _json_response(payload)
        return probe_resp

    async def fake_post(url, **kwargs):
        text = str(url)
        if text.endswith("/v1/runs"):
            return start_resp
        if text.endswith("/stop"):
            return stop_resp
        if text.endswith("/approval"):
            return approval_resp
        raise AssertionError(f"unexpected POST {text}")

    client.get = AsyncMock(side_effect=fake_get)
    client.post = AsyncMock(side_effect=fake_post)
    client.stream = MagicMock()
    client.stream.return_value.__aenter__.return_value = sse_resp
    client.stream.return_value.__aexit__.return_value = None
    return client


def test_build_native_run_payload_includes_skill():
    payload = build_native_run_payload(
        model_name="m1",
        runtime_skill_id="writer",
        prompt="hello",
        context={"a": 1},
    )
    assert "messages" not in payload
    assert payload["model"] == "m1"
    assert payload["input"].startswith("hello")
    assert "writer" in payload["instructions"]
    assert "stream" not in payload


def test_parse_hermes_version_prefers_calendar_tag():
    assert parse_hermes_version("Hermes Agent v0.21.0 (2026.8.31)") == (2026, 8, 31)
    assert parse_hermes_version("v2026.4.23") == (2026, 4, 23)
    assert hermes_version_for_floor("0.21.0") == (2026, 8, 31)
    assert hermes_version_for_floor("0.18.2") == (0, 18, 2)
    assert hermes_version_for_floor("v2026.8.3") == (2026, 8, 3)


@pytest.mark.asyncio
async def test_execute_hermes_fails_without_gateway():
    events = [
        event
        async for event in execute_hermes_run(
            tool_name="foo",
            arguments={"prompt": "hi"},
            route_snapshot={},
        )
    ]
    assert events[0]["event_type"] == "run.progress"
    assert events[-1]["event_type"] == "run.failed"
    assert "No Hermes gateway configured" in events[-1]["payload"]["error"]


@pytest.mark.asyncio
async def test_execute_hermes_uses_minted_credential_lease():
    client = _native_client(assistant_text="ok from minted lease")
    mock_fetch = AsyncMock(
        return_value={"token": "minted-token-abc", "gateway_url": "http://hermes:8642", "model": "hermes-3"}
    )
    with (
        patch("app.services.hermes_engine.fetch_credential_lease", mock_fetch),
        patch("app.services.hermes_engine.httpx.AsyncClient", return_value=client),
    ):
        events = [
            event
            async for event in execute_hermes_run(
                tool_name="foo",
                arguments={"prompt": "hi"},
                org_id="org-1",
                run_id="run-1",
                attempt_id="att-1",
                route_snapshot={"credential_lease_ref": {"instance_id": "inst-1"}},
            )
        ]

    mock_fetch.assert_called_once_with(
        org_id="org-1",
        run_id="run-1",
        attempt_id="att-1",
        lease_ref={"instance_id": "inst-1"},
    )
    start_call = next(c for c in client.post.await_args_list if str(c.args[0]).endswith("/v1/runs"))
    assert start_call.kwargs["headers"]["Authorization"] == "Bearer minted-token-abc"
    assert start_call.kwargs["headers"]["Idempotency-Key"] == "run-1:att-1:1"
    assert "messages" not in start_call.kwargs["json"]
    assert events[-1]["event_type"] == "run.completed"
    assistant_events = [e for e in events if e["event_type"] == "assistant.message"]
    assert len(assistant_events) == 1
    assert assistant_events[0]["payload"]["text"] == "ok from minted lease"
    assert assistant_events[0]["source_event_id"]
    assert "token" not in assistant_events[0]["payload"]
    assert "gateway_url" not in assistant_events[0]["payload"]
    assert "runtime_run_id" not in assistant_events[0]["payload"]


@pytest.mark.asyncio
async def test_execute_hermes_rejects_plaintext_gateway_token_fail_closed():
    events = [
        event
        async for event in execute_hermes_run(
            tool_name="foo",
            arguments={"prompt": "hi"},
            org_id="org-1",
            run_id="run-1",
            attempt_id="att-1",
            route_snapshot={
                "gateway_url": "http://gw:8642",
                "gateway_token": "raw-plaintext-token-12345",
            },
        )
    ]
    assert events[-1]["event_type"] == "run.failed"
    assert "Plaintext credential/env_file in snapshot rejected" in events[-1]["payload"]["error"]
    assert "raw-plaintext-token-12345" not in events[-1]["payload"]["error"]


@pytest.mark.asyncio
async def test_execute_hermes_lease_fetch_failure_fails_closed_and_redacted():
    with patch(
        "app.services.hermes_engine.fetch_credential_lease",
        AsyncMock(return_value=None),
    ):
        events = [
            event
            async for event in execute_hermes_run(
                tool_name="foo",
                arguments={"prompt": "hi"},
                org_id="org-1",
                run_id="run-1",
                attempt_id="att-1",
                route_snapshot={"credential_lease_ref": {"instance_id": "inst-1"}},
            )
        ]
    assert events[-1]["event_type"] == "run.failed"
    assert "Credential lease acquisition failed" in events[-1]["payload"]["error"]


@pytest.mark.asyncio
async def test_execute_engine_dispatches_hermes_and_connector_fail_closed():
    from app.services.engine_port import execute_engine

    mock_fetch = AsyncMock(
        return_value={"token": "minted-token-abc", "gateway_url": "http://hermes:8642", "model": "hermes-3"}
    )
    client = _native_client(assistant_text="hermes output")
    with (
        patch("app.services.hermes_engine.fetch_credential_lease", mock_fetch),
        patch("app.services.hermes_engine.httpx.AsyncClient", return_value=client),
    ):
        events = [
            event
            async for event in execute_engine(
                engine="hermes",
                tool_name="writer",
                arguments={"prompt": "draft"},
                route_snapshot={"credential_lease_ref": {"instance_id": "inst-1"}},
                org_id="org-1",
                run_id="run-1",
                attempt_id="att-1",
            )
        ]
    assert events[-1]["event_type"] == "run.completed"
    assistant = next(e for e in events if e["event_type"] == "assistant.message")
    assert assistant["payload"]["text"] == "hermes output"

    events_unsupported = [
        event
        async for event in execute_engine(
            engine="unknown_engine",
            tool_name="foo",
            arguments={},
            route_snapshot={},
        )
    ]
    assert events_unsupported[-1]["event_type"] == "run.failed"
    assert "Unsupported engine type: unknown_engine (fail-closed)" in events_unsupported[-1]["payload"]["error"]


@pytest.mark.asyncio
async def test_execute_engine_dispatches_connector_with_canonical_route_snapshot():
    from app.services.engine_port import execute_engine

    response = MagicMock()
    response.url = "https://example.com/api"
    response.raise_for_status = MagicMock()
    response.json.return_value = {"ok": True}
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    client.request = AsyncMock(return_value=response)

    with patch("app.services.connector_router.httpx.AsyncClient", return_value=client):
        events = [
            event
            async for event in execute_engine(
                engine="connector",
                tool_name="crm_lookup",
                arguments={"body": {"name": "Acme"}},
                route_snapshot={
                    "connector_kind": "rest",
                    "connector_config": {"url": "https://example.com/api", "method": "POST"},
                },
                org_id="org-1",
                run_id="run-1",
                attempt_id="attempt-1",
            )
        ]

    assert events[-1]["event_type"] == "run.completed"


@pytest.mark.asyncio
async def test_execute_hermes_maps_structured_semantic_fields_only():
    lines = [
        'data: {"type": "assistant.message", "text": "answer text"}',
        'data: {"type": "tool.call", "tool_name": "search", "call_id": "call-1", "status": "started", "arguments": {"q": "secret"}}',
        'data: {"type": "reasoning.summary", "summary": "safe summary"}',
        'data: {"type": "clarify.requested", "question": "Which region?", "options": ["a", "b"]}',
        'data: {"type": "approval.requested", "approval_id": "appr-1", "summary": "Need approval"}',
        "data: [DONE]",
    ]
    client = _native_client(event_lines=lines)
    with patch("app.services.hermes_engine.httpx.AsyncClient", return_value=client):
        events = [
            event
            async for event in execute_hermes_run(
                tool_name="foo",
                arguments={"prompt": "hi"},
                org_id="org-1",
                run_id="run-1",
                attempt_id="att-1",
                route_snapshot={"gateway_url": "http://hermes:8642"},
            )
        ]

    types = [e["event_type"] for e in events]
    assert "assistant.message" in types
    assert "tool.call" in types
    assert "reasoning.summary" in types
    assert "clarify.requested" in types
    assert "approval.requested" in types
    assert "artifact.persisted" not in types
    tool_evt = next(e for e in events if e["event_type"] == "tool.call")
    assert tool_evt["payload"] == {"tool_name": "search", "call_id": "call-1", "status": "started"}
    assert "arguments" not in tool_evt["payload"]
    progress_payloads = [e["payload"] for e in events if e["event_type"] == "run.progress"]
    assert all("delta" not in p for p in progress_payloads)
    assert all("runtime_run_id" not in (e.get("payload") or {}) for e in events)


@pytest.mark.asyncio
async def test_execute_hermes_plain_text_does_not_infer_semantic_types():
    client = _native_client(
        event_lines=[
            'data: {"type": "assistant.message", "text": "Please call the weather tool and approve this"}',
            "data: [DONE]",
        ]
    )
    with patch("app.services.hermes_engine.httpx.AsyncClient", return_value=client):
        events = [
            event
            async for event in execute_hermes_run(
                tool_name="foo",
                arguments={"prompt": "hi"},
                route_snapshot={"gateway_url": "http://hermes:8642"},
                run_id="run-nl",
                attempt_id="att-nl",
            )
        ]

    types = {e["event_type"] for e in events}
    assert "assistant.message" in types
    assert "tool.call" not in types
    assert "clarify.requested" not in types
    assert "approval.requested" not in types
    assert "reasoning.summary" not in types
    assistant = next(e for e in events if e["event_type"] == "assistant.message")
    assert assistant["payload"]["text"].startswith("Please call")


@pytest.mark.asyncio
# @lat: [[architecture/skill-agent#Configuration#Gateway Reachability Probe]]
async def test_execute_hermes_fails_closed_when_gateway_probe_times_out():
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    client.get = AsyncMock(side_effect=httpx.ConnectTimeout("connect timed out"))
    client.stream = MagicMock()
    client.post = AsyncMock()

    with patch("app.services.hermes_engine.httpx.AsyncClient", return_value=client):
        events = [
            event
            async for event in execute_hermes_run(
                tool_name="foo",
                arguments={"prompt": "hi"},
                route_snapshot={"gateway_url": "http://192.168.102.247:29100"},
                run_id="run-gw-timeout",
                attempt_id="att-gw-timeout",
            )
        ]

    assert events[-1]["event_type"] == "run.failed"
    assert events[-1]["payload"]["error_code"] == RUNTIME_UNREACHABLE
    assert "192.168.102.247:29100" in events[-1]["payload"]["error"]
    client.stream.assert_not_called()
    client.post.assert_not_called()


@pytest.mark.asyncio
# @lat: [[architecture/skill-agent#Configuration#Gateway Reachability Probe]]
async def test_execute_hermes_probes_gateway_before_stream():
    client = _native_client()
    with patch("app.services.hermes_engine.httpx.AsyncClient", return_value=client):
        events = [
            event
            async for event in execute_hermes_run(
                tool_name="foo",
                arguments={"prompt": "hi"},
                route_snapshot={"gateway_url": "http://hermes:8642"},
                run_id="run-gw-ok",
                attempt_id="att-gw-ok",
            )
        ]

    assert client.get.await_args_list[0].args[0] == "http://hermes:8642"
    assert any(str(c.args[0]).endswith("/v1/capabilities") for c in client.get.await_args_list)
    client.stream.assert_called()
    stream_url = client.stream.call_args.args[1]
    assert stream_url.endswith("/v1/runs/rr-1/events")
    assert client.stream.call_args.args[0] == "GET"
    assert events[-1]["event_type"] == "run.completed"


@pytest.mark.asyncio
async def test_execute_hermes_low_version_runtime_unsupported():
    client = _native_client(caps={"version": "v2026.8.3", "features": {name: True for name in REQUIRED_FEATURES}})
    with patch("app.services.hermes_engine.httpx.AsyncClient", return_value=client):
        events = [
            event
            async for event in execute_hermes_run(
                tool_name="foo",
                arguments={"prompt": "hi"},
                route_snapshot={"gateway_url": "http://hermes:8642"},
                run_id="run-old",
                attempt_id="att-old",
            )
        ]
    assert events[-1]["payload"]["error_code"] == RUNTIME_VERSION_UNSUPPORTED
    assert not any(str(c.args[0]).endswith("/v1/runs") for c in client.post.await_args_list)
    assert "/v1/chat/completions" not in str(client.post.await_args_list)
    client.stream.assert_not_called()


@pytest.mark.asyncio
async def test_execute_hermes_health_package_version_meets_floor():
    caps = {"features": {name: True for name in REQUIRED_FEATURES}}
    client = _native_client(caps=caps, health={"status": "ok", "version": "0.21.0"})
    with patch("app.services.hermes_engine.httpx.AsyncClient", return_value=client):
        events = [
            event
            async for event in execute_hermes_run(
                tool_name="foo",
                arguments={"prompt": "hi"},
                route_snapshot={"gateway_url": "http://hermes:8642"},
                run_id="run-pkg",
                attempt_id="att-pkg",
            )
        ]
    assert any(str(c.args[0]).endswith("/health") for c in client.get.await_args_list)
    assert any(str(c.args[0]).endswith("/v1/runs") for c in client.post.await_args_list)
    assert events[-1]["event_type"] == "run.completed"


@pytest.mark.asyncio
async def test_execute_hermes_health_old_package_runtime_unsupported():
    caps = {"features": {name: True for name in REQUIRED_FEATURES}}
    client = _native_client(caps=caps, health={"status": "ok", "version": "0.18.2"})
    with patch("app.services.hermes_engine.httpx.AsyncClient", return_value=client):
        events = [
            event
            async for event in execute_hermes_run(
                tool_name="foo",
                arguments={"prompt": "hi"},
                route_snapshot={"gateway_url": "http://hermes:8642"},
                run_id="run-old-pkg",
                attempt_id="att-old-pkg",
            )
        ]
    assert events[-1]["payload"]["error_code"] == RUNTIME_VERSION_UNSUPPORTED
    assert not any(str(c.args[0]).endswith("/v1/runs") for c in client.post.await_args_list)


@pytest.mark.asyncio
async def test_execute_hermes_missing_capability_fail_closed():
    features = {name: True for name in REQUIRED_FEATURES}
    features.pop("run_stop")
    persist_calls: list[dict] = []

    async def _persist(**kwargs):
        persist_calls.append(kwargs)
        return {"runtime_run_id": kwargs["runtime_run_id"], "generation": kwargs["generation"]}

    client = _native_client(caps={"version": "v2026.8.31", "features": features})
    with (
        patch("app.services.hermes_engine.persist_native_binding", _persist),
        patch("app.services.hermes_engine.httpx.AsyncClient", return_value=client),
    ):
        events = [
            event
            async for event in execute_hermes_run(
                tool_name="foo",
                arguments={"prompt": "hi"},
                route_snapshot={"gateway_url": "http://hermes:8642"},
                run_id="run-cap",
                attempt_id="att-cap",
            )
        ]
    assert events[-1]["payload"]["error_code"] == RUNTIME_CAPABILITY_MISSING
    assert persist_calls == []
    client.stream.assert_not_called()


@pytest.mark.asyncio
async def test_execute_hermes_binding_before_events_and_retry_same_runtime_run_id():
    order: list[str] = []
    persist_ids: list[str] = []

    async def _persist(**kwargs):
        order.append("persist")
        persist_ids.append(kwargs["runtime_run_id"])
        return {
            "runtime_run_id": kwargs["runtime_run_id"],
            "generation": kwargs["generation"],
            "runtime_capability_snapshot": kwargs.get("runtime_capability_snapshot"),
        }

    orig_stream_factory = None

    def stream_wrapper(*args, **kwargs):
        order.append("events")
        return orig_stream_factory(*args, **kwargs)

    client = _native_client()
    orig_stream_factory = client.stream
    client.stream = MagicMock(side_effect=lambda *a, **k: (order.append("events") or orig_stream_factory(*a, **k)))

    with (
        patch("app.services.hermes_engine.persist_native_binding", _persist),
        patch("app.services.hermes_engine.httpx.AsyncClient", return_value=client),
    ):
        events = [
            event
            async for event in execute_hermes_run(
                tool_name="foo",
                arguments={"prompt": "hi"},
                route_snapshot={"gateway_url": "http://hermes:8642"},
                run_id="run-bind",
                attempt_id="att-bind",
            )
        ]
        events2 = [
            event
            async for event in execute_hermes_run(
                tool_name="foo",
                arguments={"prompt": "hi"},
                route_snapshot={"gateway_url": "http://hermes:8642"},
                run_id="run-bind",
                attempt_id="att-bind",
            )
        ]

    assert events[-1]["event_type"] == "run.completed"
    assert events2[-1]["event_type"] == "run.completed"
    assert order[:2] == ["persist", "events"]
    assert persist_ids == ["rr-1", "rr-1"]
    keys = [
        c.kwargs["headers"]["Idempotency-Key"]
        for c in client.post.await_args_list
        if str(c.args[0]).endswith("/v1/runs")
    ]
    assert keys == ["run-bind:att-bind:1", "run-bind:att-bind:1"]


@pytest.mark.asyncio
async def test_execute_hermes_reconcil_disconnect_uses_status_not_resubscribe():
    client = _native_client(event_lines=["data: {\"type\": \"assistant.message\", \"text\": \"partial\"}"])
    with patch("app.services.hermes_engine.httpx.AsyncClient", return_value=client):
        events = [
            event
            async for event in execute_hermes_run(
                tool_name="foo",
                arguments={"prompt": "hi"},
                route_snapshot={"gateway_url": "http://hermes:8642"},
                run_id="run-rec",
                attempt_id="att-rec",
            )
        ]
    assert client.stream.call_count == 1
    status_gets = [
        c for c in client.get.await_args_list if "/v1/runs/rr-1" in str(c.args[0]) and not str(c.args[0]).endswith("/events")
    ]
    assert status_gets
    assert events[-1]["event_type"] == "run.completed"
    assert all(not str(c.args[0]).endswith("/events") for c in client.get.await_args_list)


@pytest.mark.asyncio
async def test_execute_hermes_stop_404_reconciles():
    cancel = __import__("asyncio").Event()
    lines_started = __import__("asyncio").Event()

    resp = MagicMock()
    resp.status_code = 200
    resp.headers = {"content-type": "text/event-stream"}

    async def fake_lines():
        cancel.set()
        yield 'data: {"type": "assistant.message", "text": "x"}'
        yield "data: [DONE]"

    resp.aiter_lines = fake_lines
    client = _native_client(stop_status=404, status={"id": "rr-1", "status": "cancelled"})
    client.stream.return_value.__aenter__.return_value = resp

    with patch("app.services.hermes_engine.httpx.AsyncClient", return_value=client):
        events = [
            event
            async for event in execute_hermes_run(
                tool_name="foo",
                arguments={"prompt": "hi"},
                route_snapshot={"gateway_url": "http://hermes:8642"},
                run_id="run-stop",
                attempt_id="att-stop",
                cancel_event=cancel,
            )
        ]
    stop_posts = [c for c in client.post.await_args_list if str(c.args[0]).endswith("/stop")]
    assert stop_posts
    assert events[-1]["event_type"] == "run.cancelled"


@pytest.mark.asyncio
async def test_execute_hermes_stale_generation_does_not_stop():
    async def _stale(_attempt_id: str):
        return {"runtime_run_id": "rr-new", "generation": 2}

    cancel = __import__("asyncio").Event()
    resp = MagicMock()
    resp.status_code = 200
    resp.headers = {"content-type": "text/event-stream"}

    async def fake_lines():
        cancel.set()
        yield 'data: {"type": "assistant.message", "text": "x"}'
        yield "data: [DONE]"

    resp.aiter_lines = fake_lines
    client = _native_client()
    client.stream.return_value.__aenter__.return_value = resp

    with (
        patch("app.services.hermes_engine.load_runtime_binding", _stale),
        patch("app.services.hermes_engine.httpx.AsyncClient", return_value=client),
    ):
        events = [
            event
            async for event in execute_hermes_run(
                tool_name="foo",
                arguments={"prompt": "hi"},
                route_snapshot={"gateway_url": "http://hermes:8642"},
                run_id="run-stale",
                attempt_id="att-stale",
                cancel_event=cancel,
            )
        ]
    assert not any(str(c.args[0]).endswith("/stop") for c in client.post.await_args_list)
    assert any(e["event_type"] == "run.cancelled" for e in events)


@pytest.mark.asyncio
async def test_execute_hermes_error_codes_not_raw_httpx():
    client = _native_client()

    async def boom_post(url, **kwargs):
        if str(url).endswith("/v1/runs"):
            raise httpx.ConnectError("All connection attempts failed: [Errno 111] Connection refused")
        return MagicMock(status_code=200)

    client.post = AsyncMock(side_effect=boom_post)
    with patch("app.services.hermes_engine.httpx.AsyncClient", return_value=client):
        events = [
            event
            async for event in execute_hermes_run(
                tool_name="foo",
                arguments={"prompt": "hi"},
                route_snapshot={"gateway_url": "http://hermes:8642"},
                run_id="run-err",
                attempt_id="att-err",
            )
        ]
    assert events[-1]["event_type"] == "run.failed"
    assert events[-1]["payload"]["error_code"] == RUNTIME_UNREACHABLE
    assert "Connection refused" not in events[-1]["payload"]["error"]
    assert "Errno" not in events[-1]["payload"]["error"]


@pytest.mark.asyncio
async def test_execute_hermes_never_calls_chat_completions():
    client = _native_client()
    with patch("app.services.hermes_engine.httpx.AsyncClient", return_value=client):
        events = [
            event
            async for event in execute_hermes_run(
                tool_name="foo",
                arguments={"prompt": "hi"},
                route_snapshot={"gateway_url": "http://hermes:8642"},
                run_id="run-nat",
                attempt_id="att-nat",
            )
        ]
    posted = [str(c.args[0]) for c in client.post.await_args_list]
    streamed = [str(client.stream.call_args.args[1])] if client.stream.called else []
    assert any(u.endswith("/v1/runs") for u in posted)
    assert all("/v1/chat/completions" not in u for u in posted + streamed)
    assert events[-1]["event_type"] == "run.completed"


@pytest.mark.asyncio
async def test_execute_hermes_progress_has_canonical_phase():
    client = _native_client()
    with patch("app.services.hermes_engine.httpx.AsyncClient", return_value=client):
        events = [
            event
            async for event in execute_hermes_run(
                tool_name="foo",
                arguments={"prompt": "hi"},
                route_snapshot={"gateway_url": "http://hermes:8642"},
                run_id="run-phase",
                attempt_id="att-phase",
            )
        ]
    progress = [e for e in events if e["event_type"] == "run.progress"]
    assert progress
    for item in progress:
        phase = item["payload"]["phase"]
        stage = item["payload"]["stage"]
        assert phase == phase.upper()
        assert stage == phase.lower()


@pytest.mark.asyncio
async def test_execute_hermes_uses_normalizer_not_chat_completion_parser():
    import inspect

    from app.services import hermes_engine as engine

    source = inspect.getsource(engine.execute_hermes_run)
    assert "NativeEventNormalizer" in source
    assert "_emit_semantic_from_choice" not in source
    assert "_map_native_event" not in source
    assert not hasattr(engine, "_emit_semantic_from_choice")

    lines = [
        "data: " + json.dumps({"type": "message.delta", "text": ch})
        for ch in "一二三四五六七八九十" * 9
    ] + ["data: [DONE]"]
    client = _native_client(event_lines=lines)
    with patch("app.services.hermes_engine.httpx.AsyncClient", return_value=client):
        events = [
            event
            async for event in execute_hermes_run(
                tool_name="foo",
                arguments={"prompt": "hi"},
                route_snapshot={"gateway_url": "http://hermes:8642"},
                run_id="run-coal",
                attempt_id="att-coal",
            )
        ]
    messages = [e for e in events if e["event_type"] == "assistant.message"]
    assert "".join(e["payload"]["text"] for e in messages) == "一二三四五六七八九十" * 9
    assert len(messages) < 90


@pytest.mark.asyncio
async def test_execute_hermes_parks_on_waiting_for_approval():
    client = _native_client(
        event_lines=['data: {"type": "approval.request", "approval_id": "appr-1", "summary": "Need approval"}'],
        status=[
            {"id": "rr-1", "status": "waiting_for_approval"},
            {"id": "rr-1", "status": "completed"},
        ],
    )
    with patch("app.services.hermes_engine.httpx.AsyncClient", return_value=client):
        events = [
            event
            async for event in execute_hermes_run(
                tool_name="foo",
                arguments={"prompt": "hi"},
                route_snapshot={"gateway_url": "http://hermes:8642"},
                run_id="run-park",
                attempt_id="att-park",
            )
        ]
    assert client.stream.call_count == 1
    start_posts = [c for c in client.post.await_args_list if str(c.args[0]).endswith("/v1/runs")]
    assert len(start_posts) == 1
    phases = [
        e["payload"].get("phase")
        for e in events
        if e["event_type"] == "run.progress"
    ]
    assert "WAITING_APPROVAL" in phases
    assert events[-1]["event_type"] == "run.completed"


@pytest.mark.asyncio
async def test_execute_hermes_waiting_approval_cancel_stops():
    cancel = __import__("asyncio").Event()
    client = _native_client(
        event_lines=['data: {"type": "approval.request", "approval_id": "appr-1", "summary": "Need approval"}'],
        status={"id": "rr-1", "status": "waiting_for_approval"},
        stop_status=200,
    )
    original_get = client.get.side_effect

    async def get_then_cancel(url, **kwargs):
        text = str(url)
        if "/v1/runs/" in text and not text.endswith("/events") and not text.endswith("/capabilities"):
            cancel.set()
        return await original_get(url, **kwargs)

    client.get = AsyncMock(side_effect=get_then_cancel)
    with patch("app.services.hermes_engine.httpx.AsyncClient", return_value=client):
        events = [
            event
            async for event in execute_hermes_run(
                tool_name="foo",
                arguments={"prompt": "hi"},
                route_snapshot={"gateway_url": "http://hermes:8642"},
                run_id="run-wait-stop",
                attempt_id="att-wait-stop",
                cancel_event=cancel,
            )
        ]
    stop_posts = [c for c in client.post.await_args_list if str(c.args[0]).endswith("/stop")]
    assert stop_posts
    assert events[-1]["event_type"] in {"run.cancelled", "run.failed"}


@pytest.mark.asyncio
async def test_respond_runtime_approval_posts_once():
    from app.services.hermes_engine import respond_runtime_approval

    client = _native_client()
    with patch("app.services.hermes_engine.httpx.AsyncClient", return_value=client):
        result = await respond_runtime_approval(
            attempt_id="att-1",
            generation=1,
            choice="approve",
            gateway_url="http://hermes:8642",
        )
    assert result is None
    approval_posts = [c for c in client.post.await_args_list if str(c.args[0]).endswith("/approval")]
    assert len(approval_posts) == 1
    assert approval_posts[0].kwargs.get("json", {}).get("choice") == "once"


@pytest.mark.asyncio
async def test_respond_runtime_approval_stale_generation_does_not_post():
    from app.services.hermes_engine import respond_runtime_approval

    async def _stale(_attempt_id: str):
        return {"runtime_run_id": "rr-1", "generation": 2}

    client = _native_client()
    with patch("app.services.hermes_engine.load_runtime_binding", _stale):
        with patch("app.services.hermes_engine.httpx.AsyncClient", return_value=client):
            result = await respond_runtime_approval(
                attempt_id="att-1",
                generation=1,
                choice="once",
                gateway_url="http://hermes:8642",
            )
    assert result == "fenced"
    approval_posts = [c for c in client.post.await_args_list if str(c.args[0]).endswith("/approval")]
    assert approval_posts == []


@pytest.mark.asyncio
async def test_execute_hermes_interrupted_fails_without_new_submit():
    client = _native_client(status={"id": "rr-1", "status": "interrupted"})
    with patch("app.services.hermes_engine.httpx.AsyncClient", return_value=client):
        events = [
            event
            async for event in execute_hermes_run(
                tool_name="foo",
                arguments={"prompt": "hi"},
                route_snapshot={"gateway_url": "http://hermes:8642"},
                run_id="run-int",
                attempt_id="att-int",
            )
        ]
    start_posts = [c for c in client.post.await_args_list if str(c.args[0]).endswith("/v1/runs")]
    assert len(start_posts) == 1
    assert events[-1]["event_type"] == "run.failed"
    assert events[-1]["payload"]["error_code"] == RUNTIME_INTERRUPTED

