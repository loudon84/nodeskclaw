import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.hermes_skill.mcp_tool_mapper import McpToolMapper
from app.services.hermes_skill.permission_checker import PermissionChecker
from app.models.hermes_skill.hermes_task import HermesTask, TaskStatus
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
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = None
    db.execute.return_value = mock_result

    mapper = McpToolMapper(db)
    with patch.object(PermissionChecker, "require_permission", return_value=None):
        with pytest.raises(NotFoundError) as exc_info:
            await mapper.call_tool("nonexistent_tool", {}, "org-1", "user-1")
    assert exc_info.value.message_key == "errors.skill.tool_not_found"


@pytest.mark.asyncio
async def test_tools_call_skill_not_installed():
    db = AsyncMock()

    skill = MagicMock()
    skill.id = "skill-1"
    skill.tool_name = "test_tool"
    skill.is_mcp_exposed = True
    skill.is_active = True

    mock_skill_result = AsyncMock()
    mock_skill_result.scalar_one_or_none.return_value = skill

    mock_install_result = AsyncMock()
    mock_install_result.scalar_one_or_none.return_value = None

    call_count = 0

    def mock_execute(stmt):
        nonlocal call_count
        call_count += 1
        if call_count <= 1:
            return mock_skill_result
        return mock_install_result

    db.execute.side_effect = mock_execute

    mapper = McpToolMapper(db)
    with patch.object(PermissionChecker, "require_permission", return_value=None):
        with pytest.raises(NotFoundError) as exc_info:
            await mapper.call_tool("test_tool", {}, "org-1", "user-1")
    assert exc_info.value.message_key == "errors.skill.tool_not_installed"


@pytest.mark.asyncio
async def test_tools_call_invalid_params():
    db = AsyncMock()

    skill = MagicMock()
    skill.id = "skill-1"
    skill.tool_name = "test_tool"
    skill.is_mcp_exposed = True
    skill.is_active = True
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

    mock_skill_result = AsyncMock()
    mock_skill_result.scalar_one_or_none.return_value = skill

    mock_install_result = AsyncMock()
    mock_install_result.scalar_one_or_none.return_value = installation

    call_count = 0

    def mock_execute(stmt):
        nonlocal call_count
        call_count += 1
        if call_count <= 1:
            return mock_skill_result
        return mock_install_result

    db.execute.side_effect = mock_execute

    mapper = McpToolMapper(db)
    with patch.object(PermissionChecker, "require_permission", return_value=None), \
         patch("app.services.hermes_skill.mcp_tool_mapper.jsonschema") as mock_jsonschema:
        mock_jsonschema.validate.side_effect = Exception("Validation failed")
        mock_jsonschema.ValidationError = Exception

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
    skill.tool_name = "test_tool"
    skill.is_mcp_exposed = True
    skill.is_active = True
    skill.input_schema = None

    installation = MagicMock()
    installation.agent_id = "agent-1"
    installation.profile_id = None
    installation.workspace_id = "ws-1"
    installation.id = "inst-1"

    mock_skill_result = AsyncMock()
    mock_skill_result.scalar_one_or_none.return_value = skill

    mock_install_result = AsyncMock()
    mock_install_result.scalar_one_or_none.return_value = installation

    call_count = 0

    def mock_execute(stmt):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_skill_result
        if call_count == 2:
            return mock_install_result
        return AsyncMock()

    db.execute.side_effect = mock_execute
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    mapper = McpToolMapper(db)
    with patch.object(PermissionChecker, "require_permission", return_value=None):
        result = await mapper.call_tool("test_tool", {}, "org-1", "user-1")

    assert result["tool_name"] == "test_tool"
    assert result["status"] == "queued"
    assert "task_id" in result
    assert "task_no" in result
    assert "event_url" in result
    assert "artifact_url" in result


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

    with patch("app.api.hermes_skill.mcp_router.McpToolMapper") as mock_mapper_cls, \
         patch("app.api.hermes_skill.mcp_router.require_org_member", return_value=(user, org)), \
         patch("app.api.hermes_skill.mcp_router.get_db", return_value=db):
        mock_mapper = AsyncMock()
        mock_mapper.call_tool.return_value = mapper_result
        mock_mapper_cls.return_value = mock_mapper

        result = await mcp_jsonrpc(body, user_org=(user, org), db=db)

    assert result["jsonrpc"] == "2.0"
    assert result["id"] == 42
    assert "result" in result
    assert "content" in result["result"]


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
    with patch("app.api.hermes_skill.mcp_router.McpToolMapper") as mock_mapper_cls:
        mock_mapper = AsyncMock()
        mock_mapper.call_tool.side_effect = NotFoundError("MCP Tool nonexistent 不存在", "errors.skill.tool_not_found")
        mock_mapper_cls.return_value = mock_mapper

        result = await mcp_jsonrpc(body, user_org=(user, org), db=db)

    assert result["jsonrpc"] == "2.0"
    assert result["id"] == 99
    assert "error" in result
    assert result["error"]["code"] == -32001


@pytest.mark.asyncio
async def test_mcp_router_invalid_jsonrpc_version():
    from app.api.hermes_skill.mcp_router import mcp_jsonrpc

    user = MagicMock()
    user.id = "user-1"
    org = MagicMock()
    org.id = "org-1"

    body = {"jsonrpc": "1.0", "id": 1, "method": "tools/list"}
    db = AsyncMock()

    result = await mcp_jsonrpc(body, user_org=(user, org), db=db)
    assert result["error"]["code"] == -32600


@pytest.mark.asyncio
async def test_mcp_router_method_not_found():
    from app.api.hermes_skill.mcp_router import mcp_jsonrpc

    user = MagicMock()
    user.id = "user-1"
    org = MagicMock()
    org.id = "org-1"

    body = {"jsonrpc": "2.0", "id": 2, "method": "unknown/method"}
    db = AsyncMock()

    result = await mcp_jsonrpc(body, user_org=(user, org), db=db)
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

    result = await mcp_jsonrpc(body, user_org=(user, org), db=db)
    assert result["error"]["code"] == -32602
