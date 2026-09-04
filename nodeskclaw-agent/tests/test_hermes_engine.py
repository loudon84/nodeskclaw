"""Hermes engine streaming stub behaviour."""

from __future__ import annotations

import pytest

from app.services.hermes_engine import build_chat_completions_payload, execute_hermes_run


def test_build_chat_completions_payload_includes_skill():
    payload = build_chat_completions_payload(
        model_name="m1",
        runtime_skill_id="writer",
        prompt="hello",
        context={"a": 1},
    )
    assert payload["stream"] is True
    assert payload["model"] == "m1"
    assert "writer" in payload["messages"][0]["content"]


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
    from unittest.mock import AsyncMock, MagicMock, patch

    mock_resp = MagicMock()
    mock_resp.headers = {"content-type": "application/json"}
    mock_resp.json.return_value = {"choices": [{"message": {"content": "ok from minted lease"}}]}
    mock_resp.raise_for_status = MagicMock()

    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    client.stream = MagicMock()
    client.stream.return_value.__aenter__.return_value = mock_resp
    client.stream.return_value.__aexit__.return_value = None

    mock_fetch = AsyncMock(return_value={"token": "minted-token-abc", "gateway_url": "http://hermes:8642", "model": "hermes-3"})
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
                route_snapshot={
                    "credential_lease_ref": {"instance_id": "inst-1"},
                },
            )
        ]

    mock_fetch.assert_called_once_with(
        org_id="org-1",
        run_id="run-1",
        attempt_id="att-1",
        lease_ref={"instance_id": "inst-1"},
    )
    call_kwargs = client.stream.call_args[1]
    assert call_kwargs["headers"]["Authorization"] == "Bearer minted-token-abc"
    assert events[-1]["payload"]["content"] == "ok from minted lease"
    assistant_events = [e for e in events if e["event_type"] == "assistant.message"]
    assert len(assistant_events) == 1
    assert assistant_events[0]["payload"]["text"] == "ok from minted lease"
    assert assistant_events[0]["source_event_id"]
    assert "token" not in assistant_events[0]["payload"]
    assert "gateway_url" not in assistant_events[0]["payload"]


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
    # Plaintext token must not be echoed back in error
    assert "raw-plaintext-token-12345" not in events[-1]["payload"]["error"]


@pytest.mark.asyncio
async def test_execute_hermes_lease_fetch_failure_fails_closed_and_redacted():
    from unittest.mock import AsyncMock, patch

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
                route_snapshot={
                    "credential_lease_ref": {"instance_id": "inst-1"},
                },
            )
        ]
    assert events[-1]["event_type"] == "run.failed"
    assert "Credential lease acquisition failed" in events[-1]["payload"]["error"]


@pytest.mark.asyncio
async def test_execute_engine_dispatches_hermes_and_connector_fail_closed():
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.services.engine_port import execute_engine

    # 1. Hermes dispatch
    mock_fetch = AsyncMock(return_value={"token": "minted-token-abc", "gateway_url": "http://hermes:8642", "model": "hermes-3"})
    mock_resp = MagicMock()
    mock_resp.headers = {"content-type": "application/json"}
    mock_resp.json.return_value = {"choices": [{"message": {"content": "hermes output"}}]}
    mock_resp.raise_for_status = MagicMock()

    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    client.stream = MagicMock()
    client.stream.return_value.__aenter__.return_value = mock_resp
    client.stream.return_value.__aexit__.return_value = None

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
    assert events[-1]["payload"]["content"] == "hermes output"

    # 2. Unsupported engine fails closed
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
    from unittest.mock import AsyncMock, MagicMock, patch

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
    from unittest.mock import AsyncMock, MagicMock, patch

    mock_resp = MagicMock()
    mock_resp.headers = {"content-type": "application/json"}
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": "answer text",
                    "tool_calls": [
                        {
                            "id": "call-1",
                            "function": {"name": "search", "arguments": "{\"q\":\"secret\"}"},
                        }
                    ],
                    "reasoning_summary": "safe summary",
                    "clarify": {"question": "Which region?", "options": ["a", "b"]},
                    "approval": {"approval_id": "appr-1", "summary": "Need approval"},
                }
            }
        ]
    }
    mock_resp.raise_for_status = MagicMock()

    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    client.stream = MagicMock()
    client.stream.return_value.__aenter__.return_value = mock_resp
    client.stream.return_value.__aexit__.return_value = None

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
    assert tool_evt["payload"] == {
        "tool_name": "search",
        "call_id": "call-1",
        "status": "started",
    }
    assert "arguments" not in tool_evt["payload"]
    assert tool_evt["source_event_id"]

    progress_payloads = [e["payload"] for e in events if e["event_type"] == "run.progress"]
    assert all("delta" not in p for p in progress_payloads)


@pytest.mark.asyncio
async def test_execute_hermes_plain_text_does_not_infer_semantic_types():
    from unittest.mock import AsyncMock, MagicMock, patch

    mock_resp = MagicMock()
    mock_resp.headers = {"content-type": "text/event-stream"}
    mock_resp.raise_for_status = MagicMock()

    async def fake_lines():
        yield 'data: {"choices":[{"delta":{"content":"Please call the weather tool and approve this"}}]}'
        yield "data: [DONE]"

    mock_resp.aiter_lines = fake_lines

    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    client.stream = MagicMock()
    client.stream.return_value.__aenter__.return_value = mock_resp
    client.stream.return_value.__aexit__.return_value = None

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
    assert "artifact.persisted" not in types
    assistant = next(e for e in events if e["event_type"] == "assistant.message")
    assert assistant["payload"]["text"].startswith("Please call")
    assert "source_event_id" in assistant


@pytest.mark.asyncio
# @lat: [[architecture/skill-agent#Configuration#Gateway Reachability Probe]]
async def test_execute_hermes_fails_closed_when_gateway_probe_times_out():
    from unittest.mock import AsyncMock, MagicMock, patch

    import httpx

    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    client.get = AsyncMock(side_effect=httpx.ConnectTimeout("connect timed out"))
    client.stream = MagicMock()

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
    assert events[-1]["payload"]["error_code"] == "errors.skill_run.gateway_unreachable"
    assert "192.168.102.247:29100" in events[-1]["payload"]["error"]
    client.stream.assert_not_called()


@pytest.mark.asyncio
# @lat: [[architecture/skill-agent#Configuration#Gateway Reachability Probe]]
async def test_execute_hermes_probes_gateway_before_stream():
    from unittest.mock import AsyncMock, MagicMock, patch

    mock_resp = MagicMock()
    mock_resp.headers = {"content-type": "application/json"}
    mock_resp.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
    mock_resp.raise_for_status = MagicMock()

    probe_resp = MagicMock()
    probe_resp.status_code = 404

    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    client.get = AsyncMock(return_value=probe_resp)
    client.stream = MagicMock()
    client.stream.return_value.__aenter__.return_value = mock_resp
    client.stream.return_value.__aexit__.return_value = None

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

    client.get.assert_awaited()
    assert client.get.await_args.args[0] == "http://hermes:8642"
    client.stream.assert_called()
    assert events[-1]["event_type"] == "run.completed"

