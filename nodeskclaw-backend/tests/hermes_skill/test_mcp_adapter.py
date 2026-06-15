import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.hermes_skill.hermes_agent_adapter import HermesAgentAdapter
from app.core.config import settings


@pytest.mark.asyncio
async def test_compute_output_dir_relative():
    db = AsyncMock()
    adapter = HermesAgentAdapter(db)

    task = MagicMock()
    task.id = "task-1"

    instance = MagicMock()
    instance.advanced_config = {"output_dir_mode": "relative"}

    with patch.object(adapter, "_get_instance", new_callable=AsyncMock, return_value=instance):
        result = await adapter.compute_output_dir_for_task(task)
    assert result.startswith(".nodeskclaw")
    assert "task-1" in result
    assert result.endswith("outputs")


@pytest.mark.asyncio
async def test_compute_output_dir_absolute():
    db = AsyncMock()
    adapter = HermesAgentAdapter(db)

    task = MagicMock()
    task.id = "task-2"
    task.workspace_id = "ws-1"
    task.agent_id = "agent-1"

    instance = MagicMock()
    instance.advanced_config = {"output_dir_mode": "absolute"}

    with patch.object(adapter, "_get_instance", new_callable=AsyncMock, return_value=instance), \
         patch("app.services.hermes_skill.artifact_service.ArtifactService") as mock_artifact_svc:
        mock_svc_instance = AsyncMock()
        mock_svc_instance.compute_outputs_dir.return_value = __import__("pathlib").Path("/data/ws1/.nodeskclaw/runs/task-2/outputs")
        mock_artifact_svc.return_value = mock_svc_instance

        result = await adapter.compute_output_dir_for_task(task)
    assert "data/ws1" in result.replace("\\", "/")
    assert "task-2" in result


@pytest.mark.asyncio
async def test_get_run_status():
    db = AsyncMock()
    adapter = HermesAgentAdapter(db)

    task = MagicMock()
    task.hermes_run_id = "run-1"

    with patch.object(adapter, "get_run", new_callable=AsyncMock, return_value={"status": "completed"}):
        result = await adapter.get_run_status(task)
    assert result["status"] == "completed"
