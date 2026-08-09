"""Generic PostgreSQL job leasing v2 with FOR UPDATE SKIP LOCKED.

Claim commits immediately so external I/O never holds a row lock.
Updates require lease_owner + lease_token ownership verification.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from collections.abc import Sequence

from sqlalchemy import Select, select, update
from sqlalchemy.ext.asyncio import AsyncSession


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_lease_token() -> str:
    return secrets.token_hex(16)


async def claim_next(
    db: AsyncSession,
    model: type,
    *,
    statuses: Sequence[str],
    lease_owner: str,
    lease_seconds: int,
    extra_where: Sequence[Any] | None = None,
    order_by: Sequence[Any] | None = None,
    commit: bool = True,
) -> tuple[Any, str] | None:
    """Claim one job and optionally commit so the row lock is released before I/O."""
    now = utc_now()
    token = new_lease_token()
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

    lease_until = now + timedelta(seconds=lease_seconds)
    job.lease_owner = lease_owner
    job.lease_token = token
    job.lease_until = lease_until
    if hasattr(job, "last_heartbeat_at"):
        job.last_heartbeat_at = now
    await db.flush()
    if commit:
        await db.commit()
        await db.refresh(job)
    return job, token


async def heartbeat(
    db: AsyncSession,
    model: type,
    *,
    job_id: str,
    lease_owner: str,
    lease_token: str,
    lease_seconds: int,
) -> bool:
    now = utc_now()
    values: dict[str, Any] = {
        "lease_until": now + timedelta(seconds=lease_seconds),
    }
    if hasattr(model, "last_heartbeat_at"):
        values["last_heartbeat_at"] = now
    result = await db.execute(
        update(model)
        .where(
            model.id == job_id,
            model.deleted_at.is_(None),
            model.lease_owner == lease_owner,
            model.lease_token == lease_token,
        )
        .values(**values)
    )
    await db.commit()
    return bool(result.rowcount)


async def commit_if_owner(
    db: AsyncSession,
    model: type,
    *,
    job_id: str,
    lease_owner: str,
    lease_token: str,
    values: dict[str, Any],
) -> bool:
    """Apply updates only when the caller still owns the lease token."""
    result = await db.execute(
        update(model)
        .where(
            model.id == job_id,
            model.deleted_at.is_(None),
            model.lease_owner == lease_owner,
            model.lease_token == lease_token,
        )
        .values(**values)
    )
    await db.commit()
    return bool(result.rowcount)


async def clear_lease_if_owner(
    db: AsyncSession,
    model: type,
    *,
    job_id: str,
    lease_owner: str,
    lease_token: str,
    values: dict[str, Any] | None = None,
) -> bool:
    payload = dict(values or {})
    payload.update(
        {
            "lease_owner": None,
            "lease_token": None,
            "lease_until": None,
        }
    )
    return await commit_if_owner(
        db,
        model,
        job_id=job_id,
        lease_owner=lease_owner,
        lease_token=lease_token,
        values=payload,
    )


def ownership_matches(job: Any, *, lease_owner: str, lease_token: str) -> bool:
    return (
        getattr(job, "lease_owner", None) == lease_owner
        and getattr(job, "lease_token", None) == lease_token
    )
