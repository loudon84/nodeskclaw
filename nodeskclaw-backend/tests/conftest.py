"""Shared test fixtures."""

import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/nodeskclaw_test")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-jwt-generation-nodeskclaw-testing-32chars")
os.environ.setdefault("ENCRYPTION_KEY", "MDEyMzQ1Njc4OTAxMjM0NTY3ODkwMTIzNDU2Nzg5MDE=")

import asyncio
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import text
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.core.deps import get_db
# from app.main import app
from app.models import Base

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = None
TestSessionLocal = None


def _drop_all_tables(sync_connection):
    preparer = sync_connection.dialect.identifier_preparer
    for table in Base.metadata.tables.values():
        sync_connection.execute(text(f"DROP TABLE IF EXISTS {preparer.format_table(table)} CASCADE"))


async def recreate_test_database(db_engine=None) -> bool:
    return False


async def drop_test_database(db_engine=None) -> None:
    pass


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=False)
async def setup_db():
    pass


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
