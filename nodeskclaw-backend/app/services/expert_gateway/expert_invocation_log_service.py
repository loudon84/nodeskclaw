from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.base import not_deleted
from app.models.expert_invocation_log import ExpertInvocationLog
from app.schemas.expert_log import ExpertInvocationLogDetail, ExpertInvocationLogItem

_SENSITIVE_KEY_RE = re.compile(r"(token|authorization|password|secret|api[_-]?key)", re.I)


def _sanitize_payload(payload: dict | None) -> dict | None:
    if not isinstance(payload, dict):
        return None
    result: dict[str, Any] = {}
    for key, value in payload.items():
        if _SENSITIVE_KEY_RE.search(str(key)):
            result[key] = "[REDACTED]"
        elif isinstance(value, dict):
            result[key] = _sanitize_payload(value)
        else:
            result[key] = value
    return result


def _prompt_preview(arguments: dict | None) -> str | None:
    if not isinstance(arguments, dict):
        return None
    prompt = arguments.get("prompt")
    if prompt is None:
        return None
    text = str(prompt)
    return text[:500] if len(text) > 500 else text


def _response_preview(result: dict | None) -> tuple[str | None, str | None, int | None]:
    if not isinstance(result, dict):
        return None, None, None
    content = result.get("content")
    if not isinstance(content, list):
        return None, None, None
    parts: list[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            parts.append(str(item.get("text") or ""))
    text = "\n".join(parts).strip()
    if not text:
        return None, None, None
    max_chars = settings.EXPERT_RESPONSE_PREVIEW_MAX_CHARS
    preview = text[:max_chars]
    return preview, "text/markdown", len(text.encode("utf-8"))


class ExpertInvocationLogService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_started(
        self,
        *,
        org_id: str,
        user_id: str | None,
        expert_id: str | None = None,
        expert_skill_id: str | None = None,
        expert_team_id: str | None = None,
        expert_slug: str | None = None,
        skill_name: str | None = None,
        upstream_tool_name: str | None = None,
        agent_alias: str | None = None,
        jsonrpc_id: str | None = None,
        request_payload: dict | None = None,
        client_source: str | None = None,
        client_version: str | None = None,
        client_device_id: str | None = None,
        parent_invocation_id: str | None = None,
        invocation_type: str = "expert_skill",
    ) -> ExpertInvocationLog:
        now = datetime.now(timezone.utc)
        log = ExpertInvocationLog(
            org_id=org_id,
            user_id=user_id,
            expert_id=expert_id,
            expert_skill_id=expert_skill_id,
            expert_team_id=expert_team_id,
            expert_slug=expert_slug,
            skill_name=skill_name,
            upstream_tool_name=upstream_tool_name,
            agent_alias=agent_alias,
            jsonrpc_id=str(jsonrpc_id) if jsonrpc_id is not None else None,
            status="started",
            request_payload=_sanitize_payload(request_payload),
            request_prompt_preview=_prompt_preview(request_payload),
            started_at=now,
            client_source=client_source,
            client_version=client_version,
            client_device_id=client_device_id,
            parent_invocation_id=parent_invocation_id,
            invocation_type=invocation_type,
        )
        self.db.add(log)
        await self.db.flush()
        return log

    async def mark_completed(
        self,
        log: ExpertInvocationLog,
        *,
        result: dict | None = None,
    ) -> ExpertInvocationLog:
        now = datetime.now(timezone.utc)
        preview, content_type, size_bytes = _response_preview(result)
        log.status = "completed"
        log.finished_at = now
        if log.started_at:
            log.duration_ms = int((now - log.started_at).total_seconds() * 1000)
        log.response_preview = preview
        log.response_content_type = content_type
        log.response_size_bytes = size_bytes
        await self.db.flush()
        return log

    async def mark_failed(
        self,
        log: ExpertInvocationLog,
        *,
        error_code: str,
        error_message: str,
        error_detail: dict | None = None,
    ) -> ExpertInvocationLog:
        now = datetime.now(timezone.utc)
        log.status = "failed"
        log.finished_at = now
        if log.started_at:
            log.duration_ms = int((now - log.started_at).total_seconds() * 1000)
        log.error_code = error_code
        log.error_message = error_message
        log.error_detail = error_detail
        await self.db.flush()
        return log

    async def mark_rejected(
        self,
        log: ExpertInvocationLog,
        *,
        error_code: str,
        error_message: str,
        error_detail: dict | None = None,
    ) -> ExpertInvocationLog:
        now = datetime.now(timezone.utc)
        log.status = "rejected"
        log.finished_at = now
        if log.started_at:
            log.duration_ms = int((now - log.started_at).total_seconds() * 1000)
        log.error_code = error_code
        log.error_message = error_message
        log.error_detail = error_detail
        await self.db.flush()
        return log

    async def list_logs(
        self,
        org_id: str,
        *,
        expert_slug: str | None = None,
        skill_name: str | None = None,
        status: str | None = None,
        user_id: str | None = None,
        keyword: str | None = None,
        started_from: datetime | None = None,
        started_to: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ExpertInvocationLogItem], int]:
        conditions = [ExpertInvocationLog.org_id == org_id, not_deleted(ExpertInvocationLog)]
        if expert_slug:
            conditions.append(ExpertInvocationLog.expert_slug == expert_slug)
        if skill_name:
            conditions.append(ExpertInvocationLog.skill_name == skill_name)
        if status:
            conditions.append(ExpertInvocationLog.status == status)
        if user_id:
            conditions.append(ExpertInvocationLog.user_id == user_id)
        if started_from:
            conditions.append(ExpertInvocationLog.started_at >= started_from)
        if started_to:
            conditions.append(ExpertInvocationLog.started_at <= started_to)
        if keyword:
            like = f"%{keyword}%"
            conditions.append(
                ExpertInvocationLog.request_prompt_preview.ilike(like)
                | ExpertInvocationLog.error_message.ilike(like)
            )

        count_stmt = select(func.count()).select_from(ExpertInvocationLog).where(and_(*conditions))
        total = int((await self.db.execute(count_stmt)).scalar_one())

        offset = max(page - 1, 0) * page_size
        stmt = (
            select(ExpertInvocationLog)
            .where(and_(*conditions))
            .order_by(ExpertInvocationLog.started_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        return [self._to_item(row) for row in rows], total

    async def get_log(self, org_id: str, log_id: str) -> ExpertInvocationLogDetail | None:
        stmt = select(ExpertInvocationLog).where(
            ExpertInvocationLog.org_id == org_id,
            ExpertInvocationLog.id == log_id,
            not_deleted(ExpertInvocationLog),
        )
        row = (await self.db.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        item = self._to_item(row)
        return ExpertInvocationLogDetail(
            **item.model_dump(),
            request_payload=row.request_payload,
            error_detail=row.error_detail,
        )

    async def count_recent_by_expert(self, org_id: str, expert_id: str, hours: int = 24) -> int:
        since = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(hours=hours)
        stmt = select(func.count()).select_from(ExpertInvocationLog).where(
            ExpertInvocationLog.org_id == org_id,
            ExpertInvocationLog.expert_id == expert_id,
            ExpertInvocationLog.started_at >= since,
            not_deleted(ExpertInvocationLog),
        )
        return int((await self.db.execute(stmt)).scalar_one())

    @staticmethod
    def _to_item(row: ExpertInvocationLog) -> ExpertInvocationLogItem:
        return ExpertInvocationLogItem(
            id=row.id,
            org_id=row.org_id,
            user_id=row.user_id,
            expert_id=row.expert_id,
            expert_skill_id=row.expert_skill_id,
            expert_team_id=row.expert_team_id,
            expert_slug=row.expert_slug,
            skill_name=row.skill_name,
            upstream_tool_name=row.upstream_tool_name,
            agent_alias=row.agent_alias,
            request_id=row.request_id,
            jsonrpc_id=row.jsonrpc_id,
            status=row.status,
            request_prompt_preview=row.request_prompt_preview,
            response_preview=row.response_preview,
            response_content_type=row.response_content_type,
            response_size_bytes=row.response_size_bytes,
            error_code=row.error_code,
            error_message=row.error_message,
            started_at=row.started_at,
            finished_at=row.finished_at,
            duration_ms=row.duration_ms,
            client_source=row.client_source,
            client_version=row.client_version,
            client_device_id=row.client_device_id,
            parent_invocation_id=row.parent_invocation_id,
            invocation_type=row.invocation_type,
            created_at=row.created_at,
        )
