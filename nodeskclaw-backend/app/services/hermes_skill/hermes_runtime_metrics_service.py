import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import not_deleted
from app.models.hermes_skill.hermes_artifact import HermesArtifact
from app.models.hermes_skill.hermes_task import HermesTask, TaskStatus
from app.services.hermes_external.hermes_bound_agent_scope_service import HermesBoundAgentScopeService
from app.services.hermes_skill.hermes_queue_policy_service import HermesQueuePolicyService

logger = logging.getLogger(__name__)

_RANGE_DAYS = {"today": 1, "7d": 7, "30d": 30}


class HermesRuntimeMetricsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_metrics(self, org_id: str, range_key: str = "7d") -> dict:
        days = _RANGE_DAYS.get(range_key, 7)
        since = datetime.now(timezone.utc) - timedelta(days=days)
        bound_ids = await HermesBoundAgentScopeService(self.db).list_bound_instance_ids(org_id)
        agent_filter = HermesQueuePolicyService._bound_agent_filter(bound_ids)

        overview = await self._overview(org_id, since, agent_filter)
        failed_agents = await self._top_failed_agents(org_id, since, bound_ids)
        failed_skills = await self._top_failed_skills(org_id, since, agent_filter)
        artifacts = await self._artifact_stats(org_id, since)

        return {
            "range": range_key,
            "since": since.isoformat(),
            "overview": overview,
            "failed_top_agents": failed_agents,
            "failed_top_skills": failed_skills,
            "artifacts": artifacts,
        }

    async def _overview(self, org_id: str, since: datetime, agent_filter) -> dict:
        base = select(HermesTask).where(
            not_deleted(HermesTask),
            HermesTask.org_id == org_id,
            HermesTask.created_at >= since,
            agent_filter,
        )
        total_result = await self.db.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = total_result.scalar_one()

        completed_result = await self.db.execute(
            select(func.count()).where(
                not_deleted(HermesTask),
                HermesTask.org_id == org_id,
                HermesTask.created_at >= since,
                HermesTask.status == TaskStatus.COMPLETED,
                agent_filter,
            )
        )
        completed = completed_result.scalar_one()

        failed_result = await self.db.execute(
            select(func.count()).where(
                not_deleted(HermesTask),
                HermesTask.org_id == org_id,
                HermesTask.created_at >= since,
                HermesTask.status.in_([TaskStatus.FAILED, TaskStatus.TIMEOUT]),
                agent_filter,
            )
        )
        failed = failed_result.scalar_one()

        queued_result = await self.db.execute(
            select(func.count()).where(
                not_deleted(HermesTask),
                HermesTask.org_id == org_id,
                HermesTask.status.in_([TaskStatus.QUEUED, TaskStatus.ACCEPTED]),
                agent_filter,
            )
        )
        backlog = queued_result.scalar_one()

        duration_result = await self.db.execute(
            select(
                func.avg(
                    func.extract(
                        "epoch",
                        HermesTask.completed_at - HermesTask.started_at,
                    )
                )
            ).where(
                not_deleted(HermesTask),
                HermesTask.org_id == org_id,
                HermesTask.created_at >= since,
                HermesTask.status == TaskStatus.COMPLETED,
                HermesTask.started_at.isnot(None),
                HermesTask.completed_at.isnot(None),
                agent_filter,
            )
        )
        avg_duration = duration_result.scalar_one()

        success_rate = (completed / total * 100) if total else 0.0
        return {
            "total_tasks": total,
            "completed": completed,
            "failed": failed,
            "success_rate": round(success_rate, 2),
            "avg_duration_seconds": round(float(avg_duration or 0), 2),
            "queue_backlog": backlog,
        }

    async def _top_failed_agents(
        self,
        org_id: str,
        since: datetime,
        bound_ids: list[str],
        limit: int = 10,
    ) -> list[dict]:
        if not bound_ids:
            return []
        stmt = (
            select(HermesTask.agent_id, func.count().label("cnt"))
            .where(
                not_deleted(HermesTask),
                HermesTask.org_id == org_id,
                HermesTask.created_at >= since,
                HermesTask.status.in_([TaskStatus.FAILED, TaskStatus.TIMEOUT]),
                HermesTask.agent_id.in_(bound_ids),
            )
            .group_by(HermesTask.agent_id)
            .order_by(func.count().desc())
            .limit(limit)
        )
        rows = (await self.db.execute(stmt)).all()
        return [{"agent_id": agent_id, "failed_count": cnt} for agent_id, cnt in rows]

    async def _top_failed_skills(self, org_id: str, since: datetime, agent_filter, limit: int = 10) -> list[dict]:
        stmt = (
            select(HermesTask.skill_id, func.count().label("cnt"))
            .where(
                not_deleted(HermesTask),
                HermesTask.org_id == org_id,
                HermesTask.created_at >= since,
                HermesTask.status.in_([TaskStatus.FAILED, TaskStatus.TIMEOUT]),
                HermesTask.skill_id.isnot(None),
                agent_filter,
            )
            .group_by(HermesTask.skill_id)
            .order_by(func.count().desc())
            .limit(limit)
        )
        rows = (await self.db.execute(stmt)).all()
        return [{"skill_id": skill_id, "failed_count": cnt} for skill_id, cnt in rows]

    async def _artifact_stats(self, org_id: str, since: datetime) -> dict:
        created = await self.db.execute(
            select(func.count()).where(
                not_deleted(HermesArtifact),
                HermesArtifact.org_id == org_id,
                HermesArtifact.created_at >= since,
            )
        )
        return {"created": created.scalar_one()}
