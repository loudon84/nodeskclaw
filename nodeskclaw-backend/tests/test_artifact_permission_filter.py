import pytest
from app.services.hermes_skill.permission_checker import _ROLE_PERMISSIONS


class TestArtifactPermissions:
    def test_admin_has_delete_permission(self):
        assert "hermes_artifact:delete" in _ROLE_PERMISSIONS["admin"]

    def test_admin_has_share_permission(self):
        assert "hermes_artifact:share" in _ROLE_PERMISSIONS["admin"]

    def test_admin_has_manage_permission(self):
        assert "hermes_artifact:manage_permission" in _ROLE_PERMISSIONS["admin"]

    def test_operator_has_delete_permission(self):
        assert "hermes_artifact:delete" in _ROLE_PERMISSIONS["operator"]

    def test_operator_has_share_permission(self):
        assert "hermes_artifact:share" in _ROLE_PERMISSIONS["operator"]

    def test_operator_no_manage_permission(self):
        assert "hermes_artifact:manage_permission" not in _ROLE_PERMISSIONS["operator"]

    def test_workspace_manager_has_share_permission(self):
        assert "hermes_artifact:share" in _ROLE_PERMISSIONS["workspace_manager"]

    def test_workspace_manager_no_delete_permission(self):
        assert "hermes_artifact:delete" not in _ROLE_PERMISSIONS["workspace_manager"]

    def test_member_no_share_permission(self):
        assert "hermes_artifact:share" not in _ROLE_PERMISSIONS["member"]

    def test_member_no_delete_permission(self):
        assert "hermes_artifact:delete" not in _ROLE_PERMISSIONS["member"]

    def test_viewer_no_download_permission(self):
        assert "hermes_artifact:download" not in _ROLE_PERMISSIONS["viewer"]

    def test_viewer_has_view_permission(self):
        assert "hermes_artifact:view" in _ROLE_PERMISSIONS["viewer"]
