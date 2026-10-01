from types import SimpleNamespace

import httpx
import pytest

from app.services.agent_tool_gateway import (
    arguments_digest,
    classify_connector_exception,
    decide_tool_call,
    hermes_mcp_feature,
    public_tool_view,
)


def test_catalog_view_hides_route_and_secret():
    view = public_tool_view(
        {
            "tool_name": "crm.lookup",
            "description": "lookup",
            "input_schema": {"type": "object"},
            "connector_secret_ref_id": "sec-1",
            "connector_config": {"url": "https://example.internal"},
        }
    )
    assert view == {
        "name": "crm.lookup",
        "description": "lookup",
        "inputSchema": {"type": "object"},
    }
    assert "url" not in view
    assert "secret" not in str(view)


def test_unknown_tool_and_pending_do_not_execute():
    assert decide_tool_call(
        generation_matches=True,
        tool_listed=False,
        run_waiting=False,
        pending_other=False,
        stored_result=None,
    ) == "deny_unknown"
    assert decide_tool_call(
        generation_matches=True,
        tool_listed=True,
        run_waiting=True,
        pending_other=False,
        stored_result=None,
    ) == "tool_error"
    assert decide_tool_call(
        generation_matches=True,
        tool_listed=True,
        run_waiting=False,
        pending_other=False,
        stored_result=None,
    ) == "wait_approval"


def test_stale_generation_fails_and_same_digest_replays():
    assert decide_tool_call(
        generation_matches=False,
        tool_listed=True,
        run_waiting=False,
        pending_other=False,
        stored_result=None,
    ) == "fail_run"
    stored = {"result": {"isError": False}}
    assert decide_tool_call(
        generation_matches=True,
        tool_listed=True,
        run_waiting=False,
        pending_other=False,
        stored_result=stored,
    ) == "replay"
    assert arguments_digest({"b": 1, "a": 2}) == arguments_digest({"a": 2, "b": 1})


def test_ambiguous_network_is_not_retried_and_mcp_feature_is_explicit():
    assert classify_connector_exception(httpx.TimeoutException("slow")) == "outcome_unknown"
    assert classify_connector_exception(httpx.HTTPStatusError(
        "nope",
        request=httpx.Request("POST", "https://example.com"),
        response=httpx.Response(500),
    )) == "tool_error"
    assert hermes_mcp_feature({"features": {"run_submission": True}}) is None
    assert hermes_mcp_feature({"features": {"mcp_tool_surface": True}}) == "mcp_tool_surface"


@pytest.mark.asyncio
async def test_tool_call_does_not_execute_connector_before_approval(monkeypatch):
    from app.api import agent_tools_mcp

    run = SimpleNamespace(
        run_id="run-1",
        org_id="org",
        status="RUNNING",
        generation=1,
        snapshot={"connector_binding_refs": ["11111111-1111-4111-8111-111111111111"]},
    )

    class Catalog:
        async def list_tools(self, **kwargs):
            return [{"tool_name": "crm.lookup", "description": "lookup", "input_schema": {"type": "object"}}]

    async def fail_execute(**kwargs):
        raise AssertionError("connector must not run before approval")
        yield {}

    monkeypatch.setattr(agent_tools_mcp, "RemoteAgentCatalogClient", lambda: Catalog())
    monkeypatch.setattr(agent_tools_mcp.run_service, "list_events", _empty_events)
    monkeypatch.setattr(agent_tools_mcp.run_service, "set_status", _ok)
    monkeypatch.setattr(agent_tools_mcp.run_service, "append_event", _ok)
    monkeypatch.setattr(agent_tools_mcp, "execute_connector_run", fail_execute)
    result = await agent_tools_mcp._call_tool(
        None,
        run,
        {"name": "crm.lookup", "arguments": {"q": "acme"}, "tool_call_id": "call-1"},
        1,
    )
    assert result["isError"] is True
    assert result["approval_id"]


async def _empty_events(*args, **kwargs):
    return []


async def _ok(*args, **kwargs):
    return True
