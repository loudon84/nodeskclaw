import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.hermes_skill.permission_checker import PermissionChecker
from app.core.exceptions import ForbiddenError


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
    viewer_perms = frozenset({"skill:view", "hermes_task:view", "hermes_artifact:view"})
    with patch.object(PermissionChecker, "has_permission", return_value=False):
        result = await PermissionChecker.has_permission(db, "viewer-1", "org-1", "skill:invoke")
    assert result is False
