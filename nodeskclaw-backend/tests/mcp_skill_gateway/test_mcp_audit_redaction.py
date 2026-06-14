import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.mcp_call_log import McpCallLog
from app.services.mcp_skill_gateway.audit_service import log_mcp_call, sanitize_input_summary


def test_sanitize_input_summary_redacts_sensitive_fields():
    summary = sanitize_input_summary({
        "instance_ref": "demo-profile",
        "token": "secret-token",
        "password": "secret-password",
        "webui_password": "abc",
    })

    assert summary == {
        "instance_ref": {"type": "string", "length": 12},
    }


def test_sanitize_input_summary_records_string_length():
    summary = sanitize_input_summary({"note": "hello"})

    assert summary == {"note": {"type": "string", "length": 5}}


@pytest.mark.asyncio
async def test_log_mcp_call_does_not_persist_sensitive_arguments():
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    await log_mcp_call(
        db,
        org_id="org-1",
        user_id="user-1",
        tool_name="hermes.instance.status",
        status="success",
        arguments={"instance_ref": "demo", "token": "secret"},
        permission="read",
        risk_level="low",
    )

    entry = db.add.call_args.args[0]
    assert isinstance(entry, McpCallLog)
    assert entry.input_summary == {"instance_ref": {"type": "string", "length": 4}}
    assert "token" not in (entry.input_summary or {})
