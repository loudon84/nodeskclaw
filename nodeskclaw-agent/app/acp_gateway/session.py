from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.acp_gateway.errors import AcpGatewayError
from app.config import settings

SCHEMA = settings.SKILL_AGENT_SCHEMA
NONTERMINAL = (
    "QUEUED",
    "WAITING_APPROVAL",
    "PREPARING",
    "RUNNING",
    "RESUMING",
    "WAITING_EDGE",
    "CANCELLING",
    "PAUSED",
    "SUSPENDED",
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _metadata(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


async def create_session(
    db: AsyncSession,
    *,
    org_id: str,
    user_id: str,
    agent_ref: str,
    cwd: str | None = None,
) -> str:
    session_id = str(uuid.uuid4())
    now = _utcnow()
    metadata = {"agent_ref": agent_ref, "expert_slug": agent_ref, "transport": "nodeskclaw.acp-runtime.v1"}
    if cwd:
        metadata["cwd"] = cwd
    await db.execute(
        text(
            f"""
            INSERT INTO "{SCHEMA}".run_sessions (
                id, org_id, user_id, metadata, context_version, created_at, updated_at
            ) VALUES (
                :id, :org_id, :user_id, CAST(:metadata AS jsonb), 1, :now, :now
            )
            """
        ),
        {
            "id": session_id,
            "org_id": org_id,
            "user_id": user_id,
            "metadata": json.dumps(metadata),
            "now": now,
        },
    )
    return session_id


async def load_session(db: AsyncSession, session_id: str) -> dict[str, Any] | None:
    row = (
        await db.execute(
            text(
                f"""
                SELECT id, org_id, user_id, metadata, context_version, deleted_at, expires_at
                FROM "{SCHEMA}".run_sessions
                WHERE id = :id
                LIMIT 1
                """
            ),
            {"id": session_id},
        )
    ).mappings().first()
    return dict(row) if row else None


def assert_session_scope(row: dict[str, Any], *, org_id: str, user_id: str, agent_ref: str) -> None:
    if row.get("deleted_at") is not None:
        raise AcpGatewayError("ACP_SESSION_NOT_FOUND", "session closed")
    if str(row.get("org_id") or "") != org_id or str(row.get("user_id") or "") != user_id:
        raise AcpGatewayError("ACP_SESSION_FORBIDDEN", "session scope mismatch")
    meta = _metadata(row.get("metadata"))
    pinned = str(meta.get("agent_ref") or meta.get("expert_slug") or "")
    if pinned and pinned != agent_ref:
        raise AcpGatewayError("ACP_SESSION_FORBIDDEN", "session expert mismatch")


async def session_has_nonterminal_run(db: AsyncSession, session_id: str) -> bool:
    row = (
        await db.execute(
            text(
                f"""
                SELECT id FROM "{SCHEMA}".runs
                WHERE run_session_id = :session_id AND status = ANY(:statuses)
                LIMIT 1
                """
            ),
            {"session_id": session_id, "statuses": list(NONTERMINAL)},
        )
    ).first()
    return row is not None


async def close_session(db: AsyncSession, session_id: str) -> None:
    await db.execute(
        text(
            f"""
            UPDATE "{SCHEMA}".run_sessions
            SET deleted_at = :now, updated_at = :now
            WHERE id = :id AND deleted_at IS NULL
            """
        ),
        {"id": session_id, "now": _utcnow()},
    )


async def latest_run_for_session(db: AsyncSession, session_id: str) -> dict[str, Any] | None:
    row = (
        await db.execute(
            text(
                f"""
                SELECT id, status, generation, attempt_id, arguments
                FROM "{SCHEMA}".runs
                WHERE run_session_id = :session_id
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"session_id": session_id},
        )
    ).mappings().first()
    return dict(row) if row else None
