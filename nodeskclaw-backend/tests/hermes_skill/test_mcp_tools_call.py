import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.hermes_skill.mcp_tool_mapper import McpToolMapper
from app.services.hermes_skill.permission_checker import PermissionChecker
from app.services.hermes_skill.skill_routing_service import RoutingResult, ROUTING_REASON_SINGLE, SkillRoutingService
from app.models.hermes_skill.hermes_task import TaskStatus
from app.core.exceptions import ForbiddenError, NotFoundError, BadRequestError


@pytest.mark.asyncio
async def test_tools_call_requires_invoke():
    db = AsyncMock()
    with patch.object(PermissionChecker, "has_permission", return_value=False):
        with pytest.raises(ForbiddenError):
            await PermissionChecker.require_permission(db, "user-1", "org-1", "skill:invoke")


@pytest.mark.asyncio
async def test_tools_call_requires_view():
    db = AsyncMock()
    with patch.object(PermissionChecker, "has_permission", return_value=False):
        with pytest.raises(ForbiddenError):
            await PermissionChecker.require_permission(db, "user-1", "org-1", "skill:view")


@pytest.mark.asyncio
async def test_tools_call_member_has_invoke():
    db = AsyncMock()
    with patch.object(PermissionChecker, "has_permission", return_value=True):
        result = await PermissionChecker.has_permission(db, "member-1", "org-1", "skill:invoke")
    assert result is True


@pytest.mark.asyncio
async def test_tools_call_viewer_no_invoke():
    db = AsyncMock()
    with patch.object(PermissionChecker, "has_permission", return_value=False):
        result = await PermissionChecker.has_permission(db, "viewer-1", "org-1", "skill:invoke")
    assert result is False


@pytest.mark.asyncio
async def test_tools_call_tool_not_found():
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=mock_result)

    mapper = McpToolMapper(db)
    with patch.object(PermissionChecker, "require_permission", return_value=None):
        with pytest.raises(NotFoundError) as exc_info:
            await mapper.call_tool("nonexistent_tool", {}, "org-1", "user-1")
    assert exc_info.value.message_key == "errors.skill.tool_not_found"


@pytest.mark.asyncio
async def test_tools_call_skill_not_installed():
    db = AsyncMock()
    mapper = McpToolMapper(db)
    skill = MagicMock()
    skill.source_type = "hub"
    with patch.object(PermissionChecker, "require_permission", return_value=None), \
         patch.object(SkillRoutingService, "get_exposed_skill", AsyncMock(return_value=skill)), \
         patch.object(SkillRoutingService, "resolve_by_tool_name", new_callable=AsyncMock) as mock_resolve, \
         patch("app.services.hermes_skill.mcp_tool_mapper.AgentAliasResolver") as mock_alias_cls, \
         patch("app.services.hermes_skill.skill_audit_logger.SkillAuditLogger") as mock_audit_cls:
        mock_resolve.side_effect = NotFoundError(
            "Skill test_tool 未安装到任何 Agent",
            "errors.skill.installation_not_found",
        )
        mock_alias_cls.return_value.enrich_routing = AsyncMock(return_value={})
        mock_audit_cls.return_value = AsyncMock()
        with pytest.raises(NotFoundError) as exc_info:
            await mapper.call_tool("test_tool", {}, "org-1", "user-1")
    assert exc_info.value.message_key == "errors.skill.installation_not_found"


