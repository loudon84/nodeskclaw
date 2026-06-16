import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.hermes_skill.hermes_task import TaskStatus
from app.services.hermes_skill.task_result_service import TaskResultService


def _artifact(artifact_id: str, file_name: str, artifact_type: str | None = None, size_bytes: int = 100, primary: bool = False):
    art = MagicMock()
    art.id = artifact_id
    art.file_name = file_name
    art.title = file_name
    art.artifact_type = artifact_type
    art.content_type = "text/markdown" if artifact_type == "markdown" else "text/plain"
    art.size_bytes = size_bytes
    art.metadata_json = {"primary": True} if primary else {}
    return art


@pytest.mark.asyncio
async def test_select_primary_by_manifest_flag():
    db = AsyncMock()
    svc = TaskResultService(db)
    artifacts = [
        _artifact("a1", "notes.txt", "text", 50),
        _artifact("a2", "article.md", "markdown", 200, primary=True),
    ]
    primary = svc._select_primary_artifact(artifacts, None)
    assert primary.id == "a2"


@pytest.mark.asyncio
async def test_select_primary_by_policy_filename():
    db = AsyncMock()
    svc = TaskResultService(db)
    artifacts = [
        _artifact("a1", "draft.txt", "text", 500),
        _artifact("a2", "article.md", "markdown", 100),
    ]
    policy = {"artifact_type": "markdown", "prefer_file_name": "article.md"}
    primary = svc._select_primary_artifact(artifacts, policy)
    assert primary.file_name == "article.md"


@pytest.mark.asyncio
async def test_get_result_includes_task_and_primary_artifact():
    db = AsyncMock()
    svc = TaskResultService(db)
    task = MagicMock()
    task.id = "task-1"
    task.task_no = "TASK-0001"
    task.status = TaskStatus.COMPLETED
    task.tool_name = "writer_article_generate"
    task.agent_id = "agent-1"
    task.profile_id = "writer"
    task.workspace_id = "ws-1"
    task.routing_metadata = {"agent_alias": "common-writer"}
    task.result_summary = "done"
    task.created_at = None
    task.completed_at = None
    task.skill_id = "writer.article"
    task.org_id = "org-1"

    artifact = _artifact("art-1", "article.md", "markdown", 300)

    with patch.object(svc, "_get_task", AsyncMock(return_value=task)):
        with patch.object(svc, "_list_task_artifacts", AsyncMock(return_value=[artifact])):
            with patch.object(svc, "_get_skill", AsyncMock(return_value=None)):
                with patch.object(svc, "_build_timeline", AsyncMock(return_value=[])):
                    result = await svc.get_result("task-1", "org-1")
    assert result["task"]["agent_alias"] == "common-writer"
    assert result["primary_artifact"]["file_name"] == "article.md"
    assert result["result_summary"] == "done"
