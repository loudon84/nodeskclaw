"""Job leasing v2 unit tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.models.ingestion_job import IngestionJob
from app.workers import job_leasing


def test_new_lease_token_unique():
    a = job_leasing.new_lease_token()
    b = job_leasing.new_lease_token()
    assert a != b
    assert len(a) == 32


def test_ownership_matches():
    job = SimpleNamespace(lease_owner="w1", lease_token="tok1")
    assert job_leasing.ownership_matches(job, lease_owner="w1", lease_token="tok1") is True
    assert job_leasing.ownership_matches(job, lease_owner="w1", lease_token="tok2") is False
    assert job_leasing.ownership_matches(job, lease_owner="w2", lease_token="tok1") is False


@pytest.mark.asyncio
async def test_heartbeat_commits_for_owner():
    db = AsyncMock()
    db.execute = AsyncMock(return_value=SimpleNamespace(rowcount=1))
    db.commit = AsyncMock()
    ok = await job_leasing.heartbeat(
        db,
        IngestionJob,
        job_id="j1",
        lease_owner="w1",
        lease_token="tok",
        lease_seconds=30,
    )
    assert ok is True
    db.commit.assert_awaited()
    db.execute.assert_awaited()


@pytest.mark.asyncio
async def test_commit_if_owner_rejects_stolen_lease():
    db = AsyncMock()
    db.execute = AsyncMock(return_value=SimpleNamespace(rowcount=0))
    db.commit = AsyncMock()
    ok = await job_leasing.commit_if_owner(
        db,
        IngestionJob,
        job_id="j1",
        lease_owner="w1",
        lease_token="old-token",
        values={"status": "active"},
    )
    assert ok is False
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_old_worker_cannot_overwrite_after_steal():
    db = AsyncMock()
    db.execute = AsyncMock(return_value=SimpleNamespace(rowcount=0))
    db.commit = AsyncMock()
    ok = await job_leasing.clear_lease_if_owner(
        db,
        IngestionJob,
        job_id="j1",
        lease_owner="worker-a",
        lease_token="token-a",
        values={"status": "active", "progress": 100},
    )
    assert ok is False


@pytest.mark.asyncio
async def test_claim_next_commits_before_io():
    job = SimpleNamespace(
        lease_owner=None,
        lease_token=None,
        lease_until=None,
        last_heartbeat_at=None,
    )

    class Result:
        def scalar_one_or_none(self):
            return job

    db = AsyncMock()
    db.execute = AsyncMock(return_value=Result())
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    with patch("app.workers.job_leasing.select") as select_mock:
        stmt = MagicStmt()
        select_mock.return_value = stmt
        claimed = await job_leasing.claim_next(
            db,
            IngestionJob,
            statuses=["pending"],
            lease_owner="w1",
            lease_seconds=30,
            commit=True,
        )
    assert claimed is not None
    claimed_job, token = claimed
    assert claimed_job is job
    assert job.lease_owner == "w1"
    assert job.lease_token == token
    assert token
    db.commit.assert_awaited()


class MagicStmt:
    def where(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def with_for_update(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self
