import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestError
from app.models.base import not_deleted
from app.models.hermes_skill.hermes_task import HermesTask, TaskStatus
from app.services.hermes_skill.hermes_agent_runtime_service import HermesAgentRuntimeService
from app.services.hermes_skill.hermes_runtime_control_service import HermesRuntimeControlService

logger = logging.getLogger(__name__)


class HermesQueuePolicyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def can_enqueue(
        self,
        org_id: str,
        user_id: str | None,
        agent_id: str | None,
        skill_id: str | None,
    ) -> tuple[bool, str | None]:
        control = HermesRuntimeControlService(self.db)
        if await control.is_queue_paused(org_id):
            return False, "errors.hermes.queue_paused"

        queued_count = await self._count_org_queued(org_id)
        if queued_count >= settings.HERMES_QUEUE_ORG_MAX_QUEUED:
            return False, "errors.hermes.queue_org_limit"

        if agent_id:
            runtime = HermesAgentRuntimeService(self.db)
            if not await runtime.is_agent_routable(org_id, agent_id):
                return False, "errors.hermes.agent_not_accepting"
            agent_running = await runtime.count_running_tasks(org_id, agent_id)
            state = await runtime.get_or_create_state(org_id, agent_id)
            if agent_running >= state.max_concurrent_tasks:
                return False, "errors.hermes.agent_concurrency_limit"

        if skill_id:
            skill_running = await self._count_running_by_skill(org_id, skill_id)
            if skill_running >= settings.HERMES_QUEUE_SKILL_MAX_RUNNING:
                return False, "errors.hermes.skill_concurrency_limit"

        if user_id:
            user_running = await self._count_running_by_user(org_id, user_id)
            if user_running >= settings.HERMES_QUEUE_USER_MAX_RUNNING:
                return False, "errors.hermes.user_concurrency_limit"

        return True, None

    async def can_dispatch(self, task: HermesTask) -> tuple[bool, str | None]:
        control = HermesRuntimeControlService(self.db)
        if await control.is_queue_paused(task.org_id):
            return False, "queue_paused"
        if await control.is_worker_paused(task.org_id):
            return False, "worker_paused"

        now = datetime.now(timezone.utc)
        if task.not_before and task.not_before > now:
            return False, "not_before"

        if task.agent_id:
            runtime = HermesAgentRuntimeService(self.db)
            running = await runtime.count_running_tasks(task.org_id, task.agent_id)
            state = await runtime.get_or_create_state(task.org_id, task.agent_id)
            if running >= state.max_concurrent_tasks:
                return False, "agent_concurrency"

        return True, None

    async def get_queue_stats(self, org_id: str) -> dict:
        base = select(HermesTask.status, func.count()).where(
            not_deleted(HermesTask),
            HermesTask.org_id == org_id,
        ).group_by(HermesTask.status)
        rows = (await self.db.execute(base)).all()
        counts = {status.value if hasattr(status, "value") else str(status): cnt for status, cnt in rows}
        return {
            "queued": counts.get("queued", 0),
            "accepted": counts.get("accepted", 0),
            "running": counts.get("running", 0),
            "failed": counts.get("failed", 0),
            "timeout": counts.get("timeout", 0),
        }

    async def list_queue_tasks(
        self,
        org_id: str,
        *,
        status: str | None = None,
        agent_id: str | None = None,
        skill_id: str | None = None,
        user_id: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[HermesTask], int]:
        stmt = select(HermesTask).where(
            not_deleted(HermesTask),
            HermesTask.org_id == org_id,
        )
        count_stmt = select(func.count()).select_from(HermesTask).where(
            not_deleted(HermesTask),
            HermesTask.org_id == org_id,
        )
        if status:
            stmt = stmt.where(HermesTask.status == status)
            count_stmt = count_stmt.where(HermesTask.status == status)
        if agent_id:
            stmt = stmt.where(HermesTask.agent_id == agent_id)
            count_stmt = count_stmt.where(HermesTask.agent_id == agent_id)
        if skill_id:
            stmt = stmt.where(HermesTask.skill_id == skill_id)
            count_stmt = count_stmt.where(HermesTask.skill_id == skill_id)
        if user_id:
            stmt = stmt.where(HermesTask.user_id == user_id)
            count_stmt = count_stmt.where(HermesTask.user_id == user_id)

        total = (await self.db.execute(count_stmt)).scalar() or 0
        offset = (page - 1) * page_size
        stmt = (
            stmt.order_by(HermesTask.priority.desc(), HermesTask.created_at.asc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def set_priority(self, task: HermesTask, priority: int) -> HermesTask:
        task.priority = priority
        await self.db.flush()
        return task

    async def _count_org_queued(self, org_id: str) -> int:
        result = await self.db.execute(
            select(func.count()).where(
                not_deleted(HermesTask),
                HermesTask.org_id == org_id,
                HermesTask.status.in_([TaskStatus.QUEUED, TaskStatus.ACCEPTED]),
            )
        )
        return result.scalar_one()

    async def _count_running_by_skill(self, org_id: str, skill_id: str) -> int:
        result = await self.db.execute(
            select(func.count()).where(
                not_deleted(HermesTask),
                HermesTask.org_id == org_id,
                HermesTask.skill_id == skill_id,
                HermesTask.status == TaskStatus.RUNNING,
            )
        )
        return result.scalar_one()

    async def _count_running_by_user(self, org_id: str, user_id: str) -> int:
        result = await self.db.execute(
            select(func.count()).where(
                not_deleted(HermesTask),
                HermesTask.org_id == org_id,
                HermesTask.user_id == user_id,
                HermesTask.status == TaskStatus.RUNNING,
            )
        )
        return result.scalar_one()

    def compute_retry_not_before(self, retry_count: int) -> datetime:
        backoff = settings.HERMES_TASK_RETRY_BACKOFF_SECONDS * max(1, retry_count)
        return datetime.now(timezone.utc) + timedelta(seconds=backoff)
