import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.exceptions import BadRequestError
from app.models.hermes_skill.hermes_task import TaskStatus
from app.services.hermes_skill.mcp_tool_mapper import McpToolMapper
from app.services.hermes_skill.permission_checker import PermissionChecker
from app.services.hermes_skill.skill_routing_service import (
    ROUTING_REASON_RUNTIME_FIXED_DEFAULT,
    RoutingResult,
    SkillRoutingService,
)


def _runtime_skill():
    skill = MagicMock()
    skill.id = "skill-1"
    skill.skill_id = "hermes_common_writer__customer-profiling"
    skill.tool_name = "hermes_common_writer__customer-profiling"
    skill.source_type = "hermes_api_server"
    skill.input_schema = None
    return skill


def _runtime_installation():
    installation = MagicMock()
    installation.agent_id = "inst-1"
    installation.profile_id = "default"
    installation.workspace_id = "default"
    installation.id = "install-1"
    installation.routing_metadata = {
        "route_type": "hermes_api_server",
        "force_instance": True,
        "hermes_agent_instance_id": "binding-1",
        "agent_profile": "common-writer",
        "runtime_skill_id": "customer-profiling",
    }
    return installation


def _runtime_routing_result(skill=None, installation=None):
    skill = skill or _runtime_skill()
    installation = installation or _runtime_installation()
    return RoutingResult(
        matched=True,
        installation=installation,
        skill=skill,
        reason=ROUTING_REASON_RUNTIME_FIXED_DEFAULT,
        installation_id=installation.id,
        skill_id=skill.skill_id,
        agent_id=installation.agent_id,
    )


@pytest.mark.asyncio
async def test_mcp_client_token_profile_does_not_override_runtime_route():
    db = AsyncMock()
    mapper = McpToolMapper(db)
    skill = _runtime_skill()
    routing_result = _runtime_routing_result(skill=skill)

    created_task = MagicMock()
    created_task.id = "task-uuid"
    created_task.task_no = "TASK-org1-abc"
    created_task.status = TaskStatus.QUEUED
    created_task.event_url = "/api/v1/hermes/tasks/task-uuid/events"
    created_task.artifact_url = "/api/v1/hermes/tasks/task-uuid/artifacts"

    with patch.object(PermissionChecker, "require_permission", AsyncMock()), \
         patch.object(SkillRoutingService, "get_exposed_skill", AsyncMock(return_value=skill)), \
         patch.object(
             SkillRoutingService,
             "resolve_runtime_skill_fixed_route",
             AsyncMock(return_value=routing_result),
         ) as mock_fixed_route, \
         patch("app.services.hermes_skill.mcp_tool_mapper.AgentAliasResolver") as mock_alias_cls, \
         patch("app.services.hermes_skill.mcp_tool_mapper.TaskService") as mock_task_svc_cls, \
         patch("app.services.hermes_skill.mcp_tool_mapper.HermesSkillAuthorizationService") as mock_authz_cls, \
         patch("app.services.hermes_skill.skill_audit_logger.SkillAuditLogger") as mock_audit_cls:
        mock_alias_cls.return_value.enrich_routing = AsyncMock()
        mock_alias_cls.return_value.resolve = AsyncMock(return_value=None)
        mock_authz_cls.return_value.can_invoke = AsyncMock(return_value=True)
        mock_task_svc = AsyncMock()
        mock_task_svc.create_task.return_value = created_task
        mock_task_svc_cls.return_value = mock_task_svc
        mock_audit_cls.return_value = AsyncMock()

        result = await mapper.call_tool(
            "hermes_common_writer__customer-profiling",
            {"prompt": "请为研华科技做客户画像"},
            "org-1",
            "user-1",
            profile_name="default",
        )

    assert result["task_id"] == "task-uuid"
    assert result["routing_reason"] == ROUTING_REASON_RUNTIME_FIXED_DEFAULT
    mock_fixed_route.assert_awaited_once()
    mock_alias_cls.return_value.enrich_routing.assert_not_awaited()


