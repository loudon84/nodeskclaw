from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.hermes_skill.hermes_task import TaskStatus
from app.services.mcp_skill_gateway.auth import McpAuthContext
from app.services.mcp_skill_gateway.mcp_task_dedup_service import (
    McpTaskDedupService,
    build_mcp_task_dedup_key,
)


def _auth_ctx():
    return McpAuthContext(
        user=SimpleNamespace(id="user-1"),
        org=SimpleNamespace(id="org-1"),
        auth_type="mcp_client_token",
        mcp_client_token_id="tok-1",
        mcp_client_token_prefix="ndsk_mcp_writer_abcd",
    )


def test_build_mcp_task_dedup_key_stable():
    auth_ctx = _auth_ctx()
    key_a = build_mcp_task_dedup_key("org-1", auth_ctx, "tool.a", {"company": "ACME"})
    key_b = build_mcp_task_dedup_key("org-1", auth_ctx, "tool.a", {"company": "ACME"})
    assert key_a == key_b
    assert len(key_a) == 64


def test_build_mcp_task_dedup_key_changes_with_arguments():
    auth_ctx = _auth_ctx()
    key_a = build_mcp_task_dedup_key("org-1", auth_ctx, "tool.a", {"company": "ACME"})
    key_b = build_mcp_task_dedup_key("org-1", auth_ctx, "tool.a", {"company": "OTHER"})
    assert key_a != key_b


@pytest.mark.asyncio
async def test_find_dedupe_task_returns_latest_match(monkeypatch):
    existing = SimpleNamespace(id="task-existing", status=TaskStatus.RUNNING)
    result = MagicMock()
    result.scalar_one_or_none.return_value = existing
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)

    from app.core.config import settings
    monkeypatch.setattr(settings, "MCP_TASK_DEDUP_ENABLED", True)
    monkeypatch.setattr(settings, "MCP_TASK_DEDUP_WINDOW_SECONDS", 600)

    found = await McpTaskDedupService(db).find_dedupe_task("org-1", "abc123")

    assert found is existing
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_find_dedupe_task_disabled(monkeypatch):
    db = AsyncMock()
    from app.core.config import settings
    monkeypatch.setattr(settings, "MCP_TASK_DEDUP_ENABLED", False)
    found = await McpTaskDedupService(db).find_dedupe_task("org-1", "abc123")
    assert found is None
    db.execute.assert_not_called()
