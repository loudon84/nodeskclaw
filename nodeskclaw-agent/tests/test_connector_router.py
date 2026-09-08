from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.connector_router import SSRFSafeTransport, execute_connector_run


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
        events = [event async for event in execute_connector_run(tool_name="crm_lookup", arguments={"body": {"q": "acme"}}, route_snapshot=snapshot["runtime_policy"])]

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
                route_snapshot=snapshot["runtime_policy"],
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
        async for _ in execute_connector_run(tool_name="ssrf_attempt", arguments={}, route_snapshot=snapshot["runtime_policy"]):
            pass

    # Test .internal domain blocking
    snapshot_internal = {
        "runtime_policy": {
            "connector_kind": "rest",
            "connector_config": {"url": "http://metadata.google.internal/computeMetadata/v1/"},
        }
    }
    with pytest.raises(RuntimeError, match="SSRF blocked"):
        async for _ in execute_connector_run(tool_name="ssrf_internal", arguments={}, route_snapshot=snapshot_internal["runtime_policy"]):
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
        async for _ in execute_connector_run(tool_name="analytics_query", arguments={"sql": "DELETE FROM foo"}, route_snapshot=snapshot["runtime_policy"]):
            pass


@pytest.mark.asyncio
@pytest.mark.parametrize("sql", ["WITH changed AS (DELETE FROM foo RETURNING id) SELECT * FROM changed", "SELECT 1; DELETE FROM foo"])
async def test_execute_db_connector_rejects_write_cte_and_multi_statement(sql):
    route = {"connector_kind": "db", "connector_config": {"db_url": "postgresql+asyncpg://analytics"}}
    with pytest.raises(RuntimeError, match="read-only"):
        async for _ in execute_connector_run(tool_name="analytics_query", arguments={"sql": sql}, route_snapshot=route):
            pass


@pytest.mark.asyncio
async def test_execute_rest_connector_blocks_dns_private_target(monkeypatch):
    loop = MagicMock()
    loop.getaddrinfo = AsyncMock(return_value=[(None, None, None, None, ("10.0.0.8", 443))])
    monkeypatch.setattr("app.services.connector_router.asyncio.get_running_loop", lambda: loop)
    route = {"connector_kind": "rest", "connector_config": {"url": "https://private.example.com"}}

    with pytest.raises(RuntimeError, match="forbidden IP range"):
        async for _ in execute_connector_run(tool_name="private_rest", arguments={}, route_snapshot=route):
            pass


@pytest.mark.asyncio
async def test_edge_rest_connector_requires_frozen_allowlist(monkeypatch):
    loop = MagicMock()
    loop.getaddrinfo = AsyncMock(return_value=[(None, None, None, None, ("10.0.0.8", 443))])
    monkeypatch.setattr("app.services.connector_router.asyncio.get_running_loop", lambda: loop)
    response = MagicMock(url="https://edge.example.com/api")
    response.raise_for_status = MagicMock()
    response.json.return_value = {"ok": True}
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    client.request = AsyncMock(return_value=response)
    route = {
        "connector_kind": "rest",
        "placement": "edge",
        "network_policy": {"allowlist": ["edge.example.com:443"]},
        "connector_config": {"url": "https://edge.example.com/api"},
    }

    with patch("app.services.connector_router.httpx.AsyncClient", return_value=client):
        events = [event async for event in execute_connector_run(tool_name="edge_rest", arguments={}, route_snapshot=route)]

    assert events[-1]["event_type"] == "run.completed"


@pytest.mark.asyncio
async def test_edge_rest_connector_rejects_allowlisted_host_on_wrong_port(monkeypatch):
    loop = MagicMock()
    loop.getaddrinfo = AsyncMock(return_value=[(None, None, None, None, ("10.0.0.8", 8443))])
    monkeypatch.setattr("app.services.connector_router.asyncio.get_running_loop", lambda: loop)
    route = {
        "connector_kind": "rest",
        "placement": "edge",
        "network_policy": {"allowlist": ["edge.example.com:443"]},
        "connector_config": {"url": "https://edge.example.com:8443/api"},
    }

    with pytest.raises(RuntimeError, match="frozen allowlist"):
        async for _ in execute_connector_run(tool_name="edge_wrong_port", arguments={}, route_snapshot=route):
            pass


