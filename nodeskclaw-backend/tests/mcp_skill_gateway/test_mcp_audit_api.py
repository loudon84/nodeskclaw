import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.mcp_skill_gateway.router import list_mcp_audit_logs
from app.models.org_membership import OrgRole


@pytest.mark.asyncio
async def test_audit_api_org_admin_sees_all_users():
    current_user = MagicMock()
    current_user.id = "admin-1"
    current_user.current_org_id = "org-1"
    current_user.is_super_admin = False
    db = AsyncMock()

    row = MagicMock()
    row.id = "log-1"
    row.tool_name = "hermes.instances.list"
    row.permission = "read"
    row.risk_level = "low"
    row.instance_id = None
    row.status = "success"
    row.duration_ms = 12
    row.created_at = datetime.now(timezone.utc)

    role_result = MagicMock()
    role_result.scalar_one_or_none.return_value = OrgRole.admin
    db.execute = AsyncMock(return_value=role_result)

    with patch(
        "app.api.mcp_skill_gateway.router.list_mcp_calls",
        new=AsyncMock(return_value=([row], 1)),
    ) as list_mock:
        response = await list_mcp_audit_logs(
            tool_name=None,
            instance_id=None,
            status=None,
            from_time=None,
            to_time=None,
            limit=50,
            offset=0,
            db=db,
            current_user=current_user,
        )

    list_mock.assert_awaited_once()
    assert list_mock.await_args.kwargs["user_id"] is None
    assert response.data.total == 1
    assert response.data.items[0].tool_name == "hermes.instances.list"


@pytest.mark.asyncio
async def test_audit_api_member_only_sees_self():
    current_user = MagicMock()
    current_user.id = "member-1"
    current_user.current_org_id = "org-1"
    current_user.is_super_admin = False
    db = AsyncMock()

    role_result = MagicMock()
    role_result.scalar_one_or_none.return_value = OrgRole.member
    db.execute = AsyncMock(return_value=role_result)

    with patch(
        "app.api.mcp_skill_gateway.router.list_mcp_calls",
        new=AsyncMock(return_value=([], 0)),
    ) as list_mock:
        await list_mcp_audit_logs(
            tool_name=None,
            instance_id=None,
            status=None,
            from_time=None,
            to_time=None,
            limit=50,
            offset=0,
            db=db,
            current_user=current_user,
        )

    assert list_mock.await_args.kwargs["user_id"] == "member-1"