@pytest.mark.asyncio
async def test_tools_call_invalid_params():
    db = AsyncMock()

    skill = MagicMock()
    skill.id = "skill-1"
    skill.skill_id = "skill-ext-1"
    skill.tool_name = "test_tool"
    skill.source_type = "hub"
    skill.input_schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    }

    installation = MagicMock()
    installation.agent_id = "agent-1"
    installation.profile_id = None
    installation.workspace_id = "ws-1"
    installation.id = "inst-1"

    routing_result = RoutingResult(
        matched=True,
        installation=installation,
        skill=skill,
        reason=ROUTING_REASON_SINGLE,
        installation_id="inst-1",
        skill_id="skill-ext-1",
        agent_id="agent-1",
    )

    mapper = McpToolMapper(db)
    class _ValidationError(Exception):
        def __init__(self, message: str):
            self.message = message
            super().__init__(message)

    mock_jsonschema = MagicMock()
    mock_jsonschema.ValidationError = _ValidationError
    mock_jsonschema.validate.side_effect = _ValidationError("Validation failed")

    with patch.object(PermissionChecker, "require_permission", return_value=None), \
         patch("app.services.member_skill_service.require_invoke_skill", new_callable=AsyncMock), \
         patch.object(SkillRoutingService, "get_exposed_skill", AsyncMock(return_value=skill)), \
         patch.object(SkillRoutingService, "resolve_by_tool_name", new_callable=AsyncMock) as mock_resolve, \
         patch("app.services.hermes_skill.mcp_tool_mapper.AgentAliasResolver") as mock_alias_cls, \
         patch("app.services.hermes_skill.mcp_tool_mapper.HermesSkillAuthorizationService") as mock_authz_cls, \
         patch.dict("sys.modules", {"jsonschema": mock_jsonschema}):
        mock_resolve.return_value = routing_result
        mock_alias_cls.return_value.enrich_routing = AsyncMock(return_value={})
        mock_authz_cls.return_value.can_invoke = AsyncMock(return_value=True)
        with pytest.raises(BadRequestError) as exc_info:
            await mapper.call_tool("test_tool", {"invalid": 123}, "org-1", "user-1")
    assert exc_info.value.message_key == "errors.skill.input_schema_validation_failed"


@pytest.mark.asyncio
async def test_tools_call_permission_denied():
    db = AsyncMock()
    mapper = McpToolMapper(db)
    with patch.object(PermissionChecker, "require_permission", side_effect=ForbiddenError()):
        with pytest.raises(ForbiddenError):
            await mapper.call_tool("test_tool", {}, "org-1", "user-1")


@pytest.mark.asyncio
async def test_tools_call_creates_task_and_events():
    db = AsyncMock()

    skill = MagicMock()
    skill.id = "skill-1"
    skill.skill_id = "skill-ext-1"
    skill.tool_name = "test_tool"
    skill.source_type = "hub"
    skill.is_mcp_exposed = True
    skill.is_active = True
    skill.input_schema = None

    installation = MagicMock()
    installation.agent_id = "agent-1"
    installation.profile_id = None
    installation.workspace_id = "ws-1"
    installation.id = "inst-1"

    routing_result = RoutingResult(
        matched=True,
        installation=installation,
        skill=skill,
        reason=ROUTING_REASON_SINGLE,
        installation_id="inst-1",
        skill_id="skill-ext-1",
        agent_id="agent-1",
    )

    created_task = MagicMock()
    created_task.id = "task-uuid"
    created_task.task_no = "TASK-org1-abc"
    created_task.status = TaskStatus.QUEUED
    created_task.event_url = "/api/v1/hermes/tasks/task-uuid/events"
    created_task.artifact_url = "/api/v1/hermes/tasks/task-uuid/artifacts"

    mapper = McpToolMapper(db)
    with patch.object(PermissionChecker, "require_permission", return_value=None), \
         patch("app.services.member_skill_service.require_invoke_skill", new_callable=AsyncMock), \
         patch.object(SkillRoutingService, "get_exposed_skill", AsyncMock(return_value=skill)), \
         patch.object(SkillRoutingService, "resolve_by_tool_name", new_callable=AsyncMock) as mock_resolve, \
         patch("app.services.hermes_skill.mcp_tool_mapper.TaskService") as mock_task_svc_cls, \
         patch("app.services.hermes_skill.mcp_tool_mapper.AgentAliasResolver") as mock_alias_cls, \
         patch("app.services.hermes_skill.mcp_tool_mapper.HermesSkillAuthorizationService") as mock_authz_cls, \
         patch("app.services.hermes_skill.skill_audit_logger.SkillAuditLogger") as mock_audit_cls:
        mock_resolve.return_value = routing_result
        mock_alias_cls.return_value.enrich_routing = AsyncMock(return_value={})
        mock_alias_cls.return_value.resolve = AsyncMock(return_value=None)
        mock_authz_cls.return_value.can_invoke = AsyncMock(return_value=True)
        mock_task_svc = AsyncMock()
        mock_task_svc.create_task.return_value = created_task
        mock_task_svc_cls.return_value = mock_task_svc
        mock_audit_cls.return_value = AsyncMock()

        result = await mapper.call_tool("test_tool", {}, "org-1", "user-1")

    assert result["tool_name"] == "test_tool"
    assert result["status"] == "queued"
    assert result["task_id"] == "task-uuid"
    assert result["task_no"] == "TASK-org1-abc"
    assert "event_url" in result
    assert "artifact_url" in result
    mock_task_svc.create_task.assert_awaited_once()


