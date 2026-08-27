"""Job leasing v2 unit tests."""

import asyncio
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


@pytest.mark.asyncio
async def test_build_worker_claims_only_build_jobs():
    with patch(
        "app.workers.build_worker.build_orchestrator.claim_next_build_job",
        AsyncMock(return_value=None),
    ) as claim:
        with patch("app.workers.build_worker.settings.KNOWLEDGE_V2_BUILD_ENABLED", True):
            from app.workers import build_worker

            task = asyncio.create_task(build_worker._run_loop())
            await asyncio.sleep(0.05)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
    claim.assert_awaited()


def test_worker_modules_expose_domain_entrypoints():
    from app.workers import build_worker, ingestion_worker, maintenance_worker, translation_worker

    assert callable(build_worker.main)
    assert callable(ingestion_worker.main)
    assert callable(translation_worker.main)
    assert callable(maintenance_worker.main)


@pytest.mark.asyncio
async def test_ingestion_worker_only_claims_ingestion_jobs():
    with patch("app.workers.ingestion_worker.ingestion_service.claim_next_job", AsyncMock(return_value=None)) as claim:
        with patch("app.workers.ingestion_worker.RagflowRuntimeAdapter") as ragflow_cls:
            ragflow_cls.return_value.aclose = AsyncMock()
            from app.workers import ingestion_worker

            task = asyncio.create_task(ingestion_worker._run_loop())
            await asyncio.sleep(0.05)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
    claim.assert_awaited()


@pytest.mark.asyncio
async def test_translation_worker_only_claims_translation_jobs():
    with patch(
        "app.workers.translation_worker.translation_service.claim_next_translation_job",
        AsyncMock(return_value=None),
    ) as claim:
        from app.workers import translation_worker

        with patch.object(translation_worker.settings, "KNOWLEDGE_TRANSLATION_ENABLED", True):
            task = asyncio.create_task(translation_worker._run_loop())
            await asyncio.sleep(0.05)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
    claim.assert_awaited()

