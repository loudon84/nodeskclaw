import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.exceptions import ArtifactForbiddenError, ArtifactBatchEmptyError


@pytest.mark.asyncio
async def test_batch_download_rejects_cross_task_artifact():
    from app.services.hermes_skill.artifact_service import ArtifactService

    db = AsyncMock()
    service = ArtifactService(db)

    artifact = MagicMock()
    artifact.task_id = "task-other"
    artifact.deleted_at = None
    artifact.org_id = "org-1"

    db.get.return_value = artifact

    with pytest.raises(ArtifactForbiddenError):
        service.get_artifact("art-1", "org-1")


def test_validate_zip_entry_rejects_traversal():
    from app.services.hermes_skill.path_guard import PathGuard
    from app.core.exceptions import ForbiddenError

    with pytest.raises(ForbiddenError):
        PathGuard.validate_zip_entry_name("../../etc/passwd")


def test_validate_zip_entry_rejects_absolute():
    from app.services.hermes_skill.path_guard import PathGuard
    from app.core.exceptions import ForbiddenError

    with pytest.raises(ForbiddenError):
        PathGuard.validate_zip_entry_name("/etc/passwd")


def test_validate_zip_entry_accepts_legal():
    from app.services.hermes_skill.path_guard import PathGuard

    PathGuard.validate_zip_entry_name("outputs/result.txt")
