"""MCP Skill Gateway call audit logging."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import not_deleted
from app.models.mcp_call_log import McpCallLog

logger = logging.getLogger(__name__)

_SENSITIVE_KEYS = frozenset({
    "authorization",
    "access_token",
    "accesstoken",
    "token",
    "password",
    "webui_password",
    "secret",
    "api_key",
    "apikey",
})


def sanitize_input_summary(arguments: dict[str, Any] | None) -> dict[str, Any] | None:
    if not arguments:
        return None
    summary: dict[str, Any] = {}
    for key, value in arguments.items():
        key_lower = key.lower()
        if key_lower in _SENSITIVE_KEYS or "password" in key_lower or "token" in key_lower:
            continue
        if isinstance(value, str):
            summary[key] = {"type": "string", "length": len(value)}
        elif isinstance(value, (dict, list)):
            summary[key] = {"type": type(value).__name__, "size": len(value)}
        else:
            summary[key] = value
    return summary or None


def sanitize_result_summary(result: dict[str, Any] | None) -> dict[str, Any] | None:
    if not result:
        return None
    return dict(result)


async def log_mcp_call(
    db: AsyncSession,
    *,
    org_id: str,
    user_id: str,
    tool_name: str,
    status: str,
    duration_ms: int | None = None,
    instance_id: str | None = None,
    arguments: dict[str, Any] | None = None,
    result_summary: dict[str, Any] | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    client_name: str | None = None,
    permission: str | None = None,
    risk_level: str | None = None,
) -> None:
    try:
        entry = McpCallLog(
            org_id=org_id,
            user_id=user_id,
            client_name=client_name,
            tool_name=tool_name,
            permission=permission,
            risk_level=risk_level,
            instance_id=instance_id,
            status=status,
            duration_ms=duration_ms,
            input_summary=sanitize_input_summary(arguments),
            result_summary=sanitize_result_summary(result_summary),
            error_code=error_code,
            error_message=(error_message or "")[:500] or None,
        )
        db.add(entry)
        await db.commit()
    except Exception:
        logger.warning("Failed to write MCP call audit log tool=%s", tool_name, exc_info=True)
        await db.rollback()


async def list_mcp_calls(
    db: AsyncSession,
    *,
    org_id: str,
    user_id: str | None = None,
    tool_name: str | None = None,
    instance_id: str | None = None,
    status: str | None = None,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[McpCallLog], int]:
    query = select(McpCallLog).where(
        McpCallLog.org_id == org_id,
        not_deleted(McpCallLog),
    )
    count_query = select(func.count()).select_from(McpCallLog).where(
        McpCallLog.org_id == org_id,
        not_deleted(McpCallLog),
    )

    if user_id:
        query = query.where(McpCallLog.user_id == user_id)
        count_query = count_query.where(McpCallLog.user_id == user_id)
    if tool_name:
        query = query.where(McpCallLog.tool_name == tool_name)
        count_query = count_query.where(McpCallLog.tool_name == tool_name)
    if instance_id:
        query = query.where(McpCallLog.instance_id == instance_id)
        count_query = count_query.where(McpCallLog.instance_id == instance_id)
    if status:
        query = query.where(McpCallLog.status == status)
        count_query = count_query.where(McpCallLog.status == status)
    if from_time:
        query = query.where(McpCallLog.created_at >= from_time)
        count_query = count_query.where(McpCallLog.created_at >= from_time)
    if to_time:
        query = query.where(McpCallLog.created_at <= to_time)
        count_query = count_query.where(McpCallLog.created_at <= to_time)

    total = int((await db.execute(count_query)).scalar_one())
    result = await db.execute(
        query.order_by(McpCallLog.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), total
