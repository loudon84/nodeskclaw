import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.mcp_tool_approval_request import McpToolApprovalRequest
from app.models.mcp_tool_grant import McpToolGrant
from app.services.mcp_skill_gateway.approval_service import (
    approve_request,
    check_tool_grant,
    create_approval_request,
    revoke_grant,
)
from app.services.mcp_skill_gateway.errors import MCP_TOOL_APPROVAL_REQUIRED
from app.services.mcp_skill_gateway.mcp_tool_registry import get_tool


@pytest.mark.asyncio
async def test_mcp_approval_request_created():
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()

    tool = get_tool("hermes.skills.uninstall")
    assert tool is not None

    with patch(
        "app.services.mcp_skill_gateway.approval_service._record_policy_event",
        new=AsyncMock(),
    ):
        request = await create_approval_request(
            db,
            org_id="org-1",
            requester_user_id="user-1",
            tool=tool,
            instance_id="inst-1",
            instance_ref="demo-inst",
            arguments={"instance_ref": "demo-inst", "skill_name": "demo-skill"},
        )

    assert request.status == "pending"
    assert request.tool_name == "hermes.skills.uninstall"
    assert request.instance_id == "inst-1"


@pytest.mark.asyncio
async def test_mcp_approve_request_creates_grant():
    db = AsyncMock()
    now = datetime.now(timezone.utc)
    request = McpToolApprovalRequest(
        org_id="org-1",
        requester_user_id="user-1",
        tool_name="hermes.skills.uninstall",
        permission="write",
        risk_level="high",
        request_source="mcp_tool_call",
        status="pending",
        requested_at=now,
        instance_id="inst-1",
    )
    request.id = "req-1"

    membership = MagicMock()
    membership.role = "admin"

    with patch(
        "app.services.mcp_skill_gateway.approval_service._require_approver",
        new=AsyncMock(return_value="admin"),
    ), patch(
        "app.services.mcp_skill_gateway.approval_service._get_latest_grant",
        new=AsyncMock(return_value=None),
    ), patch(
        "app.services.mcp_skill_gateway.approval_service._record_policy_event",
        new=AsyncMock(),
    ):
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=request))
        )
        db.add = MagicMock()
        db.flush = AsyncMock()

        grant = await approve_request(
            db,
            request_id="req-1",
            approver_user_id="admin-1",
            org_id="org-1",
            decision_comment="approved",
        )

    assert grant.grant_status == "active"
    assert grant.user_id == "user-1"
    assert request.status == "approved"


@pytest.mark.asyncio
async def test_check_tool_grant_returns_approval_required():
    db = AsyncMock()
    tool = get_tool("hermes.skills.uninstall")
    assert tool is not None

    with patch(
        "app.services.mcp_skill_gateway.approval_service._get_latest_grant",
        new=AsyncMock(return_value=None),
    ), patch(
        "app.services.mcp_skill_gateway.approval_service._get_pending_request",
        new=AsyncMock(return_value=None),
    ), patch(
        "app.services.mcp_skill_gateway.approval_service.create_approval_request",
        new=AsyncMock(return_value=MagicMock(id="apr-1")),
    ):
        result = await check_tool_grant(
            db,
            org_id="org-1",
            user_id="user-1",
            tool=tool,
            instance_id="inst-1",
            instance_ref="demo-inst",
            arguments={"skill_name": "demo-skill"},
        )

    assert result.allowed is False
    assert result.error_code == MCP_TOOL_APPROVAL_REQUIRED
    assert result.approval_request_id == "apr-1"


@pytest.mark.asyncio
async def test_revoke_grant_marks_grant_revoked():
    db = AsyncMock()
    now = datetime.now(timezone.utc)
    grant = McpToolGrant(
        org_id="org-1",
        user_id="user-1",
        tool_name="hermes.skills.uninstall",
        permission="write",
        risk_level="high",
        grant_status="active",
        approved_by="admin-1",
        approved_at=now,
        instance_id="inst-1",
    )
    grant.id = "grant-1"

    with patch(
        "app.services.mcp_skill_gateway.approval_service._require_approver",
        new=AsyncMock(return_value="admin"),
    ), patch(
        "app.services.mcp_skill_gateway.approval_service._record_policy_event",
        new=AsyncMock(),
    ):
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=grant))
        )
        db.flush = AsyncMock()

        revoked = await revoke_grant(
            db,
            grant_id="grant-1",
            org_id="org-1",
            revoker_user_id="admin-1",
            reason="no longer needed",
        )

    assert revoked.grant_status == "revoked"
    assert revoked.revoked_by == "admin-1"
