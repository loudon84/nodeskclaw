import pytest
from unittest.mock import AsyncMock, patch

from app.services.mcp_skill_gateway.constants import build_mcp_descriptor


def test_system_info_mcp_descriptor_fields():
    descriptor = build_mcp_descriptor()
    assert descriptor["enabled"] is True
    assert descriptor["transport"] == "streamable_http"
    assert descriptor["endpoint"] == "/api/v1/hermes/mcp"
    assert descriptor["requiresAuth"] is True
    assert descriptor["protocolVersion"] == "2025-06-18"
    assert "approvalCenterPath" in descriptor


@pytest.mark.asyncio
async def test_copilot_desktop_flow_mock_chain():
    from app.services.hermes_skill.hermes_client_service import HermesClientService, DesktopContext

    db = AsyncMock()
    svc = HermesClientService(db)
    user = type("User", (), {"id": "u1", "username": "alice", "display_name": None})()
    org = type("Org", (), {"id": "o1", "name": "Org"})()
    ctx = DesktopContext(device_id="d1", profile_name="writer", client="copilot-desktop")

    with patch.object(svc.audit, "log", AsyncMock()):
        bootstrap = await svc.build_bootstrap(user, org, ctx)
    assert bootstrap["mcp"]["server_url"]
    assert bootstrap["features"]["readiness_check"] is True

    with patch.object(svc, "run_readiness_check", AsyncMock(return_value={"ready": True, "checks": {}})):
        readiness = await svc.run_readiness_check("o1", "u1", agent_alias="common-writer", desktop_ctx=ctx)
    assert readiness["ready"] is True
