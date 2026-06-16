import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.hermes_skill.hermes_client_service import HermesClientService, DesktopContext


def _request(headers: dict | None = None):
    req = MagicMock()
    req.headers = headers or {}
    return req


@pytest.mark.asyncio
async def test_parse_desktop_headers():
    db = AsyncMock()
    svc = HermesClientService(db)
    ctx = svc.parse_desktop_headers(_request({
        "X-NoDeskClaw-Desktop-Device-Id": "desktop_xxx",
        "X-NoDeskClaw-Hermes-Profile": "writer",
        "X-NoDeskClaw-Client": "copilot-desktop",
        "X-NoDeskClaw-MCP-Proxy-Version": "v6.7",
    }))
    assert ctx.device_id == "desktop_xxx"
    assert ctx.profile_name == "writer"
    assert ctx.client == "copilot-desktop"
    assert ctx.proxy_version == "v6.7"
    assert ctx.is_present is True


@pytest.mark.asyncio
async def test_build_bootstrap_schema():
    db = AsyncMock()
    svc = HermesClientService(db)
    user = MagicMock(id="user-1", username="alice", display_name=None)
    org = MagicMock(id="org-1", name="Test Org")
    ctx = DesktopContext(device_id="d1", profile_name="writer", client="copilot-desktop")
    with patch.object(svc.audit, "log", AsyncMock()):
        data = await svc.build_bootstrap(user, org, ctx)
    assert data["user"]["id"] == "user-1"
    assert data["org"]["id"] == "org-1"
    assert data["mcp"]["server_url"] == "/api/v1/hermes/mcp"
    assert data["mcp"]["health_url"] == "/api/v1/hermes/mcp/health"
    assert data["features"]["agent_alias_routing"] is True
    assert data["events"]["sse_token_supported"] is True
