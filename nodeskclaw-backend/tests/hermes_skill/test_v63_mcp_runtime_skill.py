import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.exceptions import BadRequestError
from app.models.hermes_skill.hermes_task import TaskStatus
from app.services.hermes_skill.mcp_tool_mapper import McpToolMapper, RUNTIME_SKILL_ROUTE_TYPE
from app.services.hermes_skill.permission_checker import PermissionChecker
from app.services.hermes_skill.skill_routing_service import SkillRoutingService
from app.services.hermes_skill.task_result_service import TaskResultService
from app.services.mcp_skill_gateway.errors import map_app_error
from app.services.mcp_skill_gateway.mcp_execution_mode import ASYNC_EVENT_MODE
from app.services.mcp_skill_gateway.auth import McpAuthContext


def _runtime_skill():
    skill = MagicMock()
    skill.id = "skill-1"
    skill.skill_id = "customer-profiling"
    skill.tool_name = "hermes_xieyi__customer-profiling"
    skill.source_type = RUNTIME_SKILL_ROUTE_TYPE
    skill.name = "customer-profiling"
    skill.title = "客户画像"
    skill.description = "desc"
    skill.version = "1.0"
    skill.category = "research"
    skill.input_schema = {}
    skill.extra_metadata = {}
    return skill


def _installation():
    installation = MagicMock()
    installation.agent_id = "agent-1"
    installation.profile_id = "xieyi"
    installation.workspace_id = "default"
    installation.id = "install-1"
    installation.routing_metadata = {
        "route_type": RUNTIME_SKILL_ROUTE_TYPE,
        "force_instance": True,
        "hermes_agent_instance_id": "binding-1",
        "agent_profile": "xieyi",
        "runtime_skill_id": "customer-profiling",
    }
    return installation


@pytest.mark.asyncio
async def test_runtime_skill_tools_list_metadata():
    db = AsyncMock()
    mapper = McpToolMapper(db)
    skill = _runtime_skill()
    installation = _installation()
    binding_record = MagicMock()
    binding_record.id = "binding-1"
    binding_record.gateway_url = "http://127.0.0.1:8080"
    binding_record.gateway_runtime_status = "running"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = installation
    db.execute = AsyncMock(return_value=mock_result)

    with patch(
        "app.services.hermes_external.hermes_docker_binding_service.HermesDockerBindingService"
    ) as binding_cls:
        binding_cls.return_value.get_by_profile = AsyncMock(return_value=binding_record)
        tool = await mapper._skill_to_tool_dict(
            skill,
            "org-1",
            None,
            None,
            MagicMock(resolve=AsyncMock(return_value=None)),
            "",
        )

    assert tool["sourceType"] == RUNTIME_SKILL_ROUTE_TYPE
    assert tool["serverManagedRoute"] is True
    assert tool["defaultExecutionMode"] == ASYNC_EVENT_MODE
    assert tool["sseTimelineEnabled"] is True
    assert tool["routeOverrideAllowed"] is False
    assert "_routing" in tool["forbiddenArgumentKeys"]
    assert tool["routeHealth"]["ok"] is True


@pytest.mark.asyncio
async def test_runtime_skill_route_override_error_has_override_keys():
    db = AsyncMock()
    mapper = McpToolMapper(db)
    skill = _runtime_skill()

    with patch.object(PermissionChecker, "require_permission", AsyncMock()), \
         patch.object(SkillRoutingService, "get_exposed_skill", AsyncMock(return_value=skill)), \
         patch("app.services.hermes_skill.skill_audit_logger.SkillAuditLogger") as mock_audit_cls:
        mock_audit_cls.return_value = AsyncMock()
        with pytest.raises(BadRequestError) as exc_info:
            await mapper.call_tool(
                skill.tool_name,
                {"prompt": "hello", "_routing": {"agent_id": "x"}},
                "org-1",
                "user-1",
            )
    exc = exc_info.value
    assert exc.message_key == "errors.skill.route_override_not_allowed"
    assert exc.details["override_keys"] == ["_routing"]
    assert exc.details["expected_mode"] == "server_managed_fixed_route"

    error = map_app_error(1, exc.message_key, exc.message, extra_data=exc.details)
    data = error["error"]["data"]
    assert data["override_keys"] == ["_routing"]
    assert data["tool_name"] == skill.tool_name


@pytest.mark.asyncio
async def test_result_running_ready_false():
    db = AsyncMock()
    svc = TaskResultService(db)
    task = MagicMock()
    task.id = "task-1"
    task.task_no = "TASK-001"
    task.status = TaskStatus.RUNNING

    with patch.object(svc, "_get_task", AsyncMock(return_value=task)):
        result = await svc.get_result("task-1", "org-1")

    assert result["ready"] is False
    assert result["status"] == "running"
    assert result["content"] is None


@pytest.mark.asyncio
async def test_task_snapshot_running_ready_false():
    db = AsyncMock()
    svc = TaskResultService(db)
    task = MagicMock()
    task.id = "task-1"
    task.task_no = "TASK-001"
    task.status = TaskStatus.RUNNING
    task.tool_name = "hermes_xieyi__customer-profiling"
    task.agent_id = "agent-1"
    task.profile_id = "xieyi"
    task.workspace_id = "default"
    task.routing_metadata = {
        "agent_alias": "xieyi",
        "route_snapshot": {"route_type": RUNTIME_SKILL_ROUTE_TYPE},
    }
    task.created_at = None
    task.completed_at = None
    task.error_code = None
    task.error_message = None
    task.server_artifacts = []

    with patch.object(svc, "_get_task", AsyncMock(return_value=task)), \
         patch.object(svc, "_build_timeline", AsyncMock(return_value=[])), \
         patch.object(svc, "_list_task_artifacts", AsyncMock(return_value=[])):
        snapshot = await svc.get_snapshot("task-1", "org-1")

    assert snapshot["status"] == "running"
    assert snapshot["result"]["ready"] is False
    assert snapshot["artifacts"]["ready"] is False
    assert snapshot["artifacts"]["server_artifacts"] == []
    assert snapshot["links"]["result_url"].endswith("/result")
