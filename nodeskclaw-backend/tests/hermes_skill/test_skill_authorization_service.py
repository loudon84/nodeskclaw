import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.hermes_skill.hermes_skill_authorization_service import HermesSkillAuthorizationService
from app.services.hermes_skill.permission_checker import PermissionChecker


@pytest.mark.asyncio
async def test_admin_can_list_without_grant():
    db = AsyncMock()
    svc = HermesSkillAuthorizationService(db)
    with patch.object(PermissionChecker, "get_user_role", AsyncMock(return_value="admin")):
        assert await svc.can_list("org-1", "user-1", "skill-db", "skill-1") is True


@pytest.mark.asyncio
async def test_member_requires_grant():
    db = AsyncMock()
    svc = HermesSkillAuthorizationService(db)
    with patch.object(PermissionChecker, "get_user_role", AsyncMock(return_value="member")), \
         patch.object(svc, "_check_permission", AsyncMock(return_value=False)):
        assert await svc.can_invoke("org-1", "user-1", "skill-db", "skill-1") is False
