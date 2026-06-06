import pytest
from datetime import datetime, timezone, timedelta

from app.models.hermes_skill.artifact_download_token import ArtifactDownloadToken


class TestArtifactDownloadToken:
    def test_default_fields(self):
        token = ArtifactDownloadToken(
            id="test-id",
            artifact_id="artifact-1",
            org_id="org-1",
            token="abc123",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        assert token.max_uses == 1
        assert token.uses_remaining == 1
        assert token.is_active is True

    def test_custom_max_uses(self):
        token = ArtifactDownloadToken(
            id="test-id",
            artifact_id="artifact-1",
            org_id="org-1",
            token="abc123",
            max_uses=10,
            uses_remaining=10,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        assert token.max_uses == 10
        assert token.uses_remaining == 10
