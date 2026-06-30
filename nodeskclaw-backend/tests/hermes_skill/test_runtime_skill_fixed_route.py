import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.hermes_skill.hermes_task import TaskStatus
from app.services.hermes_skill.mcp_tool_mapper import McpToolMapper, RUNTIME_SKILL_ROUTE_TYPE
from app.services.hermes_skill.permission_checker import PermissionChecker
from app.services.hermes_skill.skill_routing_service import SkillRoutingService, RoutingResult
from app.services.hermes_skill.task_service import TaskService
from app.services.mcp_skill_gateway.mcp_execution_mode import ASYNC_EVENT_MODE


def _runtime_skill():
    skill = MagicMock()
    skill.id = "skill-1"
    skill.skill_id = "customer-profiling"
    skill.tool_name = "hermes_xieyi__customer-profiling"
    skill.source_type = RUNTIME_SKILL_ROUTE_TYPE
    skill.name = "customer-profiling"
    skill.title = "Test"
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


def _routing_result(installation):
    rr = MagicMock(spec=RoutingResult)
    rr.installation = installation
    rr.reason = "runtime_fixed_default"
    return rr


def _created_task():
    task = MagicMock()
    task.id = "task-new-1"
    task.task_no = "TASK-0001"
    task.status = TaskStatus.QUEUED
    task.routing_metadata = {}
    task.request_trace_id = None
    task.request_snapshot = None
    task.route_diagnostics = None
    return task


@pytest.mark.asyncio
async def test_runtime_skill_task_route_type_is_hermes_api_server():
    db = AsyncMock()
    mapper = McpToolMapper(db)
    skill = _runtime_skill()
    installation = _installation()
    routing_result = _routing_result(installation)
    task = _created_task()

    auth_ctx = MagicMock()
    auth_ctx.auth_type = "mcp_client_token"
    auth_ctx.profile = "xieyi"
    auth_ctx.mcp_client_token_id = "tok-1"
    auth_ctx.mcp_client_token_prefix = "abcd"

    with (
        patch.object(PermissionChecker, "require_permission", AsyncMock()),
        patch.object(SkillRoutingService, "get_exposed_skill", AsyncMock(return_value=skill)),
        patch.object(SkillRoutingService, "resolve_runtime_skill_fixed_route", AsyncMock(return_value=routing_result)),
        patch.object(TaskService, "create_task", AsyncMock(return_value=task)),
        patch("app.services.hermes_skill.mcp_tool_mapper.AgentAliasResolver") as alias_cls,
        patch("app.services.hermes_skill.mcp_tool_mapper.HermesSkillAuthorizationService") as authz_cls,
        patch("app.services.hermes_skill.skill_audit_logger.SkillAuditLogger") as audit_cls,
        patch("app.services.hermes_skill.mcp_tool_mapper.TaskEventTokenService") as token_cls,
        patch("app.services.hermes_skill.mcp_tool_mapper.resolve_mcp_execution_mode", return_value=ASYNC_EVENT_MODE),
        patch("app.services.hermes_skill.mcp_tool_mapper.OutputPolicyService") as output_cls,
        patch("app.services.hermes_skill.mcp_tool_mapper.McpTaskDedupService") as dedup_cls,
        patch.object(mapper, "_resolve_runtime_route_health", AsyncMock(return_value={"ok": True})),
    ):
        alias_resolver = alias_cls.return_value
        alias_resolver.enrich_routing = AsyncMock(return_value={})
        alias_resolver.resolve = AsyncMock(return_value=MagicMock(agent_alias="xieyi"))
        authz_cls.return_value.can_invoke = AsyncMock(return_value=True)
        audit_cls.return_value = AsyncMock()
        token_cls.return_value.create_token = AsyncMock(return_value={
            "token": "sse-tok",
            "expires_at": "2099-01-01T00:00:00Z",
            "event_url": f"/api/v1/hermes/tasks/{task.id}/events?token=sse-tok",
        })
        output_cls.resolve.return_value = {"mode": "pull_only"}
        dedup_cls.return_value.find_dedupe_task = AsyncMock(return_value=None)

        result = await mapper.call_tool(
            skill.tool_name,
            {"prompt": "test"},
            "org-1",
            user_id="user-1",
            jsonrpc_id=1,
            client_context={"source": "copilot-desktop"},
            profile_name="xieyi",
            auth_ctx=auth_ctx,
            request_trace_id="req_test123",
            request_snapshot={"trace_id": "req_test123", "entrypoint": "mcp_skill_gateway"},
        )

    assert task.request_trace_id == "req_test123"
    assert task.request_snapshot is not None
    assert task.request_snapshot["trace_id"] == "req_test123"

    assert task.route_diagnostics is not None
    assert task.route_diagnostics["route_type"] == RUNTIME_SKILL_ROUTE_TYPE


@pytest.mark.asyncio
async def test_runtime_skill_does_not_call_v1_runs():
    db = AsyncMock()
    mapper = McpToolMapper(db)
    skill = _runtime_skill()
    installation = _installation()
    routing_result = _routing_result(installation)
    task = _created_task()

    auth_ctx = MagicMock()
    auth_ctx.auth_type = "mcp_client_token"
    auth_ctx.profile = "xieyi"

    with (
        patch.object(PermissionChecker, "require_permission", AsyncMock()),
        patch.object(SkillRoutingService, "get_exposed_skill", AsyncMock(return_value=skill)),
        patch.object(SkillRoutingService, "resolve_runtime_skill_fixed_route", AsyncMock(return_value=routing_result)),
        patch.object(TaskService, "create_task", AsyncMock(return_value=task)),
        patch("app.services.hermes_skill.mcp_tool_mapper.AgentAliasResolver") as alias_cls,
        patch("app.services.hermes_skill.mcp_tool_mapper.HermesSkillAuthorizationService") as authz_cls,
        patch("app.services.hermes_skill.skill_audit_logger.SkillAuditLogger") as audit_cls,
        patch("app.services.hermes_skill.mcp_tool_mapper.TaskEventTokenService") as token_cls,
        patch("app.services.hermes_skill.mcp_tool_mapper.resolve_mcp_execution_mode", return_value=ASYNC_EVENT_MODE),
        patch("app.services.hermes_skill.mcp_tool_mapper.OutputPolicyService") as output_cls,
        patch("app.services.hermes_skill.mcp_tool_mapper.McpTaskDedupService") as dedup_cls,
        patch.object(mapper, "_resolve_runtime_route_health", AsyncMock(return_value={"ok": True})),
    ):
        alias_resolver = alias_cls.return_value
        alias_resolver.enrich_routing = AsyncMock(return_value={})
        alias_resolver.resolve = AsyncMock(return_value=MagicMock(agent_alias="xieyi"))
        authz_cls.return_value.can_invoke = AsyncMock(return_value=True)
        audit_cls.return_value = AsyncMock()
        token_cls.return_value.create_token = AsyncMock(return_value={
            "token": "sse-tok",
            "expires_at": "2099-01-01T00:00:00Z",
            "event_url": f"/api/v1/hermes/tasks/{task.id}/events?token=sse-tok",
        })
        output_cls.resolve.return_value = {"mode": "pull_only"}
        dedup_cls.return_value.find_dedupe_task = AsyncMock(return_value=None)

        result = await mapper.call_tool(
            skill.tool_name,
            {"prompt": "test"},
            "org-1",
            user_id="user-1",
            auth_ctx=auth_ctx,
            request_trace_id="req_test456",
            request_snapshot={},
        )

    assert result.get("task_id") == task.id
    assert "hermes_run_id" not in result or result.get("hermes_run_id") is None
