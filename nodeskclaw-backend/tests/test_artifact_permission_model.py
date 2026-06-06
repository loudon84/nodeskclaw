import pytest
from datetime import datetime, timezone

from app.models.hermes_skill.artifact_permission import ArtifactPermission


class TestArtifactPermission:
    def test_default_fields(self):
        perm = ArtifactPermission(
            id="test-id",
            artifact_id="artifact-1",
            org_id="org-1",
            user_id="user-1",
        )
        assert perm.permission_level == "viewer"
        assert perm.revoked_at is None

    def test_custom_permission_level(self):
        perm = ArtifactPermission(
            id="test-id",
            artifact_id="artifact-1",
            org_id="org-1",
            user_id="user-1",
            permission_level="editor",
        )
        assert perm.permission_level == "editor"

    def test_revoke_sets_timestamp(self):
        perm = ArtifactPermission(
            id="test-id",
            artifact_id="artifact-1",
            org_id="org-1",
            user_id="user-1",
        )
        now = datetime.now(timezone.utc)
        perm.revoked_at = now
        assert perm.revoked_at is not None
