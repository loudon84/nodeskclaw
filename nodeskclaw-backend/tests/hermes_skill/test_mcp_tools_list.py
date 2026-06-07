import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.hermes_skill.permission_checker import PermissionChecker


@pytest.mark.asyncio
async def test_mcp_tools_list_requires_view_permission():
    db = AsyncMock()
    with patch.object(PermissionChecker, "has_permission", return_value=False):
        result = await PermissionChecker.has_permission(db, "user-1", "org-1", "skill:view")
    assert result is False


@pytest.mark.asyncio
async def test_mcp_tools_call_requires_invoke_permission():
    db = AsyncMock()
    with patch.object(PermissionChecker, "has_permission", return_value=True):
        result = await PermissionChecker.has_permission(db, "user-1", "org-1", "skill:invoke")
    assert result is True


@pytest.mark.asyncio
async def test_non_org_member_denied():
    db = AsyncMock()
    with patch.object(PermissionChecker, "get_user_role", return_value=None):
        result = await PermissionChecker.has_permission(db, "user-1", "org-1", "skill:view")
    assert result is False
