"""Connector sync worker: schedule, claim SyncRun with leasing v2, heartbeat."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import socket
import uuid

from sqlalchemy import select

from app.core.deps import async_session_factory
from app.integrations.ragflow.client import RagflowClient
from app.models.base import not_deleted
from app.models.connector import ConnectorSyncItem, ConnectorSyncRun, KnowledgeSourceConnector
from app.models.enums import ConnectorSyncItemStatus, ConnectorSyncRunStatus
from app.models.ingestion_job import IngestionJob
from app.services import connector_service, connector_sync_service
from app.workers import job_leasing

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 3.0
LEASE_SECONDS = 60
SCHEDULE_EVERY_LOOPS = 5


def _lease_owner() -> str:
    return f"connector:{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"


async def claim_next_sync_run(db, *, lease_owner: str):
    return await job_leasing.claim_next(
        db,
        ConnectorSyncRun,
        statuses=[ConnectorSyncRunStatus.pending.value],
        lease_owner=lease_owner,
        lease_seconds=LEASE_SECONDS,
        order_by=(ConnectorSyncRun.next_run_at.asc().nullsfirst(), ConnectorSyncRun.created_at.asc()),
        commit=True,
    )


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
        await job_leasing.clear_lease_if_owner(
            db,
            ConnectorSyncRun,
            job_id=run.id,
            lease_owner=lease_owner,
            lease_token=lease_token,
            values={
                "status": run.status,
                "error_message": run.error_message,
                "error_code": run.error_code,
            },
        )
        return

    adapter = await connector_service.build_adapter(db, connector)
    try:
        # Heartbeat before heavy I/O
        await job_leasing.heartbeat(
            db,
            ConnectorSyncRun,
            job_id=run.id,
            lease_owner=lease_owner,
            lease_token=lease_token,
            lease_seconds=LEASE_SECONDS,
        )
        await db.refresh(run)
        await connector_sync_service.run_sync(db, ragflow, adapter, connector=connector, sync_run=run)
        await _track_child_ingestion(db, run)
        await db.commit()
    except Exception as exc:
        logger.exception("sync run failed run_id=%s", run.id)
        run.status = ConnectorSyncRunStatus.failed.value
        run.error_message = str(exc)
        run.error_code = "errors.knowledge.connector_sync_failed"
        await db.commit()
    finally:
        await adapter.close()
        await job_leasing.clear_lease_if_owner(
            db,
            ConnectorSyncRun,
            job_id=run.id,
            lease_owner=lease_owner,
            lease_token=lease_token,
        )


async def _track_child_ingestion(db, run: ConnectorSyncRun) -> None:
    """Move waiting_ingestion when child jobs finish; otherwise leave status."""
    result = await db.execute(
        select(ConnectorSyncItem).where(
            ConnectorSyncItem.sync_run_id == run.id,
            ConnectorSyncItem.status == ConnectorSyncItemStatus.ingestion_dispatched.value,
            not_deleted(ConnectorSyncItem),
        )
    )
    items = list(result.scalars().all())
    if not items:
        return
    pending = False
    for item in items:
        if not item.ingestion_job_id:
            continue
        job = await db.get(IngestionJob, item.ingestion_job_id)
        if job is None:
            continue
        if job.status == "active":
            item.status = ConnectorSyncItemStatus.applied.value
        elif job.status in {"failed", "cancelled"}:
            item.status = ConnectorSyncItemStatus.failed.value
            item.error = job.error_message
        else:
            pending = True
            item.status = ConnectorSyncItemStatus.waiting_parse.value
    if pending and run.status in {
        ConnectorSyncRunStatus.completed.value,
        ConnectorSyncRunStatus.partial.value,
    }:
        run.status = ConnectorSyncRunStatus.waiting_ingestion.value


async def _run_loop() -> None:
    lease_owner = _lease_owner()
    ragflow = RagflowClient()
    loop_count = 0
    logger.info("connector worker started lease_owner=%s", lease_owner)
    try:
        while True:
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
                    await process_sync_run(db, ragflow, run, lease_owner=lease_owner, lease_token=lease_token)
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
