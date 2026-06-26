import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.base import not_deleted
from app.models.hermes_skill.hermes_task import HermesTask, TaskStatus
from app.services.mcp_skill_gateway.auth import McpAuthContext

_DEDUP_STATUSES = (
    TaskStatus.QUEUED,
    TaskStatus.ACCEPTED,
    TaskStatus.RUNNING,
    TaskStatus.COMPLETED,
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _identity_part(auth_ctx: McpAuthContext) -> str:
    if auth_ctx.mcp_client_token_id:
        return auth_ctx.mcp_client_token_id
    if auth_ctx.mcp_client_token_prefix:
        return auth_ctx.mcp_client_token_prefix
    if auth_ctx.hermes_agent_id:
        return auth_ctx.hermes_agent_id
    return auth_ctx.user.id or ""


def build_mcp_task_dedup_key(
    org_id: str,
    auth_ctx: McpAuthContext,
    tool_name: str,
    arguments: dict,
) -> str:
    payload = "|".join([
        org_id,
        _identity_part(auth_ctx),
        tool_name,
        _canonical_json(arguments or {}),
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class McpTaskDedupService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_dedupe_task(
        self,
        org_id: str,
        fingerprint: str,
    ) -> HermesTask | None:
        if not settings.MCP_TASK_DEDUP_ENABLED:
            return None

        window_start = datetime.now(timezone.utc) - timedelta(
            seconds=settings.MCP_TASK_DEDUP_WINDOW_SECONDS,
        )
        result = await self.db.execute(
            select(HermesTask)
            .where(
                not_deleted(HermesTask),
                HermesTask.org_id == org_id,
                HermesTask.status.in_(_DEDUP_STATUSES),
                HermesTask.created_at >= window_start,
                HermesTask.client_context["request_fingerprint"].astext == fingerprint,
            )
            .order_by(HermesTask.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
