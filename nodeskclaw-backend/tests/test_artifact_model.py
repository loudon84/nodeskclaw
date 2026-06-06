import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.hermes_skill.hermes_artifact import HermesArtifact, PermissionScope


class TestPermissionScope:
    def test_scope_values(self):
        assert PermissionScope.ORG.value == "org"
        assert PermissionScope.WORKSPACE.value == "workspace"
        assert PermissionScope.TASK_CREATOR.value == "task_creator"
        assert PermissionScope.EXPLICIT.value == "explicit"

    def test_scope_count(self):
        assert len(PermissionScope) == 4


class TestHermesArtifactPermissionScope:
    def test_default_permission_scope(self):
        artifact = HermesArtifact(
            id="test-id",
            org_id="org-1",
            file_name="test.txt",
            file_path="/tmp/test.txt",
        )
        assert artifact.permission_scope == "workspace"

    def test_explicit_permission_scope(self):
        artifact = HermesArtifact(
            id="test-id",
            org_id="org-1",
            file_name="test.txt",
            file_path="/tmp/test.txt",
            permission_scope="org",
        )
        assert artifact.permission_scope == "org"
