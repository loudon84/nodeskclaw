"""Audit log service."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.base import not_deleted
from app.schemas.principal import KnowledgePrincipal


async def write_audit(
    db: AsyncSession,
    *,
    org_id: str,
    member_id: str | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    details: dict[str, Any] | None = None,
    commit: bool = False,
) -> AuditLog:
    row = AuditLog(
        org_id=org_id,
        member_id=member_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
    )
    db.add(row)
    if commit:
        await db.commit()
        await db.refresh(row)
    else:
        await db.flush()
    return row


async def list_audits(
    db: AsyncSession,
    member: KnowledgePrincipal,
    *,
    action: str | None = None,
    resource_type: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[AuditLog], int]:
    filters = [AuditLog.org_id == member.org_id, not_deleted(AuditLog)]
    if action:
        filters.append(AuditLog.action == action)
    if resource_type:
        filters.append(AuditLog.resource_type == resource_type)
    total = await db.scalar(select(func.count()).select_from(AuditLog).where(*filters)) or 0
    result = await db.execute(
        select(AuditLog)
        .where(*filters)
        .order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result.scalars().all()), int(total)
