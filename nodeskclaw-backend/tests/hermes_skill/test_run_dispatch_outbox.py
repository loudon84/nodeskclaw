"""Unit tests for RunDispatchOutboxService and lease generation fencing."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.hermes_skill.run_dispatch_outbox import RunDispatchOutbox, RunDispatchStatus
from app.services.hermes_skill.run_dispatch_outbox_service import RunDispatchOutboxService


def _make_entry(**kwargs):
    now = datetime.now(timezone.utc)
    defaults = {
        "id": "outbox-1",
        "run_id": "run-1",
        "dispatch_id": "disp-1",
        "org_id": "org-1",
        "user_id": "user-1",
        "tool_name": "test_tool",
        "status": RunDispatchStatus.PENDING.value,
        "payload": {"prompt": "hello"},
        "command_digest": "digest-1",
        "retry_count": 0,
        "max_retries": 5,
        "lease_generation": 0,
        "lease_until": None,
        "claimed_at": None,
        "dispatcher_id": None,
        "next_retry_at": None,
        "last_error": None,
    }
    defaults.update(kwargs)
    entry = RunDispatchOutbox()
    for k, v in defaults.items():
        setattr(entry, k, v)
    return entry


@pytest.mark.asyncio
async def test_claim_pending_increments_lease_generation():
    db = AsyncMock()
    entry = _make_entry(lease_generation=1)
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [entry]
    mock_res = MagicMock()
    mock_res.scalars.return_value = mock_scalars
    db.execute = AsyncMock(return_value=mock_res)

    service = RunDispatchOutboxService(db, dispatcher_id="disp-test")
    claimed = await service.claim_pending(batch_size=10)

    assert len(claimed) == 1
    assert claimed[0].status == RunDispatchStatus.DELIVERING.value
    assert claimed[0].dispatcher_id == "disp-test"
    assert claimed[0].lease_generation == 2
    assert claimed[0].lease_until is not None
    assert db.flush.called


@pytest.mark.asyncio
async def test_deliver_entry_success_with_matching_generation():
    db = AsyncMock()
    entry = _make_entry(
        status=RunDispatchStatus.DELIVERING.value,
        lease_generation=2,
        lease_until=datetime.now(timezone.utc) + timedelta(seconds=60),
    )

    service = RunDispatchOutboxService(db, dispatcher_id="disp-test")
    mock_resp = MagicMock(status_code=200)

    with patch("httpx.AsyncClient.post", AsyncMock(return_value=mock_resp)):
        ok = await service.deliver_entry(entry, expected_generation=2)

    assert ok is True
    assert entry.status == RunDispatchStatus.DELIVERED.value
    assert entry.delivered_at is not None
    assert entry.lease_until is None


@pytest.mark.asyncio
async def test_deliver_entry_ignores_stale_generation():
    db = AsyncMock()
    entry = _make_entry(
        status=RunDispatchStatus.DELIVERING.value,
        lease_generation=3,  # Changed by concurrent claim
        lease_until=datetime.now(timezone.utc) + timedelta(seconds=60),
    )

    service = RunDispatchOutboxService(db, dispatcher_id="disp-test")
    mock_resp = MagicMock(status_code=200)

    with patch("httpx.AsyncClient.post", AsyncMock(return_value=mock_resp)):
        ok = await service.deliver_entry(entry, expected_generation=2)

    assert ok is False
    # Status should not be changed to DELIVERED
    assert entry.status == RunDispatchStatus.DELIVERING.value


@pytest.mark.asyncio
async def test_deliver_entry_permanent_4xx_dead_letters_immediately():
    db = AsyncMock()
    entry = _make_entry(
        status=RunDispatchStatus.DELIVERING.value,
        lease_generation=1,
        lease_until=datetime.now(timezone.utc) + timedelta(seconds=60),
        retry_count=0,
    )

    service = RunDispatchOutboxService(db, dispatcher_id="disp-test")
    mock_resp = MagicMock(status_code=400, text="Bad Request: schema mismatch")

    with patch("httpx.AsyncClient.post", AsyncMock(return_value=mock_resp)):
        ok = await service.deliver_entry(entry, expected_generation=1)

    assert ok is False
    assert entry.status == RunDispatchStatus.DEAD_LETTER.value
    assert entry.retry_count == 1
    assert "HTTP 400" in (entry.last_error or "")


@pytest.mark.asyncio
async def test_replay_dead_letter():
    db = AsyncMock()
    entry = _make_entry(
        status=RunDispatchStatus.DEAD_LETTER.value,
        retry_count=5,
        last_error="Max retries exceeded",
        lease_generation=2,
    )
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = entry
    db.execute = AsyncMock(return_value=mock_res)

    service = RunDispatchOutboxService(db)
    replayed = await service.replay_dead_letter("org-1", "disp-1")

    assert replayed.status == RunDispatchStatus.PENDING.value
    assert replayed.retry_count == 0
    assert replayed.last_error is None
    assert replayed.lease_generation == 3
    assert db.flush.called


@pytest.mark.asyncio
async def test_get_outbox_stats():
    db = AsyncMock()
    mock_res = MagicMock()
    mock_res.all.return_value = [("pending", 3), ("delivering", 1), ("dead_letter", 2)]
    db.execute = AsyncMock(return_value=mock_res)

    service = RunDispatchOutboxService(db)
    stats = await service.get_outbox_stats("org-1")

    assert stats["pending"] == 3
    assert stats["delivering"] == 1
    assert stats["dead_letter"] == 2
    assert stats["delivered"] == 0

