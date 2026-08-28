"""PostgreSQL advisory lock helpers for KB-scoped config mutation serialization."""

# @lat: [[knowledge#Reconciliation Runs]]
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def kb_advisory_xact_lock(db: AsyncSession, knowledge_base_id: str) -> None:
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:kb_id))"),
        {"kb_id": knowledge_base_id},
    )


async def application_advisory_xact_lock(db: AsyncSession, application_id: str) -> None:
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
        {"key": f"app:{application_id}"},
    )
