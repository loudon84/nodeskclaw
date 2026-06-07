import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.hermes_skill.artifact_permission_service import (
    ArtifactPermissionService,
    _VALID_PERMISSION_LEVELS,
)
from app.core.exceptions import BadRequestError, ArtifactAlreadyGrantedError


@pytest.mark.asyncio
async def test_permission_level_whitelist_accepts_valid():
    assert "viewer" in _VALID_PERMISSION_LEVELS
    assert "downloader" in _VALID_PERMISSION_LEVELS
    assert "editor" in _VALID_PERMISSION_LEVELS


@pytest.mark.asyncio
async def test_permission_level_whitelist_rejects_invalid():
    assert "admin" not in _VALID_PERMISSION_LEVELS
    assert "owner" not in _VALID_PERMISSION_LEVELS
    assert "superuser" not in _VALID_PERMISSION_LEVELS


@pytest.mark.asyncio
async def test_grant_permission_rejects_invalid_level():
    db = AsyncMock()
    service = ArtifactPermissionService(db)

    artifact = MagicMock()
    artifact.deleted_at = None
    artifact.org_id = "org-1"
    artifact.created_by = "user-a"
    db.get.return_value = artifact

    membership_result = AsyncMock()
    membership_result.scalar_one_or_none.return_value = MagicMock()
    db.execute.return_value = membership_result

    with pytest.raises(BadRequestError) as exc_info:
        await service.grant_permission(
            artifact_id="art-1",
            org_id="org-1",
            user_id="user-b",
            permission_level="admin",
        )
    assert "permission_level_invalid" in str(exc_info.value.message_key)


@pytest.mark.asyncio
async def test_grant_permission_rejects_cross_org_user():
    db = AsyncMock()
    service = ArtifactPermissionService(db)

    artifact = MagicMock()
    artifact.deleted_at = None
    artifact.org_id = "org-1"
    db.get.return_value = artifact

    membership_result = AsyncMock()
    membership_result.scalar_one_or_none.return_value = None
    db.execute.return_value = membership_result

    with pytest.raises(BadRequestError) as exc_info:
        await service.grant_permission(
            artifact_id="art-1",
            org_id="org-1",
            user_id="user-b",
            permission_level="viewer",
        )
    assert "permission_user_not_in_org" in str(exc_info.value.message_key)


@pytest.mark.asyncio
async def test_revoke_permission_idempotent():
    db = AsyncMock()
    service = ArtifactPermissionService(db)

    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = None
    db.execute.return_value = mock_result

    await service.revoke_permission(
        artifact_id="art-1",
        org_id="org-1",
        user_id="user-b",
    )