@pytest.mark.asyncio
async def test_connector_cancellation_stops_before_http_io():
    cancel_event = asyncio.Event()
    cancel_event.set()
    route = {"connector_kind": "rest", "connector_config": {"url": "https://example.com/api"}}
    with patch("app.services.connector_router.httpx.AsyncClient") as client_cls, pytest.raises(asyncio.CancelledError):
        async for _ in execute_connector_run(
            tool_name="cancelled_rest",
            arguments={},
            route_snapshot=route,
            cancel_event=cancel_event,
        ):
            pass
    client_cls.assert_not_called()


@pytest.mark.asyncio
async def test_connector_cancellation_racing_completed_response_never_yields_completed(monkeypatch):
    loop = MagicMock()
    loop.getaddrinfo = AsyncMock(return_value=[(None, None, None, None, ("93.184.216.34", 443))])
    monkeypatch.setattr("app.services.connector_router.asyncio.get_running_loop", lambda: loop)
    cancel_event = asyncio.Event()
    response = MagicMock(url="https://example.com/api")
    response.raise_for_status = MagicMock()
    response.json.return_value = {"ok": True}
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None

    async def complete_and_cancel(*_args, **_kwargs):
        cancel_event.set()
        return response

    client.request = complete_and_cancel
    with patch("app.services.connector_router.httpx.AsyncClient", return_value=client), pytest.raises(asyncio.CancelledError):
        async for _ in execute_connector_run(
            tool_name="cancel_race",
            arguments={},
            route_snapshot={"connector_kind": "rest", "connector_config": {"url": "https://example.com/api"}},
            cancel_event=cancel_event,
        ):
            pass


@pytest.mark.asyncio
async def test_db_connector_sets_timeout_with_set_config_before_user_sql(monkeypatch):
    class AsyncContext:
        def __init__(self, value):
            self.value = value

        async def __aenter__(self):
            return self.value

        async def __aexit__(self, *_args):
            return None

    result = MagicMock()
    result.mappings.return_value.fetchmany.return_value = [{"id": 1}]
    conn = MagicMock()
    conn.begin.return_value = AsyncContext(None)
    conn.execute = AsyncMock(side_effect=[MagicMock(), MagicMock(), result])
    engine = MagicMock()
    engine.connect.return_value = AsyncContext(conn)
    engine.dispose = AsyncMock()
    monkeypatch.setattr("app.services.connector_router.create_async_engine", lambda _url: engine)

    events = [
        event
        async for event in execute_connector_run(
            tool_name="analytics_query",
            arguments={"sql": "SELECT id FROM report"},
            route_snapshot={"connector_kind": "db", "connector_config": {"db_url": "postgresql+asyncpg://analytics", "statement_timeout_ms": 5000}},
        )
    ]

    assert events[-1]["event_type"] == "run.completed"
    assert str(conn.execute.await_args_list[0].args[0]) == "SET TRANSACTION READ ONLY"
    assert str(conn.execute.await_args_list[1].args[0]) == "SELECT set_config('statement_timeout', CAST(:timeout_ms AS text), true)"
    assert conn.execute.await_args_list[1].args[1] == {"timeout_ms": 5000}
    assert str(conn.execute.await_args_list[2].args[0]) == "SELECT id FROM report"


@pytest.mark.asyncio
async def test_ssrf_transport_pins_validated_address_for_connection(monkeypatch):
    seen: dict[str, object] = {}

    async def fake_validate(*_args, **_kwargs):
        return ["93.184.216.34"]

    async def fake_send(_self, request):
        seen["url"] = str(request.url)
        seen["host"] = request.headers["Host"]
        seen["sni"] = request.extensions["sni_hostname"]
        return httpx.Response(200, request=request)

    monkeypatch.setattr("app.services.connector_router._validate_ssrf", fake_validate)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", fake_send)
    request = httpx.Request("GET", "https://public.example.com/api")

    response = await SSRFSafeTransport().handle_async_request(request)

    assert response.status_code == 200
    assert seen == {
        "url": "https://93.184.216.34/api",
        "host": "public.example.com",
        "sni": "public.example.com",
    }
    assert str(request.url) == "https://public.example.com/api"


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
            async for event in execute_connector_run(tool_name="secure_get", arguments={}, route_snapshot=snapshot["runtime_policy"])
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
            route_snapshot=snapshot["runtime_policy"],
        ):
            pass
