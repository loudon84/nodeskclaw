from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import BadRequestError
from app.models.hermes_skill.hermes_agent_instance import HermesAgentInstance
from app.models.user import User
from app.services.hermes_agents.mcp_skill_router_service import (
    McpSkillRouterService,
    resolve_router_skill_path,
)


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
        data_dir=None,
    )
    for key, value in kwargs.items():
        setattr(record, key, value)
    return record


def test_resolve_router_skill_path_from_data_dir():
    record = _agent_record(data_dir="/data/instances/common-writer/data/hermes")
    path = resolve_router_skill_path(record, "default")
    assert path == Path(
        "/data/instances/common-writer/data/hermes/skills/nodeskclaw-skill-router/SKILL.md",
    )


def test_compute_ui_status_mcp_unauthorized():
    service = McpSkillRouterService(AsyncMock())
    record = _agent_record(mcp_gateway_env_synced=False)
    assert service.compute_ui_status(record) == "mcp_unauthorized"


def test_compute_ui_status_synced():
    service = McpSkillRouterService(AsyncMock())
    record = _agent_record(mcp_gateway_env_synced=True, mcp_router_enabled=True)
    assert service.compute_ui_status(record) == "synced"


@pytest.mark.asyncio
async def test_sync_mcp_not_authorized(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("NODESKCLAW_MCP_ENABLED=false\n", encoding="utf-8")
    record = _agent_record(env_file=str(env_path), instance_dir=str(tmp_path))
    user = User(id="user-1", email="u@example.com", username="u")

    db = AsyncMock()
    service = McpSkillRouterService(db)
    service.get_agent = AsyncMock(return_value=record)
    service._audit = AsyncMock()
    service.binding.get_linked_instance = AsyncMock(return_value=None)

    with pytest.raises(BadRequestError) as exc_info:
        await service.sync("org-1", "agent-1", user)
    assert exc_info.value.message_key == "errors.mcp_router.mcp_not_authorized"


@pytest.mark.asyncio
async def test_sync_writes_skill_md(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join([
            "NODESKCLAW_MCP_ENABLED=true",
            "NODESKCLAW_MCP_TOKEN=ndsk_mcp_test.secret",
            "NODESKCLAW_MCP_URL=http://127.0.0.1:4510/api/v1/hermes/mcp",
            "NODESKCLAW_MCP_NAME=common-skills",
        ]) + "\n",
        encoding="utf-8",
    )
    record = _agent_record(
        env_file=str(env_path),
        instance_dir=str(tmp_path),
        data_dir=str(tmp_path / "data" / "hermes"),
        mcp_gateway_env_synced=True,
    )
    user = User(id="user-1", email="u@example.com", username="u")

    db = AsyncMock()
    service = McpSkillRouterService(db)
    service.get_agent = AsyncMock(return_value=record)
    service._audit = AsyncMock()
    service.binding.get_linked_instance = AsyncMock(return_value=None)

    tools = [
        {"name": "hermes_common_researcher__customer-profiling", "description": "画像"},
        {"name": "hermes.instances.list", "description": "registry"},
    ]

    with patch(
        "app.services.hermes_agents.mcp_skill_router_service.fetch_mcp_tools_list",
        AsyncMock(return_value=tools),
    ):
        result = await service.sync("org-1", "agent-1", user)

    skill_path = Path(result["router_skill_path"])
    assert skill_path.is_file()
    content = skill_path.read_text(encoding="utf-8")
    assert "ndsk_mcp_" not in content
    assert "Bearer" not in content
    assert result["tool_count"] == 1
    assert record.mcp_router_enabled is True


@pytest.mark.asyncio
async def test_sync_tools_empty():
    env_path_content = (
        "NODESKCLAW_MCP_ENABLED=true\n"
        "NODESKCLAW_MCP_TOKEN=ndsk_mcp_test.secret\n"
        "NODESKCLAW_MCP_URL=http://127.0.0.1:4510/api/v1/hermes/mcp\n"
    )
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        env_path = Path(tmp) / ".env"
        env_path.write_text(env_path_content, encoding="utf-8")
        record = _agent_record(
            env_file=str(env_path),
            instance_dir=tmp,
            data_dir=str(Path(tmp) / "data" / "hermes"),
            mcp_gateway_env_synced=True,
        )
        user = User(id="user-1", email="u@example.com", username="u")

        db = AsyncMock()
        service = McpSkillRouterService(db)
        service.get_agent = AsyncMock(return_value=record)
        service._audit = AsyncMock()
        service.binding.get_linked_instance = AsyncMock(return_value=None)

        with patch(
            "app.services.hermes_agents.mcp_skill_router_service.fetch_mcp_tools_list",
            AsyncMock(return_value=[{"name": "hermes.instances.list", "description": "x"}]),
        ):
            with pytest.raises(BadRequestError) as exc_info:
                await service.sync("org-1", "agent-1", user)
        assert exc_info.value.message_key == "errors.mcp_router.tools_empty"
