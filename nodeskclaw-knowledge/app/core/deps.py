"""Database session + auth dependencies."""

from collections.abc import AsyncGenerator
from time import monotonic

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.security import decode_token, extract_user_id
from app.integrations.nodeskclaw_backend.client import NodeskclawBackendClient
from app.schemas.principal import KnowledgePrincipal

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args={"ssl": False},
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_POOL_MAX_OVERFLOW,
)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

bearer_scheme = HTTPBearer(auto_error=False)
_backend_client = NodeskclawBackendClient()
_context_cache: dict[str, tuple[float, KnowledgePrincipal]] = {}


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


def get_ragflow_client():
    from app.integrations.ragflow.client import RagflowClient

    return RagflowClient()


async def get_member_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> KnowledgePrincipal:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": 40100,
                "message_key": "errors.auth.credentials_missing",
                "message": "未提供认证信息",
            },
        )
    token = credentials.credentials
    payload = decode_token(token)
    extract_user_id(payload)

    ttl = settings.MEMBER_CONTEXT_TTL_SECONDS
    if ttl > 0:
        cached = _context_cache.get(token)
        if cached and cached[0] > monotonic():
            return cached[1]

    principal = await _backend_client.fetch_knowledge_context(token)
    if not principal.is_active and not principal.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": 40300,
                "message_key": "errors.auth.user_inactive",
                "message": "用户已停用",
            },
        )
    if ttl > 0:
        _context_cache[token] = (monotonic() + ttl, principal)
    return principal
