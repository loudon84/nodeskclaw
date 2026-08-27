import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.mcp_skill_gateway.handler import dispatch_authenticated


@pytest.mark.asyncio
async def test_tools_call_success_returns_json_content():
    user = MagicMock()
    user.id = "user-1"
    org = MagicMock()
    org.id = "org-1"
    body = {
        "jsonrpc": "2.0",
        "id": "call-1",
        "method": "tools/call",
        "params": {
            "name": "writer_article_generate",
            "arguments": {"prompt": "hello"},
        },
    }
    db = AsyncMock()
    payload = {
        "task_id": "task-1",
        "status": "queued",
        "ready": False,
        "content": [{"type": "text", "text": "accepted"}],
        "structuredContent": {"task_id": "task-1", "status": "queued"},
    }

    with patch(
        "app.services.mcp_skill_gateway.handler.McpToolMapper",
    ) as mapper_cls, patch(
        "app.services.mcp_skill_gateway.handler.log_mcp_call",
        new=AsyncMock(),
    ):
        mapper = AsyncMock()
        mapper.call_tool.return_value = payload
        mapper_cls.return_value = mapper

        result = await dispatch_authenticated(body, (user, org), db)

    assert result["result"]["isError"] is False
    assert result["result"]["structuredContent"]["task_id"] == "task-1"
