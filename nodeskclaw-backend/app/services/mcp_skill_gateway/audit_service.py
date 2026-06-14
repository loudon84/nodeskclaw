"""MCP Skill Gateway call audit logging."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

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
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    try:
        entry = McpCallLog(
            org_id=org_id,
            user_id=user_id,
            tool_name=tool_name,
            instance_id=instance_id,
            status=status,
            duration_ms=duration_ms,
            input_summary=sanitize_input_summary(arguments),
            error_code=error_code,
            error_message=(error_message or "")[:500] or None,
        )
        db.add(entry)
        await db.commit()
    except Exception:
        logger.warning("Failed to write MCP call audit log tool=%s", tool_name, exc_info=True)
        await db.rollback()
