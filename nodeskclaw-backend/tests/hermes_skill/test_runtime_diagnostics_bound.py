import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.hermes_skill.runtime_diagnostics_service import RuntimeDiagnosticsService


@pytest.mark.asyncio
async def test_agent_stats_only_returns_bound_agents():
    db = AsyncMock()
    svc = RuntimeDiagnosticsService(db)
    record = MagicMock()
    record.profile_name = "common-writer"
    record.container_name = "hermes-common-writer"
    record.instance_id = "inst-1"
    record.gateway_url = "http://127.0.0.1:18900"
    record.gateway_status = "online"
    record.gateway_runtime_status = "ready"
    record.mcp_status = "callable"
    record.last_error = None
    instance = MagicMock()
    instance.id = "inst-1"
    instance.name = "生文专家"

    with patch(
        "app.services.hermes_skill.runtime_diagnostics_service.HermesBoundAgentScopeService",
    ) as scope_cls:
        scope = scope_cls.return_value
        scope.list_bound_instance_ids = AsyncMock(return_value=["inst-1"])
        scope.list_bound_pairs = AsyncMock(return_value=[(record, instance)])
        scope.to_agent_summary = MagicMock(return_value={
            "employee_name": "生文专家",
            "binding_type": "external_docker",
            "task_dispatchable": True,
        })

        agents = await svc._agent_stats("org-1", include_unbound=False)

    assert len(agents) == 1
    assert agents[0]["agent_id"] == "inst-1"
    assert agents[0]["employee_name"] == "生文专家"
    assert agents[0]["is_bound"] is True
    assert agents[0]["profile_name"] == "common-writer"


@pytest.mark.asyncio
async def test_agent_stats_include_unbound_adds_scan_records():
    db = AsyncMock()
    svc = RuntimeDiagnosticsService(db)
    bound_record = MagicMock()
    bound_record.profile_name = "common-writer"
    bound_record.container_name = "hermes-common-writer"
    bound_record.instance_id = "inst-1"
    bound_record.gateway_url = "http://127.0.0.1:18900"
    bound_record.gateway_status = "online"
    bound_record.gateway_runtime_status = "ready"
    bound_record.mcp_status = "callable"
    bound_record.last_error = None
    bound_instance = MagicMock()
    bound_instance.id = "inst-1"
    bound_instance.name = "生文专家"

    unbound_record = MagicMock()
    unbound_record.profile_name = "heyejuan"
    unbound_record.container_name = "hermes-heyejuan"
    unbound_record.instance_id = None
    unbound_record.gateway_url = None
    unbound_record.gateway_status = "offline"
    unbound_record.gateway_runtime_status = "unconfigured"
    unbound_record.mcp_status = "unknown"
    unbound_record.last_error = "missing HERMES_GATEWAY_PORT"

    with patch(
        "app.services.hermes_skill.runtime_diagnostics_service.HermesBoundAgentScopeService",
    ) as scope_cls:
        scope = scope_cls.return_value
        scope.is_bound = MagicMock(side_effect=lambda record, instance: instance is not None)
        scope.list_bound_pairs = AsyncMock(return_value=[(bound_record, bound_instance)])
        scope.to_agent_summary = MagicMock(side_effect=lambda record, instance: {
            "employee_name": instance.name if instance else None,
            "binding_type": "external_docker" if instance else None,
            "task_dispatchable": bool(instance),
        })
        with patch(
            "app.services.hermes_skill.runtime_diagnostics_service.HermesDockerBindingService",
        ) as binding_cls:
            binding_cls.return_value.list_all_with_instances = AsyncMock(return_value=[
                (bound_record, bound_instance),
                (unbound_record, None),
            ])
            agents = await svc._agent_stats("org-1", include_unbound=True)

    profile_names = {a["profile_name"] for a in agents}
    assert "common-writer" in profile_names
    assert "heyejuan" in profile_names
