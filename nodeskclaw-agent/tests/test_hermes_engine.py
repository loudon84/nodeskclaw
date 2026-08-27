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
async def test_execute_hermes_stub_without_gateway():
    events = [
        event
        async for event in execute_hermes_run(
            tool_name="foo",
            arguments={"prompt": "hi"},
            route_snapshot={},
        )
    ]
    assert events[0]["event_type"] == "run.progress"
    assert events[-1]["event_type"] == "run.completed"
    assert "stub" in events[-1]["payload"]["summary"]


@pytest.mark.asyncio
async def test_execute_hermes_uses_credential_lease():
    from unittest.mock import AsyncMock, MagicMock, patch

    mock_resp = MagicMock()
    mock_resp.headers = {"content-type": "application/json"}
    mock_resp.json.return_value = {"choices": [{"message": {"content": "ok from lease"}}]}
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
                route_snapshot={
                    "gateway_url": "http://hermes:8642",
                    "credential_lease": {"token": "lease-jwt-token", "expires_in": 900},
                },
            )
        ]

    call_kwargs = client.stream.call_args[1]
    assert call_kwargs["headers"]["Authorization"] == "Bearer lease-jwt-token"
    assert events[-1]["payload"]["content"] == "ok from lease"
