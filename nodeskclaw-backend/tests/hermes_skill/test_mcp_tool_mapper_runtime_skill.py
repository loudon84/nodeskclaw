import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.exceptions import BadRequestError
from app.models.hermes_skill.hermes_task import TaskStatus
from app.services.hermes_skill.mcp_tool_mapper import McpToolMapper
from app.services.hermes_skill.runtime_skill_run_service import RuntimeSkillRunResult
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
         patch(
             "app.services.hermes_skill.mcp_tool_mapper.SkillReleaseService",
         ) as release_cls, \
         patch("app.services.hermes_skill.mcp_tool_mapper.AgentAliasResolver") as mock_alias_cls, \
         patch("app.services.hermes_skill.mcp_tool_mapper.RuntimeSkillRunService") as mock_run_svc_cls, \
         patch("app.services.hermes_skill.mcp_tool_mapper.HermesSkillAuthorizationService") as mock_authz_cls, \
         patch("app.services.hermes_skill.skill_audit_logger.SkillAuditLogger") as mock_audit_cls, \
         patch.object(mapper, "_resolve_runtime_route_health", AsyncMock(return_value={"ok": True})):
        mock_alias_cls.return_value.enrich_routing = AsyncMock()
        mock_alias_cls.return_value.resolve = AsyncMock(return_value=None)
        release_cls.return_value.get_published_by_skill_db_id = AsyncMock(return_value=None)
        mock_authz_cls.return_value.can_invoke = AsyncMock(return_value=True)
        mock_run_svc = AsyncMock()
        mock_run_svc.start.return_value = RuntimeSkillRunResult(
            task=created_task,
            sse_token="sse_test",
            structured_content={
                "run_id": "task-uuid",
                "status": "QUEUED",
                "execution_mode": "async_event",
                "tool_name": "hermes_common_writer__customer-profiling",
                "event_stream": "/api/v1/runs/task-uuid/events",
                "result_url": "/api/v1/runs/task-uuid/result",
                "artifact_url": "/api/v1/runs/task-uuid/artifacts",
                "committed": True,
            },
        )
        mock_run_svc_cls.return_value = mock_run_svc
        mock_audit_cls.return_value = AsyncMock()

        result = await mapper.call_tool(
            "hermes_common_writer__customer-profiling",
            {"prompt": "请为研华科技做客户画像"},
            "org-1",
            "user-1",
            profile_name="default",
        )

    assert result["run_id"] == "task-uuid"
    assert result["status"] == "QUEUED"
    assert result["event_stream"] == "/api/v1/runs/task-uuid/events"
    assert "routing_reason" not in result
    assert "installation_id" not in result
    assert "workspace_id" not in result
    assert "task_no" not in result
    mock_fixed_route.assert_awaited_once()
    mock_alias_cls.return_value.enrich_routing.assert_not_awaited()
    start_req = mock_run_svc.start.await_args.args[0]
    assert start_req.workspace_id is None
    assert start_req.routing_metadata_extras["workspace_id"] == "default"


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
         patch(
             "app.services.hermes_skill.mcp_tool_mapper.settings",
         ) as mock_settings, \
         patch(
             "app.services.hermes_skill.mcp_tool_mapper.SkillReleaseService",
         ) as release_cls, \
         patch("app.services.hermes_skill.mcp_tool_mapper.AgentAliasResolver") as mock_alias_cls, \
         patch("app.services.hermes_skill.mcp_tool_mapper.TaskService") as mock_task_svc_cls, \
         patch("app.services.hermes_skill.mcp_tool_mapper.HermesSkillAuthorizationService") as mock_authz_cls, \
         patch("app.services.hermes_skill.skill_audit_logger.SkillAuditLogger") as mock_audit_cls:
        mock_settings.SKILL_AGENT_ENABLED = False
        mock_alias_cls.return_value.enrich_routing = AsyncMock(
            return_value={"profile_id": "default"},
        )
        mock_alias_cls.return_value.resolve = AsyncMock(return_value=None)
        release_cls.return_value.get_published_by_skill_db_id = AsyncMock(return_value=None)
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


