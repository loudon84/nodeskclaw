"""Tests for HermesBoundAgentScopeService (v4.5.3)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import BadRequestError
from app.models.hermes_skill.hermes_agent_instance import HermesAgentInstance
from app.models.instance import Instance
from app.services.hermes_external.hermes_bound_agent_scope_service import HermesBoundAgentScopeService


def _record(**kwargs) -> HermesAgentInstance:
    record = MagicMock(spec=HermesAgentInstance)
    record.instance_id = kwargs.get("instance_id", "inst-1")
    record.profile_name = kwargs.get("profile_name", "common-writer")
    record.container_name = kwargs.get("container_name", "hermes-common-writer")
    record.gateway_url = kwargs.get("gateway_url", "http://127.0.0.1:18900")
    record.gateway_status = kwargs.get("gateway_status", "online")
    record.mcp_status = kwargs.get("mcp_status", "callable")
    record.gateway_runtime_status = kwargs.get("gateway_runtime_status", "ready")
    record.env_file = kwargs.get("env_file", "/data/.env")
    return record


def _instance(instance_id: str = "inst-1") -> Instance:
    inst = MagicMock(spec=Instance)
    inst.id = instance_id
    inst.name = "生文专家"
    inst.advanced_config = '{"attach_mode": "external"}'
    return inst


def test_is_bound_requires_external_docker():
    record = _record()
    instance = _instance()
    with patch(
        "app.services.hermes_external.hermes_bound_agent_scope_service.get_instance_binding_type",
        return_value="external_docker",
    ):
        assert HermesBoundAgentScopeService.is_bound(record, instance) is True


def test_is_bound_rejects_platform_managed():
    record = _record()
    instance = _instance()
    with patch(
        "app.services.hermes_external.hermes_bound_agent_scope_service.get_instance_binding_type",
        return_value="platform_managed",
    ):
        assert HermesBoundAgentScopeService.is_bound(record, instance) is False


def test_is_dispatchable_requires_ready_runtime():
    record = _record(gateway_runtime_status="degraded")
    instance = _instance()
    with patch.object(HermesBoundAgentScopeService, "is_bound", return_value=True), \
         patch.object(HermesBoundAgentScopeService, "has_api_server_key", return_value=True):
        assert HermesBoundAgentScopeService.is_dispatchable(record, instance) is False


def test_is_dispatchable_true_when_all_checks_pass():
    record = _record()
    instance = _instance()
    with patch.object(HermesBoundAgentScopeService, "is_bound", return_value=True), \
         patch.object(HermesBoundAgentScopeService, "has_api_server_key", return_value=True):
        assert HermesBoundAgentScopeService.is_dispatchable(record, instance) is True


@pytest.mark.asyncio
async def test_assert_bound_instance_raises_for_unknown_id():
    db = AsyncMock()
    svc = HermesBoundAgentScopeService(db)
    with patch.object(svc, "list_bound_pairs", AsyncMock(return_value=[])):
        with pytest.raises(BadRequestError) as exc:
            await svc.assert_bound_instance("org-1", "missing-id")
    assert exc.value.message_key == "errors.hermes.agent_not_bound"


@pytest.mark.asyncio
async def test_assert_dispatchable_instance_raises_when_not_ready():
    db = AsyncMock()
    svc = HermesBoundAgentScopeService(db)
    record = _record(gateway_runtime_status="degraded")
    instance = _instance()
    with patch.object(svc, "assert_bound_instance", AsyncMock(return_value=(record, instance))), \
         patch.object(HermesBoundAgentScopeService, "is_dispatchable", return_value=False), \
         patch.object(HermesBoundAgentScopeService, "_dispatchable_failure_reason", return_value="runtime_not_ready"):
        with pytest.raises(BadRequestError) as exc:
            await svc.assert_dispatchable_instance("org-1", "inst-1")
    assert exc.value.message_key == "errors.hermes.agent_runtime_not_ready"


@pytest.mark.asyncio
async def test_to_agent_summary_includes_task_dispatchable():
    db = AsyncMock()
    svc = HermesBoundAgentScopeService(db)
    record = _record()
    instance = _instance()
    with patch(
        "app.services.hermes_external.hermes_bound_agent_scope_service.HermesDockerBindingService.to_api_dict",
        return_value={"profile_name": "common-writer", "is_bound": True},
    ), patch.object(HermesBoundAgentScopeService, "is_dispatchable", return_value=True):
        summary = svc.to_agent_summary(record, instance)
    assert summary["task_dispatchable"] is True
