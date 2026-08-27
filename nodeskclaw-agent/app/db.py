from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text

from app.config import settings

engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_schema() -> None:
    schema = settings.SKILL_AGENT_SCHEMA
    async with engine.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        await conn.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS "{schema}".runs (
                    id VARCHAR(36) PRIMARY KEY,
                    org_id VARCHAR(64) NOT NULL,
                    user_id VARCHAR(64) NOT NULL,
                    tool_name VARCHAR(255) NOT NULL,
                    skill_id VARCHAR(64),
                    status VARCHAR(32) NOT NULL,
                    arguments JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    snapshot JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    result JSONB,
                    attempt_id VARCHAR(36),
                    generation BIGINT NOT NULL DEFAULT 0,
                    dispatch_id VARCHAR(64),
                    idempotency_key VARCHAR(128),
                    command_digest VARCHAR(64),
                    lease_until TIMESTAMPTZ,
                    worker_id VARCHAR(64),
                    requires_approval BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        await conn.execute(text(f'ALTER TABLE "{schema}".runs ADD COLUMN IF NOT EXISTS generation BIGINT NOT NULL DEFAULT 0'))
        await conn.execute(text(f'ALTER TABLE "{schema}".runs ADD COLUMN IF NOT EXISTS next_event_seq INTEGER NOT NULL DEFAULT 0'))
        # Backfill next_event_seq from existing max(event_seq)
        await conn.execute(
            text(
                f"""
                UPDATE "{schema}".runs r
                SET next_event_seq = COALESCE(
                    (SELECT MAX(e.event_seq) FROM "{schema}".run_events e WHERE e.run_id = r.id),
                    0
                )
                WHERE r.next_event_seq = 0;
                """
            )
        )
        await conn.execute(
            text(
                f"""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_runs_dispatch_id
                ON "{schema}".runs (org_id, dispatch_id)
                WHERE dispatch_id IS NOT NULL;
                """
            )
        )
        await conn.execute(
            text(
                f"""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_runs_idempotency
                ON "{schema}".runs (org_id, user_id, tool_name, idempotency_key)
                WHERE idempotency_key IS NOT NULL;
                """
            )
        )
        await conn.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS "{schema}".run_attempts (
                    id VARCHAR(36) PRIMARY KEY,
                    run_id VARCHAR(36) NOT NULL REFERENCES "{schema}".runs(id),
                    attempt_no INTEGER NOT NULL,
                    generation BIGINT NOT NULL DEFAULT 0,
                    worker_id VARCHAR(64) NOT NULL,
                    status VARCHAR(32) NOT NULL,
                    lease_until TIMESTAMPTZ,
                    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    heartbeat_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    completed_at TIMESTAMPTZ,
                    error_message TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (run_id, attempt_no)
                )
                """
            )
        )
        await conn.execute(text(f'ALTER TABLE "{schema}".run_attempts ADD COLUMN IF NOT EXISTS generation BIGINT NOT NULL DEFAULT 0'))
        await conn.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS "{schema}".run_events (
                    id VARCHAR(36) PRIMARY KEY,
                    run_id VARCHAR(36) NOT NULL REFERENCES "{schema}".runs(id),
                    attempt_id VARCHAR(36),
                    event_type VARCHAR(64) NOT NULL,
                    event_seq INTEGER NOT NULL,
                    source VARCHAR(64) NOT NULL DEFAULT 'agent',
                    source_event_id VARCHAR(128),
                    payload JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (run_id, event_seq)
                )
                """
            )
        )
        await conn.execute(text(f'ALTER TABLE "{schema}".run_events ADD COLUMN IF NOT EXISTS source VARCHAR(64) NOT NULL DEFAULT \'agent\''))
        await conn.execute(text(f'ALTER TABLE "{schema}".run_events ADD COLUMN IF NOT EXISTS source_event_id VARCHAR(128)'))
        await conn.execute(
            text(
                f"""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_run_events_source_dedup
                ON "{schema}".run_events (run_id, source, source_event_id)
                WHERE source_event_id IS NOT NULL;
                """
            )
        )
        await conn.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS "{schema}".run_approvals (
                    id VARCHAR(36) PRIMARY KEY,
                    run_id VARCHAR(36) NOT NULL REFERENCES "{schema}".runs(id),
                    approval_id VARCHAR(64) NOT NULL,
                    decision VARCHAR(32) NOT NULL,
                    evidence JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (run_id, approval_id)
                )
                """
            )
        )
        await conn.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS "{schema}".run_artifacts (
                    id VARCHAR(36) PRIMARY KEY,
                    run_id VARCHAR(36) NOT NULL REFERENCES "{schema}".runs(id),
                    attempt_id VARCHAR(36),
                    name VARCHAR(255) NOT NULL,
                    content_type VARCHAR(128),
                    size_bytes BIGINT,
                    storage_ref TEXT,
                    checksum_sha256 VARCHAR(64),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        await conn.execute(
            text(
                f'CREATE INDEX IF NOT EXISTS idx_agent_runs_status ON "{schema}".runs (status, created_at)'
            )
        )


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