@pytest.mark.asyncio
async def test_mcp_router_tools_call_success():
    from app.api.hermes_skill.mcp_router import mcp_jsonrpc
    from app.core.deps import require_org_member

    db = AsyncMock()
    user = MagicMock()
    user.id = "user-1"
    org = MagicMock()
    org.id = "org-1"

    mapper_result = {
        "tool_name": "test_tool",
        "agent_id": "agent-1",
        "status": "queued",
        "task_id": "task-1",
        "task_no": "TASK-org1-abc",
        "event_url": "/api/v1/hermes/tasks/task-1/events",
        "artifact_url": "/api/v1/hermes/tasks/task-1/artifacts",
    }

    body = {
        "jsonrpc": "2.0",
        "id": 42,
        "method": "tools/call",
        "params": {"name": "test_tool", "arguments": {}},
    }

    with patch("app.services.mcp_skill_gateway.handler.McpToolMapper") as mock_mapper_cls:
        mock_mapper = AsyncMock()
        mock_mapper.call_tool.return_value = mapper_result
        mock_mapper_cls.return_value = mock_mapper

        result = await mcp_jsonrpc(body, MagicMock(headers={}), user_org=(user, org), db=db)

    assert result["jsonrpc"] == "2.0"
    assert result["id"] == 42
    assert "result" in result
    assert result["result"]["content"][0]["text"] == "任务已创建"
    assert result["result"]["structuredContent"]["task_id"] == "task-1"
    assert db.commit.await_count >= 1


@pytest.mark.asyncio
async def test_mcp_router_tools_call_error_format():
    from app.api.hermes_skill.mcp_router import mcp_jsonrpc

    user = MagicMock()
    user.id = "user-1"
    org = MagicMock()
    org.id = "org-1"

    body = {
        "jsonrpc": "2.0",
        "id": 99,
        "method": "tools/call",
        "params": {"name": "nonexistent"},
    }

    db = AsyncMock()
    with patch("app.services.mcp_skill_gateway.handler.McpToolMapper") as mock_mapper_cls:
        mock_mapper = AsyncMock()
        mock_mapper.call_tool.side_effect = NotFoundError("MCP Tool nonexistent 不存在", "errors.skill.tool_not_found")
        mock_mapper_cls.return_value = mock_mapper

        result = await mcp_jsonrpc(body, MagicMock(headers={}), user_org=(user, org), db=db)

    assert result["jsonrpc"] == "2.0"
    assert result["id"] == 99
    assert "error" in result
    assert result["error"]["code"] == -32020
    assert result["error"]["data"]["errorCode"] == "MCP_TOOL_NOT_FOUND"


@pytest.mark.asyncio
async def test_mcp_router_invalid_jsonrpc_version():
    from app.api.hermes_skill.mcp_router import mcp_jsonrpc

    user = MagicMock()
    user.id = "user-1"
    org = MagicMock()
    org.id = "org-1"

    body = {"jsonrpc": "1.0", "id": 1, "method": "tools/list"}
    db = AsyncMock()

    result = await mcp_jsonrpc(body, MagicMock(headers={}), user_org=(user, org), db=db)
    assert result["error"]["code"] == -32030


@pytest.mark.asyncio
async def test_mcp_router_method_not_found():
    from app.api.hermes_skill.mcp_router import mcp_jsonrpc

    user = MagicMock()
    user.id = "user-1"
    org = MagicMock()
    org.id = "org-1"

    body = {"jsonrpc": "2.0", "id": 2, "method": "unknown/method"}
    db = AsyncMock()

    result = await mcp_jsonrpc(body, MagicMock(headers={}), user_org=(user, org), db=db)
    assert result["error"]["code"] == -32601


@pytest.mark.asyncio
async def test_mcp_router_missing_params_name():
    from app.api.hermes_skill.mcp_router import mcp_jsonrpc

    user = MagicMock()
    user.id = "user-1"
    org = MagicMock()
    org.id = "org-1"

    body = {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {}}
    db = AsyncMock()

    result = await mcp_jsonrpc(body, MagicMock(headers={}), user_org=(user, org), db=db)
    assert result["error"]["code"] == -32030
    assert result["error"]["data"]["errorCode"] == "MCP_INVALID_ARGUMENTS"
