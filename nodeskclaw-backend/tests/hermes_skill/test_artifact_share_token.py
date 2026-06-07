import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta

from app.services.hermes_skill.download_token_service import DownloadTokenService
from app.services.hermes_skill.artifact_service import ArtifactService
from app.models.hermes_skill.artifact_download_token import ArtifactDownloadToken
from app.models.hermes_skill.hermes_artifact import HermesArtifact
from app.models.hermes_skill.hermes_task import HermesTask
from app.core.exceptions import (
    ArtifactTokenExpiredError,
    ArtifactNotFoundError,
    ArtifactFileNotFoundError,
    ForbiddenError,
    ArtifactWorkspaceRootUnresolvedError,
)


def _make_token(**overrides) -> ArtifactDownloadToken:
    defaults = {
        "id": "token-1",
        "artifact_id": "art-1",
        "org_id": "org-1",
        "token": "test-token-abc",
        "created_by": "user-a",
        "max_uses": 1,
        "uses_remaining": 1,
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        "is_active": True,
        "deleted_at": None,
    }
    defaults.update(overrides)
    tok = MagicMock(spec=ArtifactDownloadToken)
    for k, v in defaults.items():
        setattr(tok, k, v)
    return tok


@pytest.mark.asyncio
async def test_get_valid_token_success():
    db = AsyncMock()
    token_record = _make_token()
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = token_record
    db.execute.return_value = mock_result

    service = DownloadTokenService(db)
    result = await service.get_valid_token("test-token-abc")
    assert result.id == "token-1"


@pytest.mark.asyncio
async def test_get_valid_token_expired():
    db = AsyncMock()
    token_record = _make_token(expires_at=datetime.now(timezone.utc) - timedelta(hours=1))
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = token_record
    db.execute.return_value = mock_result

    service = DownloadTokenService(db)
    with pytest.raises(ArtifactTokenExpiredError):
        await service.get_valid_token("test-token-abc")


@pytest.mark.asyncio
async def test_get_valid_token_exhausted():
    db = AsyncMock()
    token_record = _make_token(uses_remaining=0)
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = token_record
    db.execute.return_value = mock_result

    service = DownloadTokenService(db)
    with pytest.raises(ArtifactTokenExpiredError):
        await service.get_valid_token("test-token-abc")


@pytest.mark.asyncio
async def test_get_valid_token_not_found():
    db = AsyncMock()
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = None
    db.execute.return_value = mock_result

    service = DownloadTokenService(db)
    with pytest.raises(ArtifactTokenExpiredError):
        await service.get_valid_token("nonexistent")


@pytest.mark.asyncio
async def test_consume_token_reduces_remaining():
    db = AsyncMock()
    token_record = _make_token(uses_remaining=2)
    locked = _make_token(uses_remaining=2)
    mock_result = AsyncMock()
    mock_result.scalar_one.return_value = locked
    db.execute.return_value = mock_result

    service = DownloadTokenService(db)
    await service.consume_token(token_record)
    assert locked.uses_remaining == 1
    assert locked.is_active is True


@pytest.mark.asyncio
async def test_consume_token_deactivates_when_zero():
    db = AsyncMock()
    token_record = _make_token(uses_remaining=1)
    locked = _make_token(uses_remaining=1)
    mock_result = AsyncMock()
    mock_result.scalar_one.return_value = locked
    db.execute.return_value = mock_result

    service = DownloadTokenService(db)
    await service.consume_token(token_record)
    assert locked.uses_remaining == 0
    assert locked.is_active is False


def _make_artifact(**overrides):
    defaults = {
        "id": "art-1",
        "org_id": "org-1",
        "task_id": "task-1",
        "workspace_id": "ws-1",
        "file_name": "result.txt",
        "file_path": "/data/ws1/.nodeskclaw/runs/task-1/outputs/result.txt",
        "deleted_at": None,
    }
    defaults.update(overrides)
    art = MagicMock(spec=HermesArtifact)
    for k, v in defaults.items():
        setattr(art, k, v)
    return art


def _make_task(**overrides):
    defaults = {
        "id": "task-1",
        "org_id": "org-1",
        "workspace_id": "ws-1",
        "agent_id": "agent-1",
        "deleted_at": None,
    }
    defaults.update(overrides)
    task = MagicMock(spec=HermesTask)
    for k, v in defaults.items():
        setattr(task, k, v)
    return task


@pytest.mark.asyncio
async def test_share_token_file_not_found_no_consume():
    db = AsyncMock()
    token_record = _make_token(uses_remaining=1)

    artifact = _make_artifact()
    task = _make_task()

    def mock_get(model, pk):
        if model is HermesArtifact:
            return artifact
        if model is HermesTask:
            return task
        return None

    db.get.side_effect = mock_get

    service = ArtifactService(db)
    with patch.object(service, "_resolve_workspace_root_for_task", return_value=Path("/data/ws1")):
        file_path = await service.resolve_and_validate(artifact, task)

    assert not file_path.is_file()
    assert token_record.uses_remaining == 1


@pytest.mark.asyncio
async def test_share_token_path_guard_fail_no_consume():
    db = AsyncMock()
    token_record = _make_token(uses_remaining=1)

    artifact = _make_artifact(file_path="/etc/passwd")
    task = _make_task()

    def mock_get(model, pk):
        if model is HermesArtifact:
            return artifact
        if model is HermesTask:
            return task
        return None

    db.get.side_effect = mock_get

    service = ArtifactService(db)
    with patch.object(service, "_resolve_workspace_root_for_task", return_value=Path("/data/ws1")):
        with pytest.raises(ForbiddenError):
            await service.resolve_and_validate(artifact, task)

    assert token_record.uses_remaining == 1


@pytest.mark.asyncio
async def test_share_token_artifact_deleted_no_consume():
    db = AsyncMock()
    token_record = _make_token(uses_remaining=1)

    artifact = _make_artifact(deleted_at=datetime.now(timezone.utc))

    db.get.return_value = artifact

    service = ArtifactService(db)
    with pytest.raises(ArtifactNotFoundError):
        await service.get_artifact("art-1", "org-1")

    assert token_record.uses_remaining == 1


@pytest.mark.asyncio
async def test_share_token_success_consume():
    db = AsyncMock()
    token_record = _make_token(uses_remaining=2)
    locked = _make_token(uses_remaining=2)
    mock_result = AsyncMock()
    mock_result.scalar_one.return_value = locked
    db.execute.return_value = mock_result

    service = DownloadTokenService(db)
    await service.consume_token(token_record)
    assert locked.uses_remaining == 1


@pytest.mark.asyncio
async def test_share_token_success_audit_logged():
    db = AsyncMock()
    token_record = _make_token(uses_remaining=1)

    from app.services.hermes_skill.artifact_audit_service import ArtifactAuditService

    audit = ArtifactAuditService(db)
    with patch.object(audit, "log_artifact_action", return_value=None) as mock_log:
        await audit.log_artifact_action(
            action="artifact.downloaded_by_token",
            artifact_id="art-1",
            org_id="org-1",
            details={"token_id": token_record.id, "uses_remaining": 0},
        )
    mock_log.assert_called_once()
