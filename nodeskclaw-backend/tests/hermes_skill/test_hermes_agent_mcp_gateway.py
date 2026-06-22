"""Tests for per-agent Hermes MCP Gateway (PRD v5.1.1)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import AppException, ConflictError, ForbiddenError
from app.schemas.hermes_instance_skill import (
    HermesInstanceSkillItem,
    HermesInstanceSkillListResponse,
)
from app.services.hermes_external import hermes_agent_mcp_gateway_service as gateway_service
from app.services.hermes_external import hermes_instance_skill_service as instance_skill_service
from app.services.hermes_external.hermes_api_server_client import HermesApiResponse


def _binding_record(tmp_path: Path, profile: str = "common-writer"):
    record = MagicMock()
    record.id = "rec-1"
    record.instance_id = "inst-1"
    record.profile_name = profile
    record.gateway_url = "http://127.0.0.1:18900"
    env_file = tmp_path / f"{profile}.env"
    env_file.write_text(
        "API_SERVER_ENABLED=true\nAPI_SERVER_KEY=test-key\nAPI_SERVER_MODEL_NAME=common-writer\n",
        encoding="utf-8",
    )
    record.env_file = str(env_file)
    return record


def _skill_list(profile: str = "common-writer") -> HermesInstanceSkillListResponse:
    now = datetime.now(timezone.utc)
    return HermesInstanceSkillListResponse(
        agent_profile=profile,
        gateway_url="http://127.0.0.1:18900",
        source_mode="api_server_default",
        total=2,
        skills=[
            HermesInstanceSkillItem(name="arxiv", category="research", description="arxiv papers"),
            HermesInstanceSkillItem(name="web-search", category="web", description="web search"),
        ],
        warnings=[],
        last_refreshed_at=now,
    )


@pytest.mark.asyncio
async def test_list_instance_skills_from_api_server(tmp_path: Path):
    record = _binding_record(tmp_path)
    db = AsyncMock()

    async def fake_list_skills(self):
        return HermesApiResponse(status_code=200, ok=True, data={"skills": [{"name": "arxiv"}]})

    with patch(
        "app.services.hermes_external.hermes_instance_skill_service.HermesDockerBindingService"
    ) as binding_cls, patch.object(
        instance_skill_service.HermesApiServerClient,
        "list_skills",
        fake_list_skills,
    ):
        binding_cls.return_value.get_by_profile = AsyncMock(return_value=record)
        instance_skill_service.invalidate_cache("common-writer")
        result = await instance_skill_service.list_instance_skills(db, "org-1", "common-writer")
    assert result.total == 1
    assert result.skills[0].name == "arxiv"


@pytest.mark.asyncio
async def test_list_instance_skills_requires_gateway_and_key(tmp_path: Path):
    record = _binding_record(tmp_path)
    record.gateway_url = None
    db = AsyncMock()

    with patch(
        "app.services.hermes_external.hermes_instance_skill_service.HermesDockerBindingService"
    ) as binding_cls:
        binding_cls.return_value.get_by_profile = AsyncMock(return_value=record)
        instance_skill_service.invalidate_cache("common-writer")
        with pytest.raises(ConflictError) as exc_info:
            await instance_skill_service.fetch_instance_skills_from_api_server(
                "common-writer",
                record.gateway_url,
                record.env_file,
            )
    assert exc_info.value.message_key == "errors.hermes.api_server_not_configured"


@pytest.mark.asyncio
async def test_api_server_offline_no_local_fallback(tmp_path: Path):
    record = _binding_record(tmp_path)
    db = AsyncMock()

    async def fake_list_skills(self):
        return HermesApiResponse(status_code=None, ok=False, data=None, error="offline")

    with patch(
        "app.services.hermes_external.hermes_instance_skill_service.HermesDockerBindingService"
    ) as binding_cls, patch.object(
        instance_skill_service.HermesApiServerClient,
        "list_skills",
        fake_list_skills,
    ), patch("asyncio.create_subprocess_exec", AsyncMock()) as docker_exec:
        binding_cls.return_value.get_by_profile = AsyncMock(return_value=record)
        instance_skill_service.invalidate_cache("common-writer")
        with pytest.raises(AppException) as exc_info:
            await instance_skill_service.list_instance_skills(db, "org-1", "common-writer")
    assert exc_info.value.message_key == "errors.hermes.api_server_offline"
    docker_exec.assert_not_called()


@pytest.mark.asyncio
async def test_mcp_tools_list_filters_by_can_list(tmp_path: Path):
    db = AsyncMock()
    skill_list = _skill_list()

    with patch(
        "app.services.hermes_external.hermes_agent_mcp_gateway_service.instance_skill_service.list_instance_skills",
        AsyncMock(return_value=skill_list),
    ), patch(
        "app.services.hermes_external.hermes_agent_mcp_gateway_service.HermesDockerBindingService"
    ) as binding_cls, patch(
        "app.services.hermes_external.hermes_agent_mcp_gateway_service.HermesSkillAuthorizationService"
    ) as authz_cls:
        binding_cls.return_value.get_by_profile = AsyncMock(return_value=_binding_record(tmp_path))
        authz = authz_cls.return_value
        authz.can_list = AsyncMock(side_effect=lambda org, user, db_id, skill_id, **kw: skill_id == "arxiv")
        authz.can_invoke = AsyncMock(return_value=True)

        result = await gateway_service.list_tools_jsonrpc(
            db, "org-1", "user-1", "common-writer", params={}
        )

    assert len(result["tools"]) == 1
    assert result["tools"][0]["name"] == "hermes_common_writer__arxiv"


@pytest.mark.asyncio
async def test_mcp_tools_list_rejects_profile_param():
    db = AsyncMock()
    with pytest.raises(Exception) as exc_info:
        await gateway_service.list_tools_jsonrpc(
            db, "org-1", "user-1", "common-writer", params={"profile": "researcher"}
        )
    assert getattr(exc_info.value, "message_key", None) == "errors.hermes.profile_not_supported"


@pytest.mark.asyncio
async def test_mcp_tools_call_invokes_chat_completions(tmp_path: Path):
    db = AsyncMock()
    skill_list = _skill_list()
    record = _binding_record(tmp_path)
    tool_name = instance_skill_service.build_tool_name("common-writer", "arxiv")

    async def fake_chat(self, payload):
        assert payload["model"] == "common-writer"
        return HermesApiResponse(
            status_code=200,
            ok=True,
            data={"choices": [{"message": {"content": "done"}}]},
        )

    with patch(
        "app.services.hermes_external.hermes_agent_mcp_gateway_service.instance_skill_service.list_instance_skills",
        AsyncMock(return_value=skill_list),
    ), patch(
        "app.services.hermes_external.hermes_agent_mcp_gateway_service.HermesDockerBindingService"
    ) as binding_cls, patch(
        "app.services.hermes_external.hermes_agent_mcp_gateway_service.HermesSkillAuthorizationService"
    ) as authz_cls, patch.object(
        instance_skill_service.HermesApiServerClient,
        "chat_completions",
        fake_chat,
    ), patch(
        "app.services.hermes_external.hermes_agent_mcp_gateway_service.log_mcp_call",
        AsyncMock(),
    ) as audit:
        binding_cls.return_value.get_by_profile = AsyncMock(return_value=record)
        authz_cls.return_value.can_invoke = AsyncMock(return_value=True)

        result = await gateway_service.call_tool_jsonrpc(
            db,
            "org-1",
            "user-1",
            "common-writer",
            params={"name": tool_name, "arguments": {"prompt": "hello"}},
        )

    assert result["content"][0]["text"] == "done"
    audit.assert_awaited()


@pytest.mark.asyncio
async def test_mcp_tools_call_permission_denied(tmp_path: Path):
    db = AsyncMock()
    skill_list = _skill_list()
    record = _binding_record(tmp_path)
    tool_name = instance_skill_service.build_tool_name("common-writer", "arxiv")

    with patch(
        "app.services.hermes_external.hermes_agent_mcp_gateway_service.instance_skill_service.list_instance_skills",
        AsyncMock(return_value=skill_list),
    ), patch(
        "app.services.hermes_external.hermes_agent_mcp_gateway_service.HermesDockerBindingService"
    ) as binding_cls, patch(
        "app.services.hermes_external.hermes_agent_mcp_gateway_service.HermesSkillAuthorizationService"
    ) as authz_cls:
        binding_cls.return_value.get_by_profile = AsyncMock(return_value=record)
        authz_cls.return_value.can_invoke = AsyncMock(return_value=False)

        with pytest.raises(ForbiddenError) as exc_info:
            await gateway_service.call_tool_jsonrpc(
                db,
                "org-1",
                "user-1",
                "common-writer",
                params={"name": tool_name, "arguments": {"prompt": "hello"}},
            )
    assert exc_info.value.message_key == "errors.hermes.skill_permission_denied"


@pytest.mark.asyncio
async def test_dispatch_tools_list_jsonrpc_rejects_profile():
    db = AsyncMock()
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {"profile": "researcher"},
    }
    result = await gateway_service.dispatch_agent_mcp(db, "org-1", "user-1", "common-writer", body)
    assert "error" in result


@pytest.mark.asyncio
async def test_instance_skills_does_not_use_docker_exec(tmp_path: Path):
    record = _binding_record(tmp_path)
    db = AsyncMock()

    async def fake_list_skills(self):
        return HermesApiResponse(status_code=200, ok=True, data={"skills": [{"name": "arxiv"}]})

    with patch(
        "app.services.hermes_external.hermes_instance_skill_service.HermesDockerBindingService"
    ) as binding_cls, patch.object(
        instance_skill_service.HermesApiServerClient,
        "list_skills",
        fake_list_skills,
    ), patch("asyncio.create_subprocess_exec", AsyncMock()) as docker_exec:
        binding_cls.return_value.get_by_profile = AsyncMock(return_value=record)
        instance_skill_service.invalidate_cache("common-writer")
        await instance_skill_service.list_instance_skills(db, "org-1", "common-writer")
    docker_exec.assert_not_called()
