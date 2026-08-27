"""Connector sync worker: schedule, claim SyncRun with leasing v2, heartbeat."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import socket
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text as sql_text

from app.core.deps import async_session_factory
from app.integrations.ragflow.client import RagflowClient
from app.models.base import not_deleted
from app.models.connector import ConnectorSyncItem, ConnectorSyncRun, KnowledgeSourceConnector
from app.models.enums import ConnectorSyncItemStatus, ConnectorSyncRunStatus, IngestionJobStatus
from app.models.ingestion_job import IngestionJob
from app.services import connector_service, connector_sync_service, metrics_service
from app.workers import job_leasing

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 3.0
LEASE_SECONDS = 60
WAITING_INGESTION_RETRY_SECONDS = 5
SCHEDULE_EVERY_LOOPS = 5


class LeaseLostError(RuntimeError):
    """Raised when heartbeat ownership check fails mid-sync."""


def _lease_owner() -> str:
    return f"connector:{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"


def _now() -> datetime:
    return datetime.now(UTC)


async def claim_next_sync_run(db, *, lease_owner: str):
    return await job_leasing.claim_next(
        db,
        ConnectorSyncRun,
        statuses=[
            ConnectorSyncRunStatus.pending.value,
            ConnectorSyncRunStatus.waiting_ingestion.value,
        ],
        lease_owner=lease_owner,
        lease_seconds=LEASE_SECONDS,
        order_by=(ConnectorSyncRun.next_run_at.asc().nullsfirst(), ConnectorSyncRun.created_at.asc()),
        commit=True,
    )


async def finalize_leased_sync_run(
    db,
    run: ConnectorSyncRun,
    *,
    lease_owner: str,
    lease_token: str,
    clear_lease: bool = True,
) -> bool:
    """Commit SyncRun session mutations only when lease ownership still holds."""
    result = await db.execute(
        sql_text(
            """
            UPDATE knowledge_connector_sync_runs
            SET last_heartbeat_at = NOW()
            WHERE id = :id
              AND lease_owner = :owner
              AND lease_token = :token
              AND deleted_at IS NULL
            """
        ),
        {"id": run.id, "owner": lease_owner, "token": lease_token},
    )
    if result.rowcount == 0:
        await db.rollback()
        return False
    if clear_lease:
        run.lease_owner = None
        run.lease_token = None
        run.lease_until = None
    await db.commit()
    return True


async def process_sync_run(
    db,
    ragflow: RagflowClient,
    run: ConnectorSyncRun,
    *,
    lease_owner: str,
    lease_token: str,
) -> None:
    if not job_leasing.ownership_matches(run, lease_owner=lease_owner, lease_token=lease_token):
        await db.rollback()
        return

    connector = await db.get(KnowledgeSourceConnector, run.connector_id)
    if connector is None or connector.deleted_at is not None:
        run.status = ConnectorSyncRunStatus.failed.value
        run.error_message = "connector missing"
        run.error_code = "errors.knowledge.connector_not_found"
        run.finished_at = _now()
        owned = await finalize_leased_sync_run(
            db, run, lease_owner=lease_owner, lease_token=lease_token
        )
        if not owned:
            logger.warning("lease stolen while failing missing connector run_id=%s", run.id)
        return

    resume_waiting = run.status == ConnectorSyncRunStatus.waiting_ingestion.value
    adapter = await connector_service.build_adapter(db, connector)
    try:

        async def _heartbeat() -> None:
            ok = await job_leasing.heartbeat(
                db,
                ConnectorSyncRun,
                job_id=run.id,
                lease_owner=lease_owner,
                lease_token=lease_token,
                lease_seconds=LEASE_SECONDS,
            )
            if not ok:
                raise LeaseLostError(f"lease lost for sync run {run.id}")

        await _heartbeat()
        await db.refresh(run)

        if resume_waiting:
            await _track_child_ingestion(db, run)
        else:
            await connector_sync_service.run_sync(
                db,
                ragflow,
                adapter,
                connector=connector,
                sync_run=run,
                on_heartbeat=_heartbeat,
            )
            await _track_child_ingestion(db, run)

        if run.status == ConnectorSyncRunStatus.waiting_ingestion.value:
            run.next_run_at = _now() + timedelta(seconds=WAITING_INGESTION_RETRY_SECONDS)

        owned = await finalize_leased_sync_run(
            db, run, lease_owner=lease_owner, lease_token=lease_token
        )
        if not owned:
            logger.warning("lease stolen, discard sync mutations run_id=%s", run.id)
    except LeaseLostError:
        logger.warning("lease lost mid-sync, rollback run_id=%s", run.id)
        await db.rollback()
    except Exception as exc:
        logger.exception("sync run failed run_id=%s", run.id)
        run.status = ConnectorSyncRunStatus.failed.value
        run.error_message = str(exc)
        run.error_code = "errors.knowledge.connector_sync_failed"
        run.finished_at = _now()
        owned = await finalize_leased_sync_run(
            db, run, lease_owner=lease_owner, lease_token=lease_token
        )
        if not owned:
            logger.warning("lease stolen while recording sync failure run_id=%s", run.id)
    finally:
        await adapter.close()


async def _track_child_ingestion(db, run: ConnectorSyncRun) -> None:
    """Advance SyncItems from child IngestionJob status; set waiting_ingestion if needed."""
    result = await db.execute(
        select(ConnectorSyncItem).where(
            ConnectorSyncItem.sync_run_id == run.id,
            ConnectorSyncItem.status.in_(
                [
                    ConnectorSyncItemStatus.ingestion_dispatched.value,
                    ConnectorSyncItemStatus.waiting_parse.value,
                ]
            ),
            not_deleted(ConnectorSyncItem),
        )
    )
    items = list(result.scalars().all())
    if not items:
        return

    pending = False
    any_failed = False
    for item in items:
        if not item.ingestion_job_id:
            continue
        job = await db.get(IngestionJob, item.ingestion_job_id)
        if job is None:
            continue
        if job.status == IngestionJobStatus.active.value:
            item.status = ConnectorSyncItemStatus.applied.value
        elif job.status in {IngestionJobStatus.failed.value, IngestionJobStatus.cancelled.value}:
            item.status = ConnectorSyncItemStatus.failed.value
            item.error = job.error_message
            any_failed = True
        else:
            pending = True
            item.status = ConnectorSyncItemStatus.waiting_parse.value

    if pending:
        if run.status in {
            ConnectorSyncRunStatus.completed.value,
            ConnectorSyncRunStatus.partial.value,
            ConnectorSyncRunStatus.waiting_ingestion.value,
            ConnectorSyncRunStatus.applying.value,
        }:
            run.status = ConnectorSyncRunStatus.waiting_ingestion.value
            run.finished_at = None
        return

    if any_failed or (run.metrics or {}).get("failed_count", 0) > 0:
        run.status = ConnectorSyncRunStatus.partial.value
    else:
        run.status = ConnectorSyncRunStatus.completed.value
    run.finished_at = _now()
    run.next_run_at = None


async def _run_loop() -> None:
    lease_owner = _lease_owner()
    ragflow = RagflowClient()
    loop_count = 0
    logger.info("connector worker started lease_owner=%s", lease_owner)
    try:
        while True:
            metrics_service.observe_worker_heartbeat(worker_role="connector")
            processed = False
            loop_count += 1
            if loop_count % SCHEDULE_EVERY_LOOPS == 0:
                async with async_session_factory() as db:
                    created = await connector_service.schedule_due_connectors(db)
                    if created:
                        logger.info("scheduled sync runs count=%s", len(created))
                    from app.services import connector_reconciliation_service

                    report = await connector_reconciliation_service.reconcile_connector_links(db)
                    if report.drifted:
                        logger.warning(
                            "connector reconciliation drifted=%s repaired=%s",
                            report.drifted,
                            report.repaired,
                        )
                    await db.commit()

            async with async_session_factory() as db:
                claimed = await claim_next_sync_run(db, lease_owner=lease_owner)
                if claimed:
                    run, lease_token = claimed
                    await process_sync_run(
                        db, ragflow, run, lease_owner=lease_owner, lease_token=lease_token
                    )
                    processed = True

            if not processed:
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
    finally:
        await ragflow.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Knowledge connector worker")
    parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_run_loop())


if __name__ == "__main__":
    main()
