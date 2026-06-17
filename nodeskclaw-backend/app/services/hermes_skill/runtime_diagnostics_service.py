import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.base import not_deleted
from app.models.hermes_skill.hermes_artifact import HermesArtifact
from app.models.hermes_skill.hermes_task import HermesTask, TaskStatus
from app.services.hermes_skill.artifact_audit_service import ArtifactAuditService
from app.services.hermes_skill.hermes_runtime_control_service import HermesRuntimeControlService
from app.services.hermes_external.hermes_bound_agent_scope_service import HermesBoundAgentScopeService
from app.services.hermes_external.hermes_docker_binding_service import HermesDockerBindingService

logger = logging.getLogger(__name__)


class RuntimeDiagnosticsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_runtime_diagnostics(self, org_id: str, *, include_unbound: bool = False) -> dict:
        now = datetime.now(timezone.utc)
        since_24h = now - timedelta(hours=24)
        bound_ids = await HermesBoundAgentScopeService(self.db).list_bound_instance_ids(org_id)

        queue = await self._queue_stats(org_id, since_24h, bound_ids)
        agents = await self._agent_stats(org_id, include_unbound=include_unbound)
        artifacts = await self._artifact_stats(org_id, since_24h)
        recent_failures = await self._recent_failed_tasks(org_id, since_24h, bound_ids)
        recent_scan_failed = await self._recent_scan_failed(org_id, since_24h)
        controls = await HermesRuntimeControlService(self.db).get_controls(org_id)

        return {
            "worker": {
                "enabled": settings.HERMES_TASK_WORKER_ENABLED,
                "interval_seconds": settings.HERMES_TASK_WORKER_INTERVAL_SECONDS,
                "batch_size": settings.HERMES_TASK_WORKER_BATCH_SIZE,
                "lock_timeout_seconds": settings.HERMES_TASK_LOCK_TIMEOUT_SECONDS,
                "paused": controls["worker"]["paused"],
            },
            "queue": {**queue, "paused": controls["queue"]["paused"]},
            "controls": controls,
            "agents": agents,
            "artifacts": artifacts,
            "recent_failures": recent_failures,
            "recent_scan_failed": recent_scan_failed,
        }

    async def _queue_stats(self, org_id: str, since: datetime, bound_ids: list[str]) -> dict:
        agent_filter = self._bound_agent_filter(bound_ids)
        base = select(HermesTask.status, func.count()).where(
            not_deleted(HermesTask),
            HermesTask.org_id == org_id,
            agent_filter,
        ).group_by(HermesTask.status)
        rows = (await self.db.execute(base)).all()
        counts = {status.value if hasattr(status, "value") else str(status): cnt for status, cnt in rows}

        failed_24h = await self.db.execute(
            select(func.count()).where(
                not_deleted(HermesTask),
                HermesTask.org_id == org_id,
                HermesTask.status == TaskStatus.FAILED,
                HermesTask.updated_at >= since,
                agent_filter,
            )
        )
        timeout_24h = await self.db.execute(
            select(func.count()).where(
                not_deleted(HermesTask),
                HermesTask.org_id == org_id,
                HermesTask.status == TaskStatus.TIMEOUT,
                HermesTask.updated_at >= since,
                agent_filter,
            )
        )
        return {
            "queued": counts.get("queued", 0),
            "accepted": counts.get("accepted", 0),
            "running": counts.get("running", 0),
            "failed_last_24h": failed_24h.scalar_one(),
            "timeout_last_24h": timeout_24h.scalar_one(),
        }

    @staticmethod
    def _bound_agent_filter(bound_ids: list[str]):
        if not bound_ids:
            return HermesTask.agent_id.is_(None)
        return or_(HermesTask.agent_id.is_(None), HermesTask.agent_id.in_(bound_ids))

    async def _agent_stats(self, org_id: str, *, include_unbound: bool = False) -> list[dict]:
        scope = HermesBoundAgentScopeService(self.db)
        agents: list[dict] = []
        for record, instance in await scope.list_bound_pairs(org_id):
            agents.append(self._pair_to_agent_dict(scope, record, instance, is_bound=True))
        if include_unbound:
            binding = HermesDockerBindingService(self.db)
            for record, instance in await binding.list_all_with_instances(org_id):
                if scope.is_bound(record, instance):
                    continue
                agents.append(self._pair_to_agent_dict(scope, record, instance, is_bound=False))
        return agents

    @staticmethod
    def _pair_to_agent_dict(
        scope: HermesBoundAgentScopeService,
        record,
        instance,
        *,
        is_bound: bool,
    ) -> dict:
        summary = scope.to_agent_summary(record, instance)
        employee_name = summary.get("employee_name")
        display_name = employee_name or record.profile_name
        agent_id = instance.id if instance is not None else (record.instance_id or record.profile_name)
        runtime_status = record.gateway_runtime_status or "unknown"
        return {
            "agent_id": agent_id,
            "instance_id": record.instance_id,
            "profile_name": record.profile_name,
            "container_name": record.container_name,
            "name": display_name,
            "employee_name": employee_name,
            "gateway_url": record.gateway_url,
            "gateway_status": record.gateway_status,
            "runtime_status": runtime_status,
            "mcp_status": record.mcp_status,
            "agent_call_status": record.mcp_status,
            "health": "ok" if runtime_status == "ready" else "degraded",
            "last_error": record.last_error,
            "binding_type": summary.get("binding_type"),
            "is_bound": is_bound,
            "task_dispatchable": summary.get("task_dispatchable", False),
            "source": "bound" if is_bound else "docker_scan",
        }

    async def _artifact_stats(self, org_id: str, since: datetime) -> dict:
        created = await self.db.execute(
            select(func.count()).where(
                not_deleted(HermesArtifact),
                HermesArtifact.org_id == org_id,
                HermesArtifact.created_at >= since,
            )
        )
        downloaded = 0
        try:
            audit = ArtifactAuditService(self.db)
            downloaded = await audit.count_actions_since(
                org_id=org_id,
                action="artifact.downloaded",
                since=since,
            )
        except Exception as exc:
            logger.warning("artifact download audit count failed: %s", exc)
        return {
            "created_last_24h": created.scalar_one(),
            "downloaded_last_24h": downloaded,
        }

    async def _recent_failed_tasks(
        self,
        org_id: str,
        since: datetime,
        bound_ids: list[str],
        limit: int = 10,
    ) -> list[dict]:
        agent_filter = self._bound_agent_filter(bound_ids)
        stmt = (
            select(HermesTask)
            .where(
                not_deleted(HermesTask),
                HermesTask.org_id == org_id,
                HermesTask.status == TaskStatus.FAILED,
                HermesTask.updated_at >= since,
                agent_filter,
            )
            .order_by(HermesTask.updated_at.desc())
            .limit(limit)
        )
        tasks = (await self.db.execute(stmt)).scalars().all()
        return [
            {
                "task_id": t.id,
                "task_no": t.task_no,
                "tool_name": t.tool_name,
                "error_code": t.error_code,
                "error_message": t.error_message,
                "updated_at": t.updated_at.isoformat() if t.updated_at else None,
            }
            for t in tasks
        ]

    async def _recent_scan_failed(self, org_id: str, since: datetime, limit: int = 10) -> list[dict]:
        from app.models.hermes_skill.hermes_task import HermesTaskEvent, EventType

        stmt = (
            select(HermesTaskEvent)
            .where(
                HermesTaskEvent.org_id == org_id,
                HermesTaskEvent.event_type == EventType.ARTIFACT_SCAN_FAILED,
                HermesTaskEvent.created_at >= since,
            )
            .order_by(HermesTaskEvent.created_at.desc())
            .limit(limit)
        )
        events = (await self.db.execute(stmt)).scalars().all()
        return [
            {
                "task_id": e.task_id,
                "payload": e.payload,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ]

    @staticmethod
    def _path_exists(path_str: str | None) -> bool:
        if not path_str:
            return False
        try:
            return Path(path_str).exists()
        except OSError:
            return False
