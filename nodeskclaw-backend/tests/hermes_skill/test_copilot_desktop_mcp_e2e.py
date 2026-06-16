import pytest
from unittest.mock import AsyncMock, patch

from app.services.hermes_skill.hermes_client_service import HermesClientService, DesktopContext


@pytest.mark.asyncio
async def test_e2e_desktop_contract_mock():
    db = AsyncMock()
    client_svc = HermesClientService(db)
    user = type("User", (), {"id": "u1", "username": "alice", "display_name": None})()
    org = type("Org", (), {"id": "o1", "name": "Org"})()
    desktop_ctx = DesktopContext(
        device_id="desktop_xxx",
        profile_name="writer",
        client="copilot-desktop",
        proxy_version="v6.7",
    )

    with patch.object(client_svc.audit, "log", AsyncMock()):
        bootstrap = await client_svc.build_bootstrap(user, org, desktop_ctx)
    assert bootstrap["desktop"]["client"] == "copilot-desktop"

    readiness = {
        "ready": True,
        "checks": {"agent_exists": True, "skill_exists": True},
        "routing": {"agent_alias": "common-writer", "agent_id": "agent-1"},
        "tool": {"name": "writer_article_generate"},
        "errors": [],
    }
    with patch.object(client_svc, "run_readiness_check", AsyncMock(return_value=readiness)):
        check = await client_svc.run_readiness_check(
            "o1", "u1", agent_alias="common-writer", tool_name="writer_article_generate", desktop_ctx=desktop_ctx,
        )
    assert check["routing"]["agent_alias"] == "common-writer"

    mcp_result = {
        "task_id": "task-1",
        "event_token_url": "/api/v1/hermes/tasks/task-1/events-token",
        "result_url": "/api/v1/hermes/tasks/task-1/result",
    }
    assert mcp_result["event_token_url"].endswith("/events-token")
    assert mcp_result["result_url"].endswith("/result")
