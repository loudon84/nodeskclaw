import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.models.hermes_skill.hermes_task import TaskStatus
from app.schemas.hermes_instance_skill import HermesInstanceSkillItem, HermesInstanceSkillListResponse
from app.schemas.hermes_skill.runtime_skill_registration import RuntimeSkillRegisterRequest
from app.services.hermes_external import hermes_instance_skill_service as instance_skill_service
from app.services.hermes_skill.hermes_task_worker import HermesTaskWorker
from app.services.hermes_skill.permission_checker import PermissionChecker
from app.services.hermes_skill.mcp_tool_mapper import McpToolMapper
from app.services.hermes_skill.runtime_skill_registration_service import RuntimeSkillRegistrationService
from app.services.hermes_skill.skill_routing_service import ROUTING_REASON_SINGLE, RoutingResult, SkillRoutingService


def _skill_list(agent_profile: str = "common-writer") -> HermesInstanceSkillListResponse:
    return HermesInstanceSkillListResponse(
        agent_profile=agent_profile,
        gateway_url="http://127.0.0.1:18789",
        source_mode="api_server_default",
        total=1,
        skills=[
            HermesInstanceSkillItem(
                name="customer-profiling",
                category="sales",
                description="客户画像",
            ),
        ],
        warnings=[],
        last_refreshed_at=datetime.now(timezone.utc),
    )


def _binding_record():
    record = MagicMock()
    record.id = "hermes-rec-1"
    record.instance_id = "inst-1"
    record.profile_name = "common-writer"
    record.gateway_url = "http://127.0.0.1:18789"
    record.env_file = "/tmp/.env"
    return record


@pytest.mark.asyncio
async def test_register_runtime_skill_creates_skill_installation_grant():
    db = AsyncMock()
    service = RuntimeSkillRegistrationService(db)

    with patch(
        "app.services.hermes_skill.runtime_skill_registration_service.HermesDockerBindingService",
    ) as mock_binding_cls, patch.object(
        instance_skill_service,
        "list_instance_skills",
        AsyncMock(return_value=_skill_list()),
    ), patch.object(
        service,
        "_get_skill_by_skill_id",
        AsyncMock(return_value=None),
    ), patch.object(
        service,
        "_upsert_skill",
        AsyncMock(return_value=MagicMock(id="skill-db-1")),
    ) as mock_upsert_skill, patch.object(
        service,
        "_upsert_installation",
        AsyncMock(return_value=(True, MagicMock(id="inst-db-1"))),
    ) as mock_upsert_installation, patch.object(
        service,
        "_upsert_grant",
        AsyncMock(return_value=(True, MagicMock())),
    ) as mock_upsert_grant, patch(
        "app.services.hermes_skill.runtime_skill_registration_service.hooks.emit",
        AsyncMock(),
    ), patch(
        "app.services.hermes_skill.runtime_skill_registration_service.parse_env_file",
    ) as mock_parse_env:
        mock_binding_cls.return_value.get_by_profile = AsyncMock(return_value=_binding_record())
        mock_parse_env.return_value = MagicMock(api_server_model_name="common-writer")

        result = await service.register_to_org_mcp(
            org_id="org-1",
            operator_user_id="user-1",
            agent_profile="common-writer",
            runtime_skill_id="customer-profiling",
            request=RuntimeSkillRegisterRequest(),
        )

    assert result.status == "created"
    assert result.tool_name == "hermes_common_writer__customer-profiling"
    assert result.hermes_instance_name == "common-writer"
    mock_upsert_skill.assert_awaited_once()
    mock_upsert_installation.assert_awaited_once()
    mock_upsert_grant.assert_awaited_once()
    route_config = mock_upsert_installation.await_args.kwargs["route_config"]
    assert route_config["route_type"] == "hermes_api_server"
    assert route_config["force_instance"] is True
    assert route_config["hermes_agent_instance_id"] == "hermes-rec-1"


@pytest.mark.asyncio
async def test_register_runtime_skill_not_found():
    db = AsyncMock()
    service = RuntimeSkillRegistrationService(db)
    empty_list = HermesInstanceSkillListResponse(
        agent_profile="common-writer",
        gateway_url="http://127.0.0.1:18789",
        source_mode="api_server_default",
        total=0,
        skills=[],
        warnings=[],
        last_refreshed_at=datetime.now(timezone.utc),
    )

    with patch(
        "app.services.hermes_skill.runtime_skill_registration_service.HermesDockerBindingService",
    ) as mock_binding_cls, patch.object(
        instance_skill_service,
        "list_instance_skills",
        AsyncMock(return_value=empty_list),
    ):
        mock_binding_cls.return_value.get_by_profile = AsyncMock(return_value=_binding_record())
        with pytest.raises(NotFoundError) as exc_info:
            await service.register_to_org_mcp(
                org_id="org-1",
                operator_user_id="user-1",
                agent_profile="common-writer",
                runtime_skill_id="missing-skill",
                request=RuntimeSkillRegisterRequest(),
            )
    assert exc_info.value.message_key == "errors.hermes.runtime_skill_not_found"


