from types import SimpleNamespace

from app.services.mcp_skill_gateway.auth import McpAuthContext
from app.services.mcp_skill_gateway.mcp_execution_mode import (
    QUEUED_MODE,
    WAIT_MODE,
    resolve_mcp_execution_mode,
    strip_mcp_control_args,
)


def _skill(source_type: str = "hermes_api_server"):
    return SimpleNamespace(source_type=source_type)


def _auth_ctx(auth_type: str = "mcp_client_token"):
    return McpAuthContext(
        user=SimpleNamespace(id="user-1"),
        org=SimpleNamespace(id="org-1"),
        auth_type=auth_type,
    )


def test_strip_mcp_control_args_removes_wait():
    args, wait_override = strip_mcp_control_args({"company": "ACME", "_wait": False})
    assert args == {"company": "ACME"}
    assert wait_override is False


def test_resolve_mode_mcp_client_token_defaults_wait(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "MCP_TASK_WAIT_ENABLED", True)
    monkeypatch.setattr(settings, "MCP_TASK_WAIT_FOR_MCP_CLIENT_TOKEN", True)
    mode = resolve_mcp_execution_mode(_auth_ctx(), _skill(), {"artifact_mode": "pull_only"})
    assert mode == WAIT_MODE


def test_resolve_mode_user_jwt_defaults_queued(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "MCP_TASK_WAIT_ENABLED", True)
    monkeypatch.setattr(settings, "MCP_TASK_WAIT_FOR_USER_JWT", False)
    mode = resolve_mcp_execution_mode(_auth_ctx("user_jwt"), _skill(), {"artifact_mode": "pull_only"})
    assert mode == QUEUED_MODE


def test_resolve_mode_wait_override_false(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "MCP_TASK_WAIT_ENABLED", True)
    mode = resolve_mcp_execution_mode(
        _auth_ctx(),
        _skill(),
        {"artifact_mode": "pull_only"},
        wait_override=False,
    )
    assert mode == QUEUED_MODE


def test_resolve_mode_non_runtime_skill_queued(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "MCP_TASK_WAIT_ENABLED", True)
    mode = resolve_mcp_execution_mode(_auth_ctx(), _skill("docker"), {}, wait_override=None)
    assert mode == QUEUED_MODE
