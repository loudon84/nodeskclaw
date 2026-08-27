import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.hermes_skill.run_dispatch_outbox import RunDispatchOutbox, RunDispatchStatus
from app.services.hermes_skill.run_dispatch_outbox_service import RunDispatchOutboxService


@pytest.mark.asyncio
async def test_claim_pending_sets_delivering_and_lease():
    db = AsyncMock()
    now = datetime.now(timezone.utc)
    entry = RunDispatchOutbox(
        run_id="run-1",
        dispatch_id="disp-1",
        org_id="org-1",
        user_id="user-1",
        tool_name="test_tool",
        status=RunDispatchStatus.PENDING.value,
        payload={"run_id": "run-1"},
        command_digest="digest-1",
    )
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [entry]
    db.execute = AsyncMock(return_value=mock_result)
    db.flush = AsyncMock()

    service = RunDispatchOutboxService(db, dispatcher_id="disp-test-1")
    claimed = await service.claim_pending(batch_size=5)

    assert len(claimed) == 1
    assert claimed[0].status == RunDispatchStatus.DELIVERING.value
    assert claimed[0].dispatcher_id == "disp-test-1"
    assert claimed[0].lease_until is not None
    assert claimed[0].claimed_at is not None
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_deliver_entry_success_marks_delivered():
    db = AsyncMock()
    entry = RunDispatchOutbox(
        run_id="run-1",
        dispatch_id="disp-1",
        org_id="org-1",
        user_id="user-1",
        tool_name="test_tool",
        status=RunDispatchStatus.DELIVERING.value,
        payload={"run_id": "run-1"},
        command_digest="digest-1",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200

    service = RunDispatchOutboxService(db)
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
        ok = await service.deliver_entry(entry)

    assert ok is True
    assert entry.status == RunDispatchStatus.DELIVERED.value
    assert entry.delivered_at is not None
    assert entry.lease_until is None
    assert entry.last_error is None


@pytest.mark.asyncio
async def test_deliver_entry_failure_retries_and_dead_letters():
    db = AsyncMock()
    entry = RunDispatchOutbox(
        run_id="run-1",
        dispatch_id="disp-1",
        org_id="org-1",
        user_id="user-1",
        tool_name="test_tool",
        status=RunDispatchStatus.DELIVERING.value,
        payload={"run_id": "run-1"},
        command_digest="digest-1",
        retry_count=4,
        max_retries=5,
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "internal agent error"

    service = RunDispatchOutboxService(db)
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
        ok = await service.deliver_entry(entry)

    assert ok is False
    assert entry.status == RunDispatchStatus.DEAD_LETTER.value
    assert entry.retry_count == 5
    assert "HTTP 500" in entry.last_error


@pytest.mark.asyncio
async def test_deliver_entry_422_400_dead_letters_immediately():
    db = AsyncMock()
    entry = RunDispatchOutbox(
        run_id="run-1",
        dispatch_id="disp-1",
        org_id="org-1",
        user_id="user-1",
        tool_name="test_tool",
        status=RunDispatchStatus.DELIVERING.value,
        payload={"run_id": "run-1"},
        command_digest="digest-1",
        retry_count=0,
        max_retries=5,
    )

    # 422 Unprocessable Entity (e.g. missing header, validation failure)
    mock_resp = MagicMock()
    mock_resp.status_code = 422
    mock_resp.text = "missing execution context header"

    service = RunDispatchOutboxService(db)
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)):
        ok = await service.deliver_entry(entry)

    assert ok is False
    # Immediately dead letter without waiting for 5 retries
    assert entry.status == RunDispatchStatus.DEAD_LETTER.value
    assert entry.retry_count == 1
    assert entry.next_retry_at is None
    assert "HTTP 422" in entry.last_error
