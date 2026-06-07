import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from app.services.hermes_skill.artifact_service import ArtifactService
from app.services.hermes_skill.path_guard import PathGuard


@pytest.mark.asyncio
async def test_scan_and_register_empty_dir():
    db = AsyncMock()
    service = ArtifactService(db)

    task = MagicMock()
    task.id = "task-1"
    task.org_id = "org-1"
    task.deleted_at = None
    db.get.return_value = task

    mock_event_service = AsyncMock()
    with patch("app.services.hermes_skill.artifact_service.TaskEventService", return_value=mock_event_service), \
         patch.object(service, "compute_outputs_dir", return_value=Path("/nonexistent")):
        result = await service.scan_and_register("task-1", "org-1")
    assert result == []


def test_resolve_artifact_file_path():
    artifact = MagicMock()
    artifact.file_path = "/tmp/test/output.txt"
    result = ArtifactService.resolve_artifact_file_path(artifact)
    assert result == Path("/tmp/test/output.txt")


def test_resolve_artifact_file_path_empty():
    artifact = MagicMock()
    artifact.file_path = None
    result = ArtifactService.resolve_artifact_file_path(artifact)
    assert result is None


def test_validate_artifact_file_path_legal(tmp_path):
    from app.core.config import settings

    workspace_root = tmp_path / "ws"
    workspace_root.mkdir()
    outputs_dir = workspace_root / ".nodeskclaw" / "runs" / "task-1" / "outputs"
    outputs_dir.mkdir(parents=True)
    f = outputs_dir / "result.txt"
    f.write_text("ok")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(settings, "HERMES_OUTPUT_BASE_DIR_NAME", ".nodeskclaw")
        ArtifactService.validate_artifact_file_path(f, workspace_root, "task-1")


def test_guess_content_type():
    assert ArtifactService._guess_content_type(Path("report.pdf")) == "application/pdf"
    assert ArtifactService._guess_content_type(Path("data.json")) == "application/json"
    assert ArtifactService._guess_content_type(Path("image.png")) == "image/png"
    assert ArtifactService._guess_content_type(Path("file.xyz")) == "application/octet-stream"