@pytest.mark.asyncio
async def test_public_connector_tool_starts_agent_run():
    db = AsyncMock()
    mapper = McpToolMapper(db)
    run_task = MagicMock()
    run_task.id = "run-1"
    run_task.task_no = "TASK-org1-xyz"
    run_task.status = TaskStatus.QUEUED
    run_task.event_url = "/api/v1/hermes/tasks/run-1/events"
    run_task.artifact_url = "/api/v1/hermes/tasks/run-1/artifacts"

    bundle = {
        "tool": MagicMock(id="tool-1", tool_name="crm_lookup", title="CRM Lookup", description="lookup crm"),
        "instance": MagicMock(id="inst-1", placement="central", config={"url": "https://example.com"}),
        "definition": MagicMock(id="def-1", kind="rest"),
        "secret_ref_name": None,
    }

    with patch.object(PermissionChecker, "require_permission", AsyncMock()), \
         patch.object(SkillRoutingService, "get_exposed_skill", AsyncMock(return_value=None)), \
         patch(
             "app.services.hermes_skill.mcp_tool_mapper.ConnectorService",
         ) as connector_cls, \
         patch(
             "app.services.hermes_skill.mcp_tool_mapper.RuntimeSkillRunService",
         ) as run_svc_cls:
        connector_cls.return_value.get_public_tool_bundle = AsyncMock(return_value=bundle)
        run_svc_cls.return_value.start = AsyncMock(
            return_value=RuntimeSkillRunResult(
                task=run_task,
                sse_token="tok",
                structured_content={"run_id": "run-1", "result_url": "/api/v1/runs/run-1/result"},
            )
        )

        result = await mapper.call_tool(
            "crm_lookup",
            {"customer_id": "c-1"},
            "org-1",
            "user-1",
        )

    assert result["run_id"] == "run-1"
    request = run_svc_cls.return_value.start.await_args.args[0]
    assert request.catalog_kind == "connector"
    assert request.extra_route_snapshot["connector_kind"] == "rest"


@pytest.mark.asyncio
async def test_public_edge_connector_mapper_only_creates_agent_run():
    db = AsyncMock()
    db.add = MagicMock()
    mapper = McpToolMapper(db)
    run_task = MagicMock(id="run-1")
    bundle = {
        "tool": MagicMock(id="tool-1", tool_name="crm_lookup", title="CRM Lookup", description="lookup crm"),
        "instance": MagicMock(
            id="inst-1",
            placement="edge",
            edge_node_id="edge-1",
            config={"url": "https://example.com", "network_policy": {"allowlist": ["example.com:443"]}},
            secret_ref_id=None,
        ),
        "definition": MagicMock(id="def-1", kind="rest"),
        "secret_ref_name": None,
    }
    online_node = MagicMock()

    with (
        patch.object(PermissionChecker, "require_permission", AsyncMock()),
        patch.object(SkillRoutingService, "get_exposed_skill", AsyncMock(return_value=None)),
        patch("app.services.hermes_skill.mcp_tool_mapper.ConnectorService") as connector_cls,
        patch("app.services.hermes_skill.mcp_tool_mapper.RuntimeSkillRunService") as run_svc_cls,
        patch("app.services.hermes_skill.mcp_tool_mapper.is_edge_node_online", return_value=True),
    ):
        connector_cls.return_value.get_public_tool_bundle = AsyncMock(return_value=bundle)
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=online_node)))
        run_svc_cls.return_value.start = AsyncMock(
            return_value=RuntimeSkillRunResult(
                task=run_task,
                sse_token="tok",
                structured_content={"run_id": "run-1"},
            )
        )

        await mapper.call_tool("crm_lookup", {"customer_id": "c-1"}, "org-1", "user-1")

    db.add.assert_not_called()
    request = run_svc_cls.return_value.start.await_args.args[0]
    assert request.extra_route_snapshot["network_policy"] == {"allowlist": ["example.com:443"]}


