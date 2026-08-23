from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import ForbiddenError
from app.models.org_membership import OrgRole
from app.services.hermes_skill.task_service import TaskService


@pytest.mark.asyncio
async def test_assert_task_access_blocks_other_user():
    db = AsyncMock()
    service = TaskService(db)
    task = SimpleNamespace(user_id="owner-1")
    service.get_org_role = AsyncMock(return_value=OrgRole.member)
    with pytest.raises(ForbiddenError):
        await service.assert_task_access(task, "viewer-1", "org-1")


@pytest.mark.asyncio
async def test_assert_task_access_allows_admin_cross_user():
    db = AsyncMock()
    service = TaskService(db)
    task = SimpleNamespace(user_id="owner-1")
    service.get_org_role = AsyncMock(return_value=OrgRole.admin)
    await service.assert_task_access(task, "admin-1", "org-1")
