"""Background job for workspace schedule triggers (cron-based system messages)."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from croniter import croniter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workspace_agent import WorkspaceAgent
from app.models.workspace_schedule import WorkspaceSchedule
from app.models.workspace_task import WorkspaceTask

logger = logging.getLogger(__name__)


class ScheduleRunner:
    """Checks workspace_schedules every 60s, fires matching cron triggers."""

    def __init__(self, session_factory, check_interval: int = 60):
        self._session_factory = session_factory
        self._interval = check_interval
        self._task: asyncio.Task | None = None
        self._last_check: datetime | None = None

    def start(self):
        self._task = asyncio.create_task(self._loop())
        logger.info("ScheduleRunner started (interval=%ds)", self._interval)

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("ScheduleRunner stopped")

    async def _loop(self):
        while True:
            try:
                await asyncio.sleep(self._interval)
                await self._check()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("ScheduleRunner error: %s", e)
                await asyncio.sleep(30)

    async def _check(self):
        now = datetime.now(timezone.utc)
        prev = self._last_check or now
        self._last_check = now

        async with self._session_factory() as db:
            await self._check_overdue(db)

            result = await db.execute(
                select(WorkspaceSchedule).where(
                    WorkspaceSchedule.is_active,
                    WorkspaceSchedule.deleted_at.is_(None),
                )
            )
            schedules = result.scalars().all()

            for schedule in schedules:
                try:
                    cron = croniter(schedule.cron_expr, prev)
                    next_fire = cron.get_next(datetime)
                    if next_fire.replace(tzinfo=timezone.utc) <= now:
                        await self._fire(db, schedule)
                except Exception as e:
                    logger.warning(
                        "Schedule %s cron error: %s", schedule.id, e
                    )

    async def _check_overdue(self, db: AsyncSession):
        """Mark overdue scheduled tasks as failed and write task_success=0.0."""
        from app.api.workspaces import broadcast_event, _fire_task, _notify_agents_task_failed
        from app.models.workspace_task import FAILURE_TIMEOUT, FAILURE_UNCLAIMED_TIMEOUT
        from app.services import gene_service
        from app.services.workspace_service import _task_to_info, update_schedule_failure_count

        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(WorkspaceTask).where(
                WorkspaceTask.schedule_id.isnot(None),
                WorkspaceTask.deadline.isnot(None),
                WorkspaceTask.deadline < now,
                WorkspaceTask.status.in_(["pending", "in_progress"]),
                WorkspaceTask.deleted_at.is_(None),
            )
        )
        overdue = result.scalars().all()

        for task in overdue:
            old_status = task.status
            task.status = "failed"
            task.failure_reason = (
                FAILURE_TIMEOUT if task.assignee_instance_id else FAILURE_UNCLAIMED_TIMEOUT
            )
            await update_schedule_failure_count(
                db, task.schedule_id, success=False, workspace_id=task.workspace_id,
            )
            await db.commit()
            await db.refresh(task)

            task_info = _task_to_info(task)
            broadcast_event(task.workspace_id, "task:updated", task_info.model_dump(mode="json"))
            broadcast_event(task.workspace_id, "task:status_changed", {
                "task_id": task.id, "title": task.title,
                "old_status": old_status, "new_status": "failed",
            })

            if task.assignee_instance_id:
                try:
                    await gene_service.log_task_outcome(
                        db, task.assignee_instance_id, task.id, task.title,
                        success=False, failure_reason=task.failure_reason,
                    )
                except Exception as e:
                    logger.warning("超时任务写入 task_success 失败: %s", e)

            _fire_task(_notify_agents_task_failed(task.workspace_id, task.title))
            logger.info(
                "Overdue scheduled task '%s' marked failed (reason=%s, workspace %s)",
                task.title, task.failure_reason, task.workspace_id,
            )

    async def _fire(self, db, schedule: WorkspaceSchedule):
        from app.api.workspaces import broadcast_event
        from app.services import corridor_router, workspace_service
        from app.services.collaboration_service import send_system_message_to_agents
        from app.schemas.workspace import TaskCreate
        from app.models.instance import Instance
        from app.models.base import not_deleted

        workspace_id = schedule.workspace_id
        now = datetime.now(timezone.utc)

        has_topo = await corridor_router.has_any_connections(workspace_id, db)
        if has_topo:
            audience = await corridor_router.get_blackboard_audience(workspace_id, db)
            agent_ids = [ep.entity_id for ep in audience if ep.endpoint_type == "agent"]
        else:
            agents_q = await db.execute(
                select(Instance, WorkspaceAgent).join(
                    WorkspaceAgent,
                    (WorkspaceAgent.instance_id == Instance.id) & (WorkspaceAgent.deleted_at.is_(None)),
                ).where(
                    WorkspaceAgent.workspace_id == workspace_id,
                    Instance.status == "running",
                    not_deleted(Instance),
                )
            )
            agent_ids = [row[0].id for row in agents_q.all()]

        active_q = await db.execute(
            select(WorkspaceTask.id).where(
                WorkspaceTask.schedule_id == schedule.id,
                WorkspaceTask.status.in_(["pending", "in_progress"]),
                WorkspaceTask.deleted_at.is_(None),
            ).limit(1)
        )
        has_active = active_q.scalar_one_or_none() is not None

        task_created = False
        if not has_active:
            assignee = agent_ids[0] if len(agent_ids) == 1 else None
            deadline = now + timedelta(minutes=schedule.timeout_minutes)
            task_info = await workspace_service.create_task(
                db, workspace_id,
                TaskCreate(
                    title=schedule.name,
                    description=schedule.message_template,
                    assignee_id=assignee,
                ),
                schedule_id=schedule.id,
                deadline=deadline,
            )
            broadcast_event(workspace_id, "task:created", task_info.model_dump(mode="json"))
            task_created = True

        if agent_ids:
            if task_created:
                message = f"定时任务「{schedule.name}」已创建，请检查黑板待办任务。\n\n{schedule.message_template}"
            else:
                message = schedule.message_template or f"[{schedule.name}]"
            await send_system_message_to_agents(
                workspace_id, agent_ids, message, db,
                mention_targets=agent_ids,
            )

        logger.info(
            "Schedule '%s' fired (workspace %s, task_created=%s, agents=%d)",
            schedule.name, workspace_id, task_created, len(agent_ids),
        )


PRESET_TEMPLATES = [
    {
        "name": "daily_standup",
        "label": "每日站会",
        "cron_expr": "0 9 * * *",
        "message_template": "请各位汇报昨日进展、今日计划和当前卡点。",
    },
    {
        "name": "weekly_report",
        "label": "每周周报",
        "cron_expr": "0 17 * * 5",
        "message_template": "请提交本周工作总结和下周计划。",
    },
    {
        "name": "sprint_retro",
        "label": "冲刺回顾",
        "cron_expr": "0 14 1,15 * *",
        "message_template": "请回顾本冲刺的完成情况和改进建议。",
    },
]
