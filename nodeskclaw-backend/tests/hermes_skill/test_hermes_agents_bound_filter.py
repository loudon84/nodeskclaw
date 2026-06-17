"""Tests for Hermes agents list bound-only filtering (v4.5.2)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.hermes_skill.agents_bind_router import list_hermes_agents
from app.models.hermes_skill.hermes_agent_instance import HermesAgentInstance
from app.models.instance import Instance
from app.services.hermes_external.hermes_docker_binding_service import HermesDockerBindingService


def _user_org():
    user = MagicMock()
    user.id = "user-1"
    org = MagicMock()
    org.id = "org-1"
    return user, org


def _record(profile: str, *, instance_id: str | None = None) -> HermesAgentInstance:
    record = MagicMock(spec=HermesAgentInstance)
    record.id = f"rec-{profile}"
    record.profile_name = profile
    record.container_name = f"hermes-{profile}"
    record.container_id = "cid"
    record.image = "hermes:latest"
    record.docker_status = "running"
    record.docker_health = "healthy"
    record.host_ip = "127.0.0.1"
    record.webui_port = 8900
    record.webui_url = "http://127.0.0.1:8900"
    record.gateway_port = 18900
    record.gateway_url = "http://127.0.0.1:18900"
    record.gateway_status = "online"
    record.gateway_runtime_status = "ready"
    record.mcp_status = "callable"
    record.instance_dir = f"/data/instances/{profile}"
    record.data_dir = f"/data/instances/{profile}/data/hermes"
    record.env_file = f"/data/instances/{profile}/.env"
    record.compose_file = None
    record.compose_project = f"hermes-{profile}"
    record.managed_mode = "external_docker"
    record.instance_id = instance_id
    record.last_probe_at = None
    record.last_seen_at = None
    record.last_error = None
    return record


def _instance(name: str, instance_id: str) -> Instance:
    inst = MagicMock(spec=Instance)
    inst.id = instance_id
    inst.name = name
    inst.status = MagicMock()
    inst.status.value = "running"
    inst.advanced_config = json.dumps({"attach_mode": "external"})
    return inst


@pytest.mark.asyncio
async def test_list_hermes_agents_default_excludes_unbound():
    user, org = _user_org()
    db = AsyncMock()
    bound_record = _record("common-writer", instance_id="inst-1")
    bound_instance = _instance("生文专家", "inst-1")

    with patch("app.api.hermes_skill.agents_bind_router.PermissionChecker.require_permission", AsyncMock()):
        with patch("app.api.hermes_skill.agents_bind_router.PermissionChecker.has_permission", AsyncMock(return_value=False)):
            with patch.object(
                HermesDockerBindingService,
                "list_instances_for_api",
                AsyncMock(return_value=[(bound_record, bound_instance)]),
            ) as list_mock:
                response = await list_hermes_agents(
                    include_unavailable=True,
                    include_unbound=False,
                    managed_mode=None,
                    refresh=False,
                    user_org=(user, org),
                    db=db,
                )

    list_mock.assert_awaited_once_with(
        org.id,
        include_unbound=False,
        include_unavailable=True,
        managed_mode=None,
    )
    assert response["code"] == 0
    assert len(response["data"]["items"]) == 1
    assert response["data"]["items"][0]["employee_name"] == "生文专家"
    assert response["data"]["items"][0]["is_bound"] is True


@pytest.mark.asyncio
async def test_list_hermes_agents_include_unbound_requires_manage_permission():
    user, org = _user_org()
    db = AsyncMock()
    unbound = _record("heyejuan", instance_id=None)

    with patch("app.api.hermes_skill.agents_bind_router.PermissionChecker.require_permission", AsyncMock()):
        with patch("app.api.hermes_skill.agents_bind_router.PermissionChecker.has_permission", AsyncMock(return_value=False)):
            with patch.object(
                HermesDockerBindingService,
                "list_instances_for_api",
                AsyncMock(return_value=[(unbound, None)]),
            ) as list_mock:
                await list_hermes_agents(
                    include_unavailable=True,
                    include_unbound=True,
                    managed_mode=None,
                    refresh=False,
                    user_org=(user, org),
                    db=db,
                )

    list_mock.assert_awaited_once_with(
        org.id,
        include_unbound=False,
        include_unavailable=True,
        managed_mode=None,
    )


@pytest.mark.asyncio
async def test_list_hermes_agents_refresh_only_bound_by_default():
    user, org = _user_org()
    db = AsyncMock()

    with patch("app.api.hermes_skill.agents_bind_router.PermissionChecker.require_permission", AsyncMock()):
        with patch("app.api.hermes_skill.agents_bind_router.PermissionChecker.has_permission", AsyncMock(return_value=False)):
            with patch.object(HermesDockerBindingService, "probe_all", AsyncMock(return_value=[])) as probe_mock:
                with patch.object(HermesDockerBindingService, "list_instances_for_api", AsyncMock(return_value=[])):
                    await list_hermes_agents(
                        include_unavailable=True,
                        include_unbound=False,
                        managed_mode=None,
                        refresh=True,
                        user_org=(user, org),
                        db=db,
                    )

    probe_mock.assert_awaited_once_with(org.id, include_unbound=False)
    db.commit.assert_awaited_once()
