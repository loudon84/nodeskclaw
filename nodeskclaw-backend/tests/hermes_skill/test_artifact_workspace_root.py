import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.hermes_skill.artifact_service import ArtifactService
from app.core.config import settings


def _path_contains(path: Path, segment: str) -> bool:
    return segment in path.as_posix()


@pytest.mark.asyncio
async def test_compute_outputs_dir_uses_tmp_fallback():
    db = AsyncMock()
    service = ArtifactService(db)

    task = MagicMock()
    task.id = "task-1"
    task.workspace_id = None
    task.agent_id = None

    db.get.return_value = None

    with patch.object(settings, "HERMES_WORKSPACE_ROOT", ""):
        result = await service.compute_outputs_dir(task)

    assert result.name == "outputs"
    assert _path_contains(result, "nodeskclaw-workspaces/default")
    assert _path_contains(result, "runs/task-1")


@pytest.mark.asyncio
async def test_compute_outputs_dir_uses_settings_root():
    db = AsyncMock()
    service = ArtifactService(db)

    task = MagicMock()
    task.id = "task-2"
    task.workspace_id = "ws-1"
    task.agent_id = None

    ws = MagicMock()
    ws.deleted_at = None
    ws.storage_root = None
    ws.root_path = None
    ws.local_root_path = None
    db.get.return_value = ws

    with patch.object(settings, "HERMES_WORKSPACE_ROOT", "/data/workspaces"):
        result = await service.compute_outputs_dir(task)
    assert _path_contains(result, "data/workspaces")
    assert _path_contains(result, "task-2")


@pytest.mark.asyncio
async def test_compute_outputs_dir_uses_workspace_storage_root():
    db = AsyncMock()
    service = ArtifactService(db)

    task = MagicMock()
    task.id = "task-3"
    task.workspace_id = "ws-2"
    task.agent_id = None

    ws = MagicMock()
    ws.deleted_at = None
    ws.storage_root = "/mnt/ws2"
    ws.root_path = None
    ws.local_root_path = None
    db.get.return_value = ws

    result = await service.compute_outputs_dir(task)
    assert _path_contains(result, "mnt/ws2")
    assert _path_contains(result, "task-3")


@pytest.mark.asyncio
async def test_compute_outputs_dir_uses_instance_workspace_root_path():
    db = AsyncMock()
    service = ArtifactService(db)

    task = MagicMock()
    task.id = "task-4"
    task.workspace_id = None
    task.agent_id = "agent-1"

    instance = MagicMock()
    instance.deleted_at = None
    instance.advanced_config = {"workspace_root_path": "/opt/hermes/ws1"}

    def mock_get(model, id):
        if model.__name__ == "Workspace":
            return None
        if model.__name__ == "Instance":
            return instance
        return None

    db.get.side_effect = mock_get

    result = await service.compute_outputs_dir(task)
    assert _path_contains(result, "opt/hermes/ws1")
    assert _path_contains(result, "task-4")