@pytest.mark.asyncio
async def test_public_connector_server_approval_cannot_be_lowered_by_client():
    db = AsyncMock()
    mapper = McpToolMapper(db)
    run_task = MagicMock(id="run-1")
    tool = MagicMock(id="tool-1", tool_name="crm_lookup", title="CRM Lookup", description="lookup crm")
    tool.extra_metadata = {"requires_approval": True}
    bundle = {
        "tool": tool,
        "instance": MagicMock(id="inst-1", placement="central", config={"url": "https://example.com"}, secret_ref_id=None),
        "definition": MagicMock(id="def-1", kind="rest"),
        "secret_ref_name": None,
    }

    with (
        patch.object(PermissionChecker, "require_permission", AsyncMock()),
        patch.object(SkillRoutingService, "get_exposed_skill", AsyncMock(return_value=None)),
        patch("app.services.hermes_skill.mcp_tool_mapper.ConnectorService") as connector_cls,
        patch("app.services.hermes_skill.mcp_tool_mapper.RuntimeSkillRunService") as run_svc_cls,
    ):
        connector_cls.return_value.get_public_tool_bundle = AsyncMock(return_value=bundle)
        run_svc_cls.return_value.start = AsyncMock(
            return_value=RuntimeSkillRunResult(task=run_task, sse_token="tok", structured_content={"run_id": "run-1"})
        )

        await mapper.call_tool(
            "crm_lookup",
            {"customer_id": "c-1"},
            "org-1",
            "user-1",
            client_context={"requires_approval": False},
        )

    request = run_svc_cls.return_value.start.await_args.args[0]
    assert request.client_context["requires_approval"] is True


