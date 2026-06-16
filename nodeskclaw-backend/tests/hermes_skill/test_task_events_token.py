import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.hermes_skill.task_event_token_service import TaskEventTokenService


@pytest.mark.asyncio
async def test_create_token_returns_event_url():
    db = AsyncMock()
    task = MagicMock(id="task-1", org_id="org-1")
    svc = TaskEventTokenService(db)
    with patch.object(svc, "_get_task", AsyncMock(return_value=task)):
        data = await svc.create_token("task-1", "user-1", "org-1", ttl_seconds=300)
    assert data["expires_in"] == 300
    assert "/api/v1/hermes/tasks/task-1/events?token=" in data["event_url"]
    db.add.assert_called_once()


@pytest.mark.asyncio
async def test_verify_token_valid():
    db = AsyncMock()
    svc = TaskEventTokenService(db)
    raw = "sse_testtoken"
    token_hash = svc._hash_token(raw)
    record = MagicMock(
        user_id="user-1",
        org_id="org-1",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        used_count=0,
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = record
    db.execute = AsyncMock(return_value=mock_result)
    valid, user_id, org_id = await svc.verify_token(raw, "task-1")
    assert valid is True
    assert user_id == "user-1"
    assert org_id == "org-1"


@pytest.mark.asyncio
async def test_verify_token_expired():
    db = AsyncMock()
    svc = TaskEventTokenService(db)
    record = MagicMock(
        user_id="user-1",
        org_id="org-1",
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = record
    db.execute = AsyncMock(return_value=mock_result)
    valid, user_id, org_id = await svc.verify_token("sse_expired", "task-1")
    assert valid is False
    assert user_id is None
    assert org_id is None
