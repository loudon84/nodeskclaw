import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.base import not_deleted
from app.models.hermes_skill.hermes_artifact import HermesArtifact
from app.models.hermes_skill.hermes_task import HermesTask, TaskStatus
from app.models.hermes_skill.skill_installation import HermesSkillInstallation
from app.services.hermes_skill.artifact_audit_service import ArtifactAuditService

logger = logging.getLogger(__name__)


class RuntimeDiagnosticsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_runtime_diagnostics(self, org_id: str) -> dict:
        now = datetime.now(timezone.utc)
        since_24h = now - timedelta(hours=24)

        queue = await self._queue_stats(org_id, since_24h)
        agents = await self._agent_stats(org_id)
        artifacts = await self._artifact_stats(org_id, since_24h)
        recent_failures = await self._recent_failed_tasks(org_id, since_24h)
        recent_scan_failed = await self._recent_scan_failed(org_id, since_24h)

        return {
            "worker": {
                "enabled": settings.HERMES_TASK_WORKER_ENABLED,
                "interval_seconds": settings.HERMES_TASK_WORKER_INTERVAL_SECONDS,
                "batch_size": settings.HERMES_TASK_WORKER_BATCH_SIZE,
                "lock_timeout_seconds": settings.HERMES_TASK_LOCK_TIMEOUT_SECONDS,
            },
            "queue": queue,
            "agents": agents,
            "artifacts": artifacts,
            "recent_failures": recent_failures,
            "recent_scan_failed": recent_scan_failed,
        }

    async def _queue_stats(self, org_id: str, since: datetime) -> dict:
        base = select(HermesTask.status, func.count()).where(
            not_deleted(HermesTask),
            HermesTask.org_id == org_id,
        ).group_by(HermesTask.status)
        rows = (await self.db.execute(base)).all()
        counts = {status.value if hasattr(status, "value") else str(status): cnt for status, cnt in rows}

        failed_24h = await self.db.execute(
            select(func.count()).where(
                not_deleted(HermesTask),
                HermesTask.org_id == org_id,
                HermesTask.status == TaskStatus.FAILED,
                HermesTask.updated_at >= since,
            )
        )
        timeout_24h = await self.db.execute(
            select(func.count()).where(
                not_deleted(HermesTask),
                HermesTask.org_id == org_id,
                HermesTask.status == TaskStatus.TIMEOUT,
                HermesTask.updated_at >= since,
            )
        )
        return {
            "queued": counts.get("queued", 0),
            "accepted": counts.get("accepted", 0),
            "running": counts.get("running", 0),
            "failed_last_24h": failed_24h.scalar_one(),
            "timeout_last_24h": timeout_24h.scalar_one(),
        }

    async def _agent_stats(self, org_id: str) -> list[dict]:
        stmt = (
            select(HermesSkillInstallation)
            .where(
                not_deleted(HermesSkillInstallation),
                HermesSkillInstallation.org_id == org_id,
                HermesSkillInstallation.status == "installed",
            )
            .order_by(HermesSkillInstallation.agent_id)
        )
        installations = (await self.db.execute(stmt)).scalars().all()
        seen: set[str] = set()
        agents: list[dict] = []
        for inst in installations:
            if inst.agent_id in seen:
                continue
            seen.add(inst.agent_id)
            profile_exists = self._path_exists(inst.profile_root_path)
            workspace_exists = self._path_exists(inst.installed_path)
            health = "ok" if inst.status == "installed" else "degraded"
            if not profile_exists or not workspace_exists:
                health = "degraded"
            agents.append({
                "agent_id": inst.agent_id,
                "name": inst.agent_id,
                "base_url": None,
                "health": health,
                "profile_root_path": inst.profile_root_path,
                "profile_root_path_exists": profile_exists,
                "workspace_root_path": inst.installed_path,
                "workspace_root_path_exists": workspace_exists,
                "last_error": inst.error_message,
            })
        return agents

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

    async def _recent_failed_tasks(self, org_id: str, since: datetime, limit: int = 10) -> list[dict]:
        stmt = (
            select(HermesTask)
            .where(
                not_deleted(HermesTask),
                HermesTask.org_id == org_id,
                HermesTask.status == TaskStatus.FAILED,
                HermesTask.updated_at >= since,
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
