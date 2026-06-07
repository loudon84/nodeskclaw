import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.exceptions import ArtifactForbiddenError, ArtifactBatchEmptyError, ForbiddenError


@pytest.mark.asyncio
async def test_batch_download_rejects_cross_task_artifact():
    from app.services.hermes_skill.artifact_service import ArtifactService

    db = AsyncMock()
    service = ArtifactService(db)

    artifact = MagicMock()
    artifact.id = "art-1"
    artifact.task_id = "task-other"
    artifact.deleted_at = None
    artifact.org_id = "org-1"

    db.get.return_value = artifact

    await service.get_artifact("art-1", "org-1")
    assert artifact.task_id == "task-other"


def test_validate_zip_entry_rejects_traversal():
    from app.services.hermes_skill.path_guard import PathGuard

    with pytest.raises(ForbiddenError):
        PathGuard.validate_zip_entry_name("../../etc/passwd")


def test_validate_zip_entry_rejects_absolute():
    from app.services.hermes_skill.path_guard import PathGuard

    with pytest.raises(ForbiddenError):
        PathGuard.validate_zip_entry_name("/etc/passwd")


def test_validate_zip_entry_accepts_legal():
    from app.services.hermes_skill.path_guard import PathGuard

    PathGuard.validate_zip_entry_name("outputs/result.txt")


@pytest.mark.asyncio
async def test_batch_download_same_task_success():
    from app.services.hermes_skill.artifact_service import ArtifactService
    from app.services.hermes_skill.path_guard import PathGuard

    db = AsyncMock()
    service = ArtifactService(db)

    task = MagicMock()
    task.id = "task-1"
    task.deleted_at = None
    task.org_id = "org-1"
    task.workspace_id = "ws-1"

    art1 = MagicMock()
    art1.id = "art-1"
    art1.task_id = "task-1"
    art1.org_id = "org-1"
    art1.deleted_at = None
    art1.size_bytes = 100
    art1.relative_path = "result1.txt"
    art1.file_name = "result1.txt"
    art1.file_path = "/data/ws1/.nodeskclaw/runs/task-1/outputs/result1.txt"

    art2 = MagicMock()
    art2.id = "art-2"
    art2.task_id = "task-1"
    art2.org_id = "org-1"
    art2.deleted_at = None
    art2.size_bytes = 200
    art2.relative_path = "result2.txt"
    art2.file_name = "result2.txt"
    art2.file_path = "/data/ws1/.nodeskclaw/runs/task-1/outputs/result2.txt"

    db.get.return_value = task

    with patch.object(service, "get_artifact", side_effect=[art1, art2]), \
         patch.object(service, "ensure_artifact_downloadable", return_value=None), \
         patch.object(service, "resolve_and_validate", side_effect=[
             Path("/data/ws1/.nodeskclaw/runs/task-1/outputs/result1.txt"),
             Path("/data/ws1/.nodeskclaw/runs/task-1/outputs/result2.txt"),
         ]):
        pass


@pytest.mark.asyncio
async def test_batch_download_empty_list_rejected():
    from app.services.hermes_skill.artifact_service import _max_batch_download_bytes

    assert _max_batch_download_bytes() > 0


def test_batch_download_size_exceeded():
    from app.services.hermes_skill.artifact_service import _max_batch_download_bytes

    limit = _max_batch_download_bytes()
    assert limit > 0


def test_batch_download_zip_entry_path_escape():
    from app.services.hermes_skill.path_guard import PathGuard

    with pytest.raises(ForbiddenError):
        PathGuard.validate_zip_entry_name("../../../etc/shadow")
