import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operation_audit_log import OperationAuditLog
from app.models.hermes_skill.hermes_artifact import HermesArtifact
from app.models.base import not_deleted

logger = logging.getLogger(__name__)

ARTIFACT_ACTIONS = frozenset({
    "artifact.created",
    "artifact.downloaded",
    "artifact.previewed",
    "artifact.deleted",
    "artifact.permission_changed",
    "artifact.shared",
    "artifact.permission_granted",
    "artifact.permission_revoked",
})


class ArtifactAuditService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def log_artifact_action(
        self,
        action: str,
        artifact_id: str,
        org_id: str,
        actor_type: str = "user",
        actor_id: str = "",
        actor_name: str | None = None,
        workspace_id: str | None = None,
        details: dict | None = None,
    ) -> None:
        try:
            record = OperationAuditLog(
                id=str(uuid.uuid4()),
                org_id=org_id,
                workspace_id=workspace_id,
                action=action,
                target_type="hermes_artifact",
                target_id=artifact_id,
                actor_type=actor_type,
                actor_id=actor_id,
                actor_name=actor_name,
                details=details,
                created_at=datetime.now(timezone.utc),
            )
            self.db.add(record)
            await self.db.flush()
        except Exception as exc:
            logger.error("Artifact 审计日志写入失败: %s", exc)

    async def query_audit_logs(
        self,
        org_id: str,
        action: str | None = None,
        actor_id: str | None = None,
        target_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[OperationAuditLog], int]:
        base = select(OperationAuditLog).where(
            OperationAuditLog.org_id == org_id,
            OperationAuditLog.target_type == "hermes_artifact",
        )
        if action:
            base = base.where(OperationAuditLog.action == action)
        if actor_id:
            base = base.where(OperationAuditLog.actor_id == actor_id)
        if target_id:
            base = base.where(OperationAuditLog.target_id == target_id)
        if start_time:
            base = base.where(OperationAuditLog.created_at >= start_time)
        if end_time:
            base = base.where(OperationAuditLog.created_at <= end_time)

        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await self.db.execute(count_stmt)).scalar_one()

        offset = (page - 1) * page_size
        result = await self.db.execute(
            base.order_by(OperationAuditLog.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        return result.scalars().all(), total