@pytest.mark.asyncio
async def test_prompt_first_invalid_installation_workspace_still_accepted():
    db = AsyncMock()
    mapper = McpToolMapper(db)
    skill = _runtime_skill()
    installation = _runtime_installation()
    installation.workspace_id = "missing-or-deleted-workspace"
    routing_result = _runtime_routing_result(skill=skill, installation=installation)

    created_task = MagicMock()
    created_task.id = "run-accepted-1"
    created_task.task_no = "TASK-org1-acc"
    created_task.status = TaskStatus.QUEUED
    created_task.event_url = "/api/v1/hermes/tasks/run-accepted-1/events"
    created_task.artifact_url = "/api/v1/hermes/tasks/run-accepted-1/artifacts"
    created_task.server_artifacts = []

    with patch.object(PermissionChecker, "require_permission", AsyncMock()), \
         patch.object(SkillRoutingService, "get_exposed_skill", AsyncMock(return_value=skill)), \
         patch.object(
             SkillRoutingService,
             "resolve_runtime_skill_fixed_route",
             AsyncMock(return_value=routing_result),
         ), \
         patch(
             "app.services.hermes_skill.mcp_tool_mapper.SkillReleaseService",
         ) as release_cls, \
         patch("app.services.hermes_skill.mcp_tool_mapper.AgentAliasResolver") as mock_alias_cls, \
         patch("app.services.hermes_skill.mcp_tool_mapper.RuntimeSkillRunService") as mock_run_svc_cls, \
         patch("app.services.hermes_skill.mcp_tool_mapper.HermesSkillAuthorizationService") as mock_authz_cls, \
         patch("app.services.hermes_skill.skill_audit_logger.SkillAuditLogger") as mock_audit_cls, \
         patch.object(mapper, "_resolve_runtime_route_health", AsyncMock(return_value={"ok": True})), \
         patch("app.services.hermes_skill.mcp_tool_mapper.McpTaskDedupService") as dedup_cls:
        mock_alias_cls.return_value.enrich_routing = AsyncMock()
        mock_alias_cls.return_value.resolve = AsyncMock(return_value=None)
        release_cls.return_value.get_published_by_skill_db_id = AsyncMock(return_value=None)
        mock_authz_cls.return_value.can_invoke = AsyncMock(return_value=True)
        mock_run_svc = AsyncMock()
        mock_run_svc.start.return_value = RuntimeSkillRunResult(
            task=created_task,
            sse_token="sse_test",
            structured_content={
                "run_id": "run-accepted-1",
                "status": "QUEUED",
                "execution_mode": "async_event",
                "tool_name": skill.tool_name,
                "event_stream": "/api/v1/runs/run-accepted-1/events",
                "result_url": "/api/v1/runs/run-accepted-1/result",
                "artifact_url": "/api/v1/runs/run-accepted-1/artifacts",
                "committed": True,
            },
        )
        mock_run_svc_cls.return_value = mock_run_svc
        mock_audit_cls.return_value = AsyncMock()

        result = await mapper.call_tool(
            skill.tool_name,
            {"prompt": "hello"},
            "org-1",
            "user-1",
            profile_name="default",
            client_context={"request_fingerprint": "fp-should-not-short-circuit"},
        )

    dedup_cls.assert_not_called()
    mock_run_svc.start.assert_awaited_once()
    start_req = mock_run_svc.start.await_args.args[0]
    assert start_req.workspace_id is None
    assert start_req.routing_metadata_extras["workspace_id"] == "missing-or-deleted-workspace"
    assert result["run_id"] == "run-accepted-1"
    assert result["status"] == "QUEUED"
    assert result["event_stream"] == "/api/v1/runs/run-accepted-1/events"
    assert result["result_url"] == "/api/v1/runs/run-accepted-1/result"
    assert result["artifact_url"] == "/api/v1/runs/run-accepted-1/artifacts"
    assert "token=" not in result["event_stream"]
    assert "/hermes/tasks" not in result["event_stream"]
    assert "workspace_id" not in result
    assert "installation_id" not in result
    assert "agent_id" not in result
    assert "profile_id" not in result
    assert "routing_reason" not in result
    assert "task_no" not in result


def test_build_structured_content_employee_queued_without_hermes_token():
    from app.schemas.hermes_skill.runtime_skill_run import StartRuntimeSkillRunRequest
    from app.services.hermes_skill.runtime_skill_run_service import RuntimeSkillRunService

    task = MagicMock()
    task.id = "run-2"
    task.status = TaskStatus.QUEUED
    task.server_artifacts = []
    request = StartRuntimeSkillRunRequest(
        org_id="org-1",
        user_id="user-1",
        tool_name="writer_tool",
        runtime_skill_id="writer_tool",
        agent_profile="default",
        hermes_agent_instance_id="",
        agent_id="agent-1",
        arguments={},
        client_context={},
        output_policy={"artifact_mode": "pull_only"},
        task_source="org_mcp",
        skill_id="writer_tool",
        entrypoint="mcp_skill_gateway",
        execution_mode="async_event",
    )
    with patch(
        "app.services.hermes_skill.runtime_skill_run_service.settings.SKILL_AGENT_ENABLED",
        True,
    ):
        content = RuntimeSkillRunService.build_structured_content(
            task=task,
            request=request,
            event_sse_url="/api/v1/hermes/tasks/run-2/events?token=secret",
            output_policy={"artifact_mode": "pull_only"},
        )
    assert content["status"] == "QUEUED"
    assert content["event_stream"] == "/api/v1/runs/run-2/events"
    assert "token=" not in content["event_stream"]
    assert content["result_url"] == "/api/v1/runs/run-2/result"
    assert content["artifact_url"] == "/api/v1/runs/run-2/artifacts"
    assert "task_no" not in content
    assert "task_id" not in content
