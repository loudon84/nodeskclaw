import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.hermes_skill.artifact_service import ArtifactService
from app.services.hermes_skill.permission_checker import PermissionChecker
from app.models.hermes_skill.hermes_artifact import HermesArtifact


def _make_artifact(**overrides) -> HermesArtifact:
    defaults = {
        "id": "art-1",
        "org_id": "org-1",
        "task_id": "task-1",
        "workspace_id": "ws-1",
        "file_name": "result.txt",
        "file_path": "/tmp/nodeskclaw-workspaces/ws1/.nodeskclaw/runs/task-1/outputs/result.txt",
        "permission_scope": "org",
        "created_by": "user-a",
    }
    defaults.update(overrides)
    art = MagicMock(spec=HermesArtifact)
    for k, v in defaults.items():
        setattr(art, k, v)
    return art


_ROLES = ["admin", "operator", "workspace_manager", "member", "viewer"]
_SCOPES = ["org", "workspace", "task_creator", "explicit"]


@pytest.mark.parametrize("role", _ROLES)
@pytest.mark.parametrize("scope", _SCOPES)
@pytest.mark.asyncio
async def test_can_view_artifact(role, scope):
    db = AsyncMock()
    artifact = _make_artifact(permission_scope=scope, created_by="user-a")

    with patch.object(PermissionChecker, "has_permission", return_value=True), \
         patch.object(PermissionChecker, "get_user_role", return_value=role), \
         patch.object(PermissionChecker, "_is_workspace_member", return_value=True), \
         patch.object(PermissionChecker, "_has_explicit_permission", return_value=True):
        result = await PermissionChecker.can_view_artifact(db, artifact, "user-a", "org-1")

    expected = True
    if scope == "workspace" and role not in ("admin", "operator"):
        pass
    if scope == "task_creator" and role not in ("admin", "operator"):
        expected = artifact.created_by == "user-a"
    if scope == "explicit" and role not in ("admin", "operator"):
        expected = True

    assert result == expected


@pytest.mark.asyncio
async def test_task_creator_only_creator_visible():
    db = AsyncMock()
    artifact = _make_artifact(permission_scope="task_creator", created_by="user-a")

    with patch.object(PermissionChecker, "has_permission", return_value=True), \
         patch.object(PermissionChecker, "get_user_role", return_value="member"):
        result = await PermissionChecker.can_view_artifact(db, artifact, "user-b", "org-1")
    assert result is False


@pytest.mark.asyncio
async def test_task_creator_admin_visible():
    db = AsyncMock()
    artifact = _make_artifact(permission_scope="task_creator", created_by="user-a")

    with patch.object(PermissionChecker, "has_permission", return_value=True), \
         patch.object(PermissionChecker, "get_user_role", return_value="admin"):
        result = await PermissionChecker.can_view_artifact(db, artifact, "user-b", "org-1")
    assert result is True


@pytest.mark.asyncio
async def test_workspace_scope_non_member_invisible():
    db = AsyncMock()
    artifact = _make_artifact(permission_scope="workspace", workspace_id="ws-1")

    with patch.object(PermissionChecker, "has_permission", return_value=True), \
         patch.object(PermissionChecker, "get_user_role", return_value="member"), \
         patch.object(PermissionChecker, "_is_workspace_member", return_value=False):
        result = await PermissionChecker.can_view_artifact(db, artifact, "user-b", "org-1")
    assert result is False


@pytest.mark.asyncio
async def test_workspace_scope_empty_workspace_id_invisible_for_member():
    db = AsyncMock()
    artifact = _make_artifact(permission_scope="workspace", workspace_id=None)

    with patch.object(PermissionChecker, "has_permission", return_value=True), \
         patch.object(PermissionChecker, "get_user_role", return_value="member"):
        result = await PermissionChecker.can_view_artifact(db, artifact, "user-b", "org-1")
    assert result is False


@pytest.mark.asyncio
async def test_workspace_scope_empty_workspace_id_visible_for_admin():
    db = AsyncMock()
    artifact = _make_artifact(permission_scope="workspace", workspace_id=None)

    with patch.object(PermissionChecker, "has_permission", return_value=True), \
         patch.object(PermissionChecker, "get_user_role", return_value="admin"):
        result = await PermissionChecker.can_view_artifact(db, artifact, "user-b", "org-1")
    assert result is True


@pytest.mark.asyncio
async def test_explicit_viewer_cannot_download():
    db = AsyncMock()
    artifact = _make_artifact(permission_scope="explicit")

    with patch.object(PermissionChecker, "can_view_artifact", return_value=True), \
         patch.object(PermissionChecker, "has_permission", return_value=True), \
         patch.object(PermissionChecker, "_has_explicit_permission", return_value=False):
        result = await PermissionChecker.can_download_artifact(db, artifact, "user-b", "org-1")
    assert result is False


@pytest.mark.asyncio
async def test_explicit_downloader_can_download():
    db = AsyncMock()
    artifact = _make_artifact(permission_scope="explicit")

    with patch.object(PermissionChecker, "can_view_artifact", return_value=True), \
         patch.object(PermissionChecker, "has_permission", return_value=True), \
         patch.object(PermissionChecker, "_has_explicit_permission", return_value=True):
        result = await PermissionChecker.can_download_artifact(db, artifact, "user-b", "org-1")
    assert result is True
