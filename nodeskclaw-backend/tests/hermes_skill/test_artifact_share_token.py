import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta

from app.services.hermes_skill.download_token_service import DownloadTokenService
from app.models.hermes_skill.artifact_download_token import ArtifactDownloadToken
from app.core.exceptions import ArtifactTokenExpiredError


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
