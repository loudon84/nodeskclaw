from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.connector_router import execute_connector_run


@pytest.mark.asyncio
async def test_execute_rest_connector_happy_path():
    response = MagicMock()
    response.url = "https://example.com/api"
    response.raise_for_status = MagicMock()
    response.json.return_value = {"ok": True}
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    client.request = AsyncMock(return_value=response)

    snapshot = {
        "runtime_policy": {
            "connector_kind": "rest",
            "connector_config": {"url": "https://example.com/api", "method": "POST"},
        }
    }
    with patch("app.services.connector_router.httpx.AsyncClient", return_value=client):
        events = [event async for event in execute_connector_run(tool_name="crm_lookup", arguments={"body": {"q": "acme"}}, snapshot=snapshot)]

    assert events[-1]["event_type"] == "run.completed"
    assert "REST connector completed" in events[-1]["payload"]["summary"]


@pytest.mark.asyncio
async def test_execute_mcp_connector_happy_path():
    response = MagicMock()
    response.url = "https://example.com/mcp"
    response.raise_for_status = MagicMock()
    response.json.return_value = {"jsonrpc": "2.0", "id": "connector-call", "result": {"ok": True}}
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    client.post = AsyncMock(return_value=response)

    snapshot = {
        "runtime_policy": {
            "connector_kind": "mcp",
            "connector_config": {
                "url": "https://example.com/mcp",
                "remote_tool_name": "search",
            },
        }
    }
    with patch("app.services.connector_router.httpx.AsyncClient", return_value=client):
        events = [
            event
            async for event in execute_connector_run(
                tool_name="mcp_search",
                arguments={"remote_arguments": {"q": "acme"}},
                snapshot=snapshot,
            )
        ]

    assert events[-1]["event_type"] == "run.completed"
    assert "MCP connector completed" in events[-1]["payload"]["summary"]
    client.post.assert_awaited()
    call_kwargs = client.post.await_args
    assert call_kwargs.args[0] == "https://example.com/mcp"
    assert call_kwargs.kwargs["json"]["method"] == "tools/call"
    assert call_kwargs.kwargs["json"]["params"]["name"] == "search"


@pytest.mark.asyncio
async def test_execute_rest_connector_blocks_ssrf():
    snapshot = {
        "runtime_policy": {
            "connector_kind": "rest",
            "connector_config": {"url": "http://169.254.169.254/latest/meta-data/"},
        }
    }
    with pytest.raises(RuntimeError, match="SSRF blocked"):
        async for _ in execute_connector_run(tool_name="ssrf_attempt", arguments={}, snapshot=snapshot):
            pass

    # Test .internal domain blocking
    snapshot_internal = {
        "runtime_policy": {
            "connector_kind": "rest",
            "connector_config": {"url": "http://metadata.google.internal/computeMetadata/v1/"},
        }
    }
    with pytest.raises(RuntimeError, match="SSRF blocked"):
        async for _ in execute_connector_run(tool_name="ssrf_internal", arguments={}, snapshot=snapshot_internal):
            pass



@pytest.mark.asyncio
async def test_execute_db_connector_rejects_non_select():
    snapshot = {
        "runtime_policy": {
            "connector_kind": "db",
            "connector_config": {"db_url": "postgresql+asyncpg://user:pass@example.com/db"},
        }
    }
    with pytest.raises(RuntimeError, match="read-only"):
        async for _ in execute_connector_run(tool_name="analytics_query", arguments={"sql": "DELETE FROM foo"}, snapshot=snapshot):
            pass


@pytest.mark.asyncio
async def test_rest_connector_injects_bearer_from_secret_store(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.secret_store.settings.SKILL_AGENT_SECRET_STORE", str(tmp_path))
    (tmp_path / "tok-1").write_text("super-token", encoding="utf-8")

    response = MagicMock()
    response.url = "https://example.com/api"
    response.raise_for_status = MagicMock()
    response.json.return_value = {"ok": True}
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    client.request = AsyncMock(return_value=response)

    snapshot = {
        "runtime_policy": {
            "connector_kind": "rest",
            "connector_secret_ref_id": "tok-1",
            "connector_config": {"url": "https://example.com/api", "method": "GET"},
        }
    }
    with patch("app.services.connector_router.httpx.AsyncClient", return_value=client):
        events = [
            event
            async for event in execute_connector_run(tool_name="secure_get", arguments={}, snapshot=snapshot)
        ]

    assert events[-1]["event_type"] == "run.completed"
    headers = client.request.await_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer super-token"


@pytest.mark.asyncio
async def test_rest_connector_rejects_missing_config_url():
    snapshot = {
        "runtime_policy": {
            "connector_kind": "rest",
            "connector_config": {},
        }
    }
    with pytest.raises(RuntimeError, match="connector REST url missing"):
        async for _ in execute_connector_run(
            tool_name="unconfigured_rest",
            arguments={"url": "https://malicious.attacker.com"},
            snapshot=snapshot,
        ):
            pass
