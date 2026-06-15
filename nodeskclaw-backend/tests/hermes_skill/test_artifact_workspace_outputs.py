import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.hermes_skill.artifact_service import ArtifactService
from app.core.config import settings


@pytest.mark.asyncio
async def test_outputs_dir_under_workspace_root():
    db = AsyncMock()
    service = ArtifactService(db)

    task = MagicMock()
    task.id = "task-outputs-1"
    task.workspace_id = None
    task.agent_id = None

    db.get.return_value = None

    with patch.object(settings, "HERMES_WORKSPACE_ROOT", "/data/workspaces"):
        result = await service.compute_outputs_dir(task)

    assert result.name == "outputs"
    assert result.parent.name == "task-outputs-1"
    assert settings.HERMES_OUTPUT_BASE_DIR_NAME in result.as_posix()
