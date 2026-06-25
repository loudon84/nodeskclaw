from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.models.hermes_skill.hermes_agent_instance import HermesAgentInstance
from app.models.mcp_client_token import McpClientToken
from app.models.user import User
from app.services.hermes_agents.mcp_gateway_authorization_service import McpGatewayAuthorizationService


def _agent_record(**kwargs) -> HermesAgentInstance:
    record = HermesAgentInstance(
        id="agent-1",
        org_id="org-1",
        profile_name="common-writer",
        container_name="hermes-common-writer",
        docker_status="running",
        docker_health="healthy",
        gateway_status="ready",
        gateway_runtime_status="ready",
        mcp_status="ready",
        env_file=None,
        instance_dir=None,
    )
    for key, value in kwargs.items():
        setattr(record, key, value)
    return record


def test_compute_ui_status_none():
    service = McpGatewayAuthorizationService(AsyncMock())
    assert service.compute_ui_status(_agent_record(), None) == "none"


def test_compute_ui_status_env_synced():
    service = McpGatewayAuthorizationService(AsyncMock())
    record = _agent_record(mcp_gateway_enabled=True, mcp_gateway_env_synced=True)
    token = McpClientToken(
        id="t1",
        org_id="org-1",
        name="n",
        token_prefix="p",
        token_hash="h",
        created_by="u1",
    )
    assert service.compute_ui_status(record, token) == "env_synced"


@pytest.mark.asyncio
async def test_authorize_writes_env_and_updates_record(tmp_path):
    env_path = tmp_path / ".env"
    record = _agent_record(env_file=str(env_path), instance_dir=str(tmp_path))
    user = User(id="user-1", email="u@example.com", username="u")

    db = AsyncMock()
    service = McpGatewayAuthorizationService(db)
    service.get_agent = AsyncMock(return_value=record)
    service._resolve_allowed_skills = AsyncMock(return_value=["tool.a"])
    service._audit = AsyncMock()

    plain = "ndsk_mcp_common_writer_abcd.secret"
    token_record = McpClientToken(
        id="tok-1",
        org_id="org-1",
        name="n",
        token_prefix="ndsk_mcp_common_writer_abcd",
        token_hash="hash",
        created_by="user-1",
        expires_at=datetime.now(timezone.utc),
    )
    service.token_service.create_token = AsyncMock(return_value=(plain, token_record))
    service.token_service.get_active_token = AsyncMock(return_value=None)

    with patch(
        "app.services.hermes_agents.mcp_gateway_authorization_service.build_mcp_gateway_url",
        return_value="http://host.docker.internal:4510/api/v1/hermes/mcp",
    ):
        result = await service.authorize(
            "org-1",
            "agent-1",
            user,
            write_env=True,
            force_rotate=True,
        )

    assert result["ok"] is True
    assert result["token_prefix"] == token_record.token_prefix
    assert record.mcp_gateway_enabled is True
    assert record.mcp_gateway_env_synced is True
    content = env_path.read_text(encoding="utf-8")
    assert "NODESKCLAW_MCP_URL=" in content
    assert "NODESKCLAW_MCP_TOKEN=" in content


@pytest.mark.asyncio
async def test_authorize_env_failure_revokes_token():
    record = _agent_record(env_file="C:/fake/instance/.env")
    user = User(id="user-1", email="u@example.com", username="u")

    db = AsyncMock()
    service = McpGatewayAuthorizationService(db)
    service.get_agent = AsyncMock(return_value=record)
    service._resolve_allowed_skills = AsyncMock(return_value=None)
    service._audit = AsyncMock()

    token_record = McpClientToken(
        id="tok-1",
        org_id="org-1",
        name="n",
        token_prefix="p",
        token_hash="h",
        created_by="user-1",
        expires_at=datetime.now(timezone.utc),
    )
    service.token_service.create_token = AsyncMock(
        return_value=("ndsk_mcp_x_y.secret", token_record),
    )
    service.token_service.get_active_token = AsyncMock(return_value=None)
    service.token_service.revoke_token = AsyncMock(return_value=token_record)

    from app.core.exceptions import BadRequestError

    with patch(
        "app.services.hermes_agents.mcp_gateway_authorization_service.build_mcp_gateway_url",
        return_value="http://example.com/api/v1/hermes/mcp",
    ), patch(
        "app.services.hermes_agents.mcp_gateway_authorization_service.write_mcp_env_values",
        side_effect=BadRequestError("写入失败", "errors.mcp_gateway.env_write_failed"),
    ):
        with pytest.raises(BadRequestError):
            await service.authorize("org-1", "agent-1", user, write_env=True)

    service.token_service.revoke_token.assert_awaited_once_with("tok-1")
    assert record.mcp_gateway_env_synced is False
    assert record.mcp_gateway_last_error
