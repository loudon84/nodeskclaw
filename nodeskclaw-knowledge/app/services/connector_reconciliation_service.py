"""Connector reconciliation: SourceObject vs SourceFile, SyncItem vs IngestionJob."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import not_deleted
from app.models.connector import ConnectorSourceObject, ConnectorSyncItem, ConnectorSyncRun
from app.models.enums import ConnectorSourceObjectState, ConnectorSyncItemStatus, ConnectorSyncRunStatus
from app.models.ingestion_job import IngestionJob
from app.models.source_file import SourceFile

logger = logging.getLogger(__name__)

# @lat: [[knowledge-objects#Connector Domain]]

STUCK_WAITING_HOURS = 6


@dataclass
class ConnectorReconciliationReport:
    checked: int = 0
    drifted: int = 0
    repaired: int = 0
    findings: list[dict] = field(default_factory=list)


def _now() -> datetime:
    return datetime.now(UTC)


async def reconcile_connector_links(db: AsyncSession) -> ConnectorReconciliationReport:
    report = ConnectorReconciliationReport()

    objs = list(
        (
            await db.execute(
                select(ConnectorSourceObject).where(
                    not_deleted(ConnectorSourceObject),
                    ConnectorSourceObject.state != ConnectorSourceObjectState.detached.value,
                )
            )
        )
        .scalars()
        .all()
    )
    for obj in objs:
        report.checked += 1
        if obj.source_file_id:
            sf = await db.get(SourceFile, obj.source_file_id)
            if sf is None or sf.deleted_at is not None:
                report.drifted += 1
                report.findings.append(
                    {
                        "kind": "source_object_missing_source_file",
                        "source_object_id": obj.id,
                        "source_file_id": obj.source_file_id,
                    }
                )
                obj.source_file_id = None
                obj.state = ConnectorSourceObjectState.error.value
                obj.last_error = "mapped SourceFile missing"
                report.repaired += 1

    orphan_files = list(
        (
            await db.execute(
                select(SourceFile).where(
                    SourceFile.source_kind == "connector",
                    SourceFile.connector_id.is_not(None),
                    not_deleted(SourceFile),
                )
            )
        )
        .scalars()
        .all()
    )
    for sf in orphan_files:
        report.checked += 1
        result = await db.execute(
            select(ConnectorSourceObject).where(
                ConnectorSourceObject.connector_id == sf.connector_id,
                ConnectorSourceObject.external_object_id == sf.external_object_id,
                not_deleted(ConnectorSourceObject),
            )
        )
        if result.scalar_one_or_none() is None:
            report.drifted += 1
            report.findings.append(
                {
                    "kind": "connector_source_file_missing_source_object",
                    "source_file_id": sf.id,
                    "connector_id": sf.connector_id,
                }
            )

    items = list(
        (
            await db.execute(
                select(ConnectorSyncItem).where(
                    ConnectorSyncItem.ingestion_job_id.is_not(None),
                    not_deleted(ConnectorSyncItem),
                )
            )
        )
        .scalars()
        .all()
    )
    for item in items:
        report.checked += 1
        job = await db.get(IngestionJob, item.ingestion_job_id)
        if job is None or job.deleted_at is not None:
            report.drifted += 1
            report.findings.append(
                {
                    "kind": "sync_item_missing_ingestion_job",
                    "sync_item_id": item.id,
                    "ingestion_job_id": item.ingestion_job_id,
                }
            )
            item.status = ConnectorSyncItemStatus.failed.value
            item.error = "ingestion job missing"
            report.repaired += 1

    cutoff = _now() - timedelta(hours=STUCK_WAITING_HOURS)
    stuck_runs = list(
        (
            await db.execute(
                select(ConnectorSyncRun).where(
                    ConnectorSyncRun.status == ConnectorSyncRunStatus.waiting_ingestion.value,
                    ConnectorSyncRun.updated_at < cutoff,
                    not_deleted(ConnectorSyncRun),
                )
            )
        )
        .scalars()
        .all()
    )
    for run in stuck_runs:
        report.checked += 1
        report.drifted += 1
        report.findings.append({"kind": "stuck_waiting_ingestion", "sync_run_id": run.id})
        # Soft repair: re-check child jobs; if none pending, mark completed/partial
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
        pending = list(result.scalars().all())
        still_waiting = False
        failed = 0
        for item in pending:
            if not item.ingestion_job_id:
                still_waiting = True
                continue
            job = await db.get(IngestionJob, item.ingestion_job_id)
            if job is None:
                item.status = ConnectorSyncItemStatus.failed.value
                failed += 1
                continue
            if job.status == "active":
                item.status = ConnectorSyncItemStatus.applied.value
            elif job.status in {"failed", "cancelled"}:
                item.status = ConnectorSyncItemStatus.failed.value
                failed += 1
            else:
                still_waiting = True
        if not still_waiting:
            run.status = (
                ConnectorSyncRunStatus.partial.value if failed else ConnectorSyncRunStatus.completed.value
            )
            run.finished_at = run.finished_at or _now()
            report.repaired += 1
        else:
            logger.warning("connector sync still stuck waiting_ingestion run_id=%s", run.id)

    return report
