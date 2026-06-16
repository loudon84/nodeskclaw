import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.base import not_deleted
from app.models.hermes_skill.hermes_task import HermesTask
from app.models.hermes_skill.hermes_task_event_token import HermesTaskEventToken

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 300
TOKEN_SCOPE = "task_events_read"


class TaskEventTokenService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _hash_token(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode()).hexdigest()

    async def create_token(
        self,
        task_id: str,
        user_id: str,
        org_id: str,
        *,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> dict:
        task = await self._get_task(task_id, org_id)
        raw_token = f"sse_{secrets.token_urlsafe(32)}"
        token_hash = self._hash_token(raw_token)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl_seconds)

        record = HermesTaskEventToken(
            id=str(uuid.uuid4()),
            org_id=org_id,
            task_id=task.id,
            user_id=user_id,
            token_hash=token_hash,
            scope=TOKEN_SCOPE,
            expires_at=expires_at,
            used_count=0,
        )
        self.db.add(record)
        await self.db.flush()

        event_url = f"/api/v1/hermes/tasks/{task_id}/events?token={raw_token}"
        return {
            "event_url": event_url,
            "expires_in": ttl_seconds,
            "expires_at": expires_at.isoformat(),
        }

    async def verify_token(
        self,
        raw_token: str,
        task_id: str,
    ) -> tuple[bool, str | None, str | None]:
        if not raw_token:
            return False, None, None
        token_hash = self._hash_token(raw_token)
        result = await self.db.execute(
            select(HermesTaskEventToken).where(
                HermesTaskEventToken.token_hash == token_hash,
                HermesTaskEventToken.task_id == task_id,
                HermesTaskEventToken.scope == TOKEN_SCOPE,
                HermesTaskEventToken.revoked_at.is_(None),
                not_deleted(HermesTaskEventToken),
            )
        )
        record = result.scalar_one_or_none()
        if record is None:
            return False, None, None

        now = datetime.now(timezone.utc)
        if record.expires_at <= now:
            return False, None, None

        record.used_count += 1
        await self.db.flush()
        return True, record.user_id, record.org_id

    async def revoke_token(self, token_hash: str) -> None:
        now = datetime.now(timezone.utc)
        await self.db.execute(
            update(HermesTaskEventToken)
            .where(
                HermesTaskEventToken.token_hash == token_hash,
                not_deleted(HermesTaskEventToken),
            )
            .values(revoked_at=now)
        )
        await self.db.flush()

    async def _get_task(self, task_id: str, org_id: str) -> HermesTask:
        result = await self.db.execute(
            select(HermesTask).where(
                HermesTask.id == task_id,
                HermesTask.org_id == org_id,
                not_deleted(HermesTask),
            )
        )
        task = result.scalar_one_or_none()
        if task is None:
            raise NotFoundError("任务不存在", "errors.task.not_found")
        return task