@pytest.mark.asyncio
async def test_register_requires_bound_instance():
    db = AsyncMock()
    service = RuntimeSkillRegistrationService(db)
    record = _binding_record()
    record.instance_id = None

    with patch(
        "app.services.hermes_skill.runtime_skill_registration_service.HermesDockerBindingService",
    ) as mock_binding_cls:
        mock_binding_cls.return_value.get_by_profile = AsyncMock(return_value=record)
        with pytest.raises(BadRequestError) as exc_info:
            await service.register_to_org_mcp(
                org_id="org-1",
                operator_user_id="user-1",
                agent_profile="common-writer",
                runtime_skill_id="customer-profiling",
                request=RuntimeSkillRegisterRequest(),
            )
    assert exc_info.value.message_key == "errors.skill.route_config_invalid"


@pytest.mark.asyncio
async def test_register_tool_name_conflict():
    db = AsyncMock()
    service = RuntimeSkillRegistrationService(db)
    existing = MagicMock()
    existing.extra_metadata = {
        "runtime_skill_id": "other-skill",
        "agent_profile": "common-writer",
    }

    with patch(
        "app.services.hermes_skill.runtime_skill_registration_service.HermesDockerBindingService",
    ) as mock_binding_cls, patch.object(
        instance_skill_service,
        "list_instance_skills",
        AsyncMock(return_value=_skill_list()),
    ), patch.object(
        service,
        "_get_skill_by_skill_id",
        AsyncMock(return_value=existing),
    ):
        mock_binding_cls.return_value.get_by_profile = AsyncMock(return_value=_binding_record())
        with pytest.raises(ConflictError) as exc_info:
            await service.register_to_org_mcp(
                org_id="org-1",
                operator_user_id="user-1",
                agent_profile="common-writer",
                runtime_skill_id="customer-profiling",
                request=RuntimeSkillRegisterRequest(tool_name="hermes_common_writer__custom"),
            )
    assert exc_info.value.message_key == "errors.skill.tool_name_conflict"


@pytest.mark.asyncio
async def test_org_mcp_tools_call_rejects_route_override():
    db = AsyncMock()
    skill = MagicMock()
    skill.id = "skill-1"
    skill.skill_id = "hermes_common_writer__customer-profiling"
    skill.tool_name = "hermes_common_writer__customer-profiling"
    skill.source_type = "hermes_api_server"
    skill.input_schema = None

    installation = MagicMock()
    installation.agent_id = "inst-1"
    installation.profile_id = "default"
    installation.workspace_id = "default"
    installation.id = "install-1"
    installation.routing_metadata = {"route_type": "hermes_api_server"}

    routing_result = RoutingResult(
        matched=True,
        installation=installation,
        skill=skill,
        reason=ROUTING_REASON_SINGLE,
    )

    mapper = McpToolMapper(db)
    with patch.object(PermissionChecker, "require_permission", AsyncMock()), \
         patch.object(
             SkillRoutingService,
             "extract_routing",
             return_value=({"prompt": "hello"}, {"agent_id": "other-agent"}),
         ), \
         patch.object(
             SkillRoutingService,
             "resolve_by_tool_name",
             AsyncMock(return_value=routing_result),
         ), \
         patch(
             "app.services.hermes_skill.mcp_tool_mapper.AgentAliasResolver",
         ) as mock_alias_cls, \
         patch(
             "app.services.hermes_skill.mcp_tool_mapper.HermesSkillAuthorizationService",
         ) as mock_authz_cls:
        mock_alias_cls.return_value.enrich_routing = AsyncMock(
            return_value={"agent_id": "other-agent"},
        )
        mock_authz_cls.return_value.can_invoke = AsyncMock(return_value=True)
        with pytest.raises(BadRequestError) as exc_info:
            await mapper.call_tool(
                "hermes_common_writer__customer-profiling",
                {"prompt": "hello", "_routing": {"agent_id": "other-agent"}},
                "org-1",
                "user-1",
            )
    assert exc_info.value.message_key == "errors.skill.route_override_not_allowed"


