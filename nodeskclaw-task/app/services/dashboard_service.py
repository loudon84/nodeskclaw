"""Dashboard aggregation."""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.automation_task import AutomationTask
from app.models.base import not_deleted
from app.models.enums import TaskStatus, WorkerStatus
from app.models.rpa_worker import RpaWorker
from app.schemas.dashboard import DashboardSummary


async def get_dashboard_summary(db: AsyncSession, tenant_id: str) -> DashboardSummary:
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    base = select(AutomationTask).where(
        AutomationTask.tenant_id == tenant_id,
        AutomationTask.created_at >= today_start,
        not_deleted(AutomationTask),
    )
    tasks = (await db.execute(base)).scalars().all()
    today_total = len(tasks)
    ready = sum(1 for t in tasks if t.status == TaskStatus.READY)
    running = sum(1 for t in tasks if t.status in {TaskStatus.RUNNING, TaskStatus.LEASED})
    waiting_human = sum(1 for t in tasks if t.status in {TaskStatus.WAITING_HUMAN, TaskStatus.HUMAN_OPERATING})
    failed = sum(1 for t in tasks if t.status == TaskStatus.FAILED)
    success = sum(1 for t in tasks if t.status in {TaskStatus.SUCCESS, TaskStatus.SUCCESS_MANUAL, TaskStatus.PARTIAL_SUCCESS})
    success_rate = (success / today_total) if today_total else 0.0

    cutoff = datetime.now(UTC)
    from datetime import timedelta

    heartbeat_cutoff = cutoff - timedelta(seconds=settings.WORKER_HEARTBEAT_TIMEOUT_SECONDS)
    online_workers = (
        await db.execute(
            select(func.count()).select_from(RpaWorker).where(
                RpaWorker.status.in_([WorkerStatus.ONLINE, WorkerStatus.BUSY]),
                RpaWorker.last_heartbeat_at >= heartbeat_cutoff,
                not_deleted(RpaWorker),
            )
        )
    ).scalar_one()

    return DashboardSummary(
        today_total=today_total,
        ready=ready,
        running=running,
        waiting_human=waiting_human,
        failed=failed,
        success=success,
        success_rate=round(success_rate, 2),
        online_workers=online_workers or 0,
    )