@pytest.mark.parametrize(
    "arguments",
    [
        {"prompt": "hello", "_routing": {"agent_alias": "other-agent"}},
        {"prompt": "hello", "_routing": {}},
        {"prompt": "hello", "_execution": {}},
        {"prompt": "hello", "route_config": {}},
    ],
)
@pytest.mark.asyncio
async def test_runtime_skill_explicit_override_denied(arguments):
    db = AsyncMock()
    mapper = McpToolMapper(db)
    skill = _runtime_skill()

    with patch.object(PermissionChecker, "require_permission", AsyncMock()), \
         patch.object(SkillRoutingService, "get_exposed_skill", AsyncMock(return_value=skill)), \
         patch("app.services.hermes_skill.skill_audit_logger.SkillAuditLogger") as mock_audit_cls:
        mock_audit_cls.return_value = AsyncMock()
        with pytest.raises(BadRequestError) as exc_info:
            await mapper.call_tool(
                "hermes_common_writer__customer-profiling",
                arguments,
                "org-1",
                "user-1",
                profile_name="default",
            )
    assert exc_info.value.message_key == "errors.skill.route_override_not_allowed"


@pytest.mark.asyncio
async def test_normal_skill_profile_routing_unchanged():
    db = AsyncMock()
    mapper = McpToolMapper(db)

    skill = MagicMock()
    skill.id = "skill-1"
    skill.skill_id = "writer"
    skill.tool_name = "writer_tool"
    skill.source_type = "hub"
    skill.input_schema = None

    installation = MagicMock()
    installation.agent_id = "agent-1"
    installation.profile_id = "default"
    installation.workspace_id = "default"
    installation.id = "install-1"
    installation.routing_metadata = None

    routing_result = RoutingResult(
        matched=True,
        installation=installation,
        skill=skill,
        reason="matched_by_explicit_agent",
    )

    created_task = MagicMock()
    created_task.id = "task-uuid"
    created_task.task_no = "TASK-org1-abc"
    created_task.status = TaskStatus.QUEUED
    created_task.event_url = "/api/v1/hermes/tasks/task-uuid/events"
    created_task.artifact_url = "/api/v1/hermes/tasks/task-uuid/artifacts"

    with patch.object(PermissionChecker, "require_permission", AsyncMock()), \
         patch.object(SkillRoutingService, "get_exposed_skill", AsyncMock(return_value=skill)), \
         patch.object(SkillRoutingService, "resolve_by_tool_name", AsyncMock(return_value=routing_result)), \
         patch.object(
             SkillRoutingService,
             "resolve_runtime_skill_fixed_route",
             AsyncMock(),
         ) as mock_fixed_route, \
         patch("app.services.hermes_skill.mcp_tool_mapper.AgentAliasResolver") as mock_alias_cls, \
         patch("app.services.hermes_skill.mcp_tool_mapper.TaskService") as mock_task_svc_cls, \
         patch("app.services.hermes_skill.mcp_tool_mapper.HermesSkillAuthorizationService") as mock_authz_cls, \
         patch("app.services.hermes_skill.skill_audit_logger.SkillAuditLogger") as mock_audit_cls:
        mock_alias_cls.return_value.enrich_routing = AsyncMock(
            return_value={"profile_id": "default"},
        )
        mock_alias_cls.return_value.resolve = AsyncMock(return_value=None)
        mock_authz_cls.return_value.can_invoke = AsyncMock(return_value=True)
        mock_task_svc = AsyncMock()
        mock_task_svc.create_task.return_value = created_task
        mock_task_svc_cls.return_value = mock_task_svc
        mock_audit_cls.return_value = AsyncMock()

        await mapper.call_tool(
            "writer_tool",
            {"prompt": "hello"},
            "org-1",
            "user-1",
            profile_name="default",
        )

    mock_alias_cls.return_value.enrich_routing.assert_awaited_once()
    mock_fixed_route.assert_not_awaited()
