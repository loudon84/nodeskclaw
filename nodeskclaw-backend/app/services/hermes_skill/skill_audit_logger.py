import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operation_audit_log import OperationAuditLog

logger = logging.getLogger(__name__)


class SkillAuditLogger:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self,
        action: str,
        target_id: str,
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
                target_type="hermes_skill",
                target_id=target_id,
                actor_type=actor_type,
                actor_id=actor_id,
                actor_name=actor_name,
                details=details,
                created_at=datetime.now(timezone.utc),
            )
            self.db.add(record)
            await self.db.flush()
        except Exception as exc:
            logger.error("审计日志写入失败: %s", exc)