@pytest.mark.asyncio
async def test_worker_executes_hermes_api_server_route():
    worker = HermesTaskWorker()
    db = AsyncMock()

    task = MagicMock()
    task.id = "task-1"
    task.org_id = "org-1"
    task.task_no = "TASK-001"
    task.skill_id = "hermes_common_writer__customer-profiling"
    task.tool_name = "hermes_common_writer__customer-profiling"
    task.agent_id = "inst-1"
    task.arguments = {"prompt": "analyze customer", "context": {"company": "Acme"}}
    task.routing_metadata = {
        "route_snapshot": {
            "route_type": "hermes_api_server",
            "agent_profile": "common-writer",
            "hermes_agent_instance_id": "hermes-rec-1",
            "runtime_skill_id": "customer-profiling",
            "hermes_instance_name": "common-writer",
            "timeout_seconds": 1800,
        },
    }
    task.status = TaskStatus.RUNNING
    task.worker_id = worker._worker_id
    task.locked_at = datetime.now(timezone.utc)

    task_service = AsyncMock()
    event_service = AsyncMock()
    audit_logger = AsyncMock()

    with patch(
        "app.services.hermes_skill.hermes_task_worker.HermesDockerBindingService",
    ) as mock_binding_cls, patch(
        "app.services.hermes_external.hermes_bound_agent_scope_service.HermesBoundAgentScopeService",
    ) as mock_scope_cls, patch(
        "app.services.hermes_skill.hermes_task_worker.execute_runtime_skill_via_api_server",
        AsyncMock(return_value="analysis result"),
    ) as mock_execute:
        mock_binding_cls.return_value.get_by_profile = AsyncMock(return_value=_binding_record())
        mock_scope_cls.return_value.assert_dispatchable_instance = AsyncMock()

        await worker._execute_api_server_task(
            db,
            task,
            task.routing_metadata["route_snapshot"],
            task_service,
            event_service,
            audit_logger,
        )

    mock_execute.assert_awaited_once()
    task_service.mark_completed.assert_awaited_once()
    event_service.write_event.assert_awaited()
    assert task.dispatch_status == "finished"


@pytest.mark.asyncio
async def test_worker_api_server_completed_calls_artifact_discovery():
    from app.services.hermes_skill.hermes_task_worker import HermesTaskWorker

    worker = HermesTaskWorker()
    db = AsyncMock()
    task = MagicMock()
    task.id = "task-1"
    task.org_id = "org-1"
    task.task_no = "TASK-001"
    task.skill_id = "hermes_common_writer__customer-profiling"
    task.tool_name = "hermes_common_writer__customer-profiling"
    task.agent_id = "inst-1"
    task.arguments = {"prompt": "analyze customer"}
    task.routing_metadata = {
        "route_snapshot": {
            "route_type": "hermes_api_server",
            "agent_profile": "common-writer",
            "hermes_agent_instance_id": "hermes-rec-1",
            "runtime_skill_id": "customer-profiling",
            "hermes_instance_name": "common-writer",
        },
    }
    task.worker_id = worker._worker_id
    task.locked_at = datetime.now(timezone.utc)

    task_service = AsyncMock()
    event_service = AsyncMock()
    audit_logger = AsyncMock()

    with patch(
        "app.services.hermes_skill.hermes_task_worker.HermesDockerBindingService",
    ) as mock_binding_cls, patch(
        "app.services.hermes_external.hermes_bound_agent_scope_service.HermesBoundAgentScopeService",
    ) as mock_scope_cls, patch(
        "app.services.hermes_skill.hermes_task_worker.execute_runtime_skill_via_api_server",
        AsyncMock(return_value="saved to /data/hermes/workspace/a.md"),
    ), patch(
        "app.services.hermes_skill.artifact_discovery_service.ArtifactDiscoveryService.discover_and_register_for_task",
        AsyncMock(return_value=[]),
    ) as mock_discover:
        mock_binding_cls.return_value.get_by_profile = AsyncMock(return_value=_binding_record())
        mock_scope_cls.return_value.assert_dispatchable_instance = AsyncMock()

        await worker._execute_api_server_task(
            db,
            task,
            task.routing_metadata["route_snapshot"],
            task_service,
            event_service,
            audit_logger,
        )

    mock_discover.assert_awaited_once()
    assert mock_discover.await_args.kwargs["result_text"] == "saved to /data/hermes/workspace/a.md"


@pytest.mark.asyncio
async def test_worker_does_not_fallback_when_instance_mismatch():
    worker = HermesTaskWorker()
    db = AsyncMock()
    task = MagicMock()
    task.id = "task-2"
    task.org_id = "org-1"
    task.task_no = "TASK-002"
    task.agent_id = "inst-1"
    task.routing_metadata = {
        "route_snapshot": {
            "route_type": "hermes_api_server",
            "agent_profile": "common-writer",
            "hermes_agent_instance_id": "wrong-id",
            "runtime_skill_id": "customer-profiling",
            "hermes_instance_name": "common-writer",
        },
    }
    task.worker_id = worker._worker_id
    task.locked_at = datetime.now(timezone.utc)
    task.dispatch_status = "running"

    task_service = AsyncMock()
    event_service = AsyncMock()
    audit_logger = AsyncMock()

    record = _binding_record()
    with patch(
        "app.services.hermes_skill.hermes_task_worker.HermesDockerBindingService",
    ) as mock_binding_cls, patch(
        "app.services.hermes_skill.hermes_task_worker.execute_runtime_skill_via_api_server",
        AsyncMock(),
    ) as mock_execute:
        mock_binding_cls.return_value.get_by_profile = AsyncMock(return_value=record)
        await worker._execute_api_server_task(
            db,
            task,
            task.routing_metadata["route_snapshot"],
            task_service,
            event_service,
            audit_logger,
        )

    mock_execute.assert_not_called()
    task_service.mark_failed.assert_awaited_once()
    assert task_service.mark_failed.await_args.kwargs["error_code"] == "hermes_instance_unavailable"
