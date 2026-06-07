import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.hermes_skill.artifact_service import ArtifactService
from app.core.config import settings


@pytest.mark.asyncio
async def test_compute_outputs_dir_uses_tmp_fallback():
    db = AsyncMock()
    service = ArtifactService(db)

    task = MagicMock()
    task.id = "task-1"
    task.workspace_id = None
    task.agent_id = None

    ws_result = None
    db.get.return_value = ws_result

    with patch.object(settings, "HERMES_WORKSPACE_ROOT", ""):
        result = await service.compute_outputs_dir(task)
    assert "/tmp/nodeskclaw-workspaces/default" in str(result)
    assert "task-1" in str(result)
    assert "outputs" in str(result)


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
    assert "/data/workspaces" in str(result)
    assert "task-2" in str(result)


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
    assert "/mnt/ws2" in str(result)
    assert "task-3" in str(result)


@pytest.mark.asyncio
async def test_compute_outputs_dir_uses_instance_workspace_root_path():
    db = AsyncMock()
    service = ArtifactService(db)

    task = MagicMock()
    task.id = "task-4"
    task.workspace_id = None
    task.agent_id = "agent-1"

    ws_result = None

    instance = MagicMock()
    instance.deleted_at = None
    instance.advanced_config = {"workspace_root_path": "/opt/hermes/ws1"}

    def mock_get(model, id):
        if model.__name__ == "Workspace":
            return ws_result
        if model.__name__ == "Instance":
            return instance
        return None

    db.get.side_effect = mock_get

    result = await service.compute_outputs_dir(task)
    assert "/opt/hermes/ws1" in str(result)
    assert "task-4" in str(result)
