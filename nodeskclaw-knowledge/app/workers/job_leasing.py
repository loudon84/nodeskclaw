"""Generic PostgreSQL job leasing with FOR UPDATE SKIP LOCKED."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from collections.abc import Sequence

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession


def utc_now() -> datetime:
    return datetime.now(UTC)


async def claim_next(
    db: AsyncSession,
    model: type,
    *,
    statuses: Sequence[str],
    lease_owner: str,
    lease_seconds: int,
    extra_where: Sequence[Any] | None = None,
    order_by: Sequence[Any] | None = None,
) -> Any | None:
    now = utc_now()
    conditions = [
        model.status.in_(list(statuses)),
        model.deleted_at.is_(None),
        (model.next_run_at.is_(None)) | (model.next_run_at <= now),
        (model.lease_until.is_(None)) | (model.lease_until < now),
    ]
    if extra_where:
        conditions.extend(extra_where)

    stmt: Select = select(model).where(*conditions)
    if order_by:
        stmt = stmt.order_by(*order_by)
    else:
        stmt = stmt.order_by(model.next_run_at.asc().nullsfirst(), model.created_at.asc())
    stmt = stmt.with_for_update(skip_locked=True).limit(1)

    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    if job is None:
        return None
    job.lease_owner = lease_owner
    job.lease_until = now + timedelta(seconds=lease_seconds)
    await db.flush()
    return job
