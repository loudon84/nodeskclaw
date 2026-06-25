import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.base import not_deleted
from app.models.mcp_client_token import McpClientToken

DEFAULT_MCP_CLIENT_SCOPES = [
    "mcp:tools:list",
    "mcp:tools:call",
    "skill:view",
    "skill:invoke",
]


def _slugify_instance_name(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower())
    return slug.strip("_") or "instance"


def _hash_token(plain: str) -> str:
    return hashlib.sha256(plain.encode()).hexdigest()


def _token_prefix(instance_name: str, random_part: str) -> str:
    return f"ndsk_mcp_{_slugify_instance_name(instance_name)}_{random_part}"


class McpClientTokenService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_active_token(self, hermes_agent_id: str) -> McpClientToken | None:
        result = await self.db.execute(
            select(McpClientToken).where(
                not_deleted(McpClientToken),
                McpClientToken.hermes_agent_id == hermes_agent_id,
                McpClientToken.revoked_at.is_(None),
            )
        )
        token = result.scalar_one_or_none()
        if token is None:
            return None
        if token.expires_at and token.expires_at <= datetime.now(timezone.utc):
            return token
        return token

    async def get_token_by_id(self, token_id: str) -> McpClientToken | None:
        result = await self.db.execute(
            select(McpClientToken).where(
                not_deleted(McpClientToken),
                McpClientToken.id == token_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_token(
        self,
        *,
        org_id: str,
        hermes_agent_id: str,
        instance_name: str,
        created_by: str,
        profile: str = "default",
        workspace_id: str = "default",
        allowed_skills: list[str] | None = None,
        allowed_tools: list[str] | None = None,
        expires_days: int = 180,
        scopes: list[str] | None = None,
    ) -> tuple[str, McpClientToken]:
        if expires_days < 1:
            raise BadRequestError("有效期必须大于 0 天", "errors.mcp_gateway.invalid_expires_days")

        random_part = secrets.token_hex(4)
        secret = secrets.token_urlsafe(32)
        prefix = _token_prefix(instance_name, random_part)
        plain = f"{prefix}.{secret}"

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=expires_days)

        record = McpClientToken(
            org_id=org_id,
            name=f"hermes-{instance_name}",
            token_prefix=prefix,
            token_hash=_hash_token(plain),
            actor_type="mcp_client",
            service_account_user_id=created_by,
            hermes_agent_id=hermes_agent_id,
            hermes_instance_name=instance_name,
            profile=profile,
            workspace_id=workspace_id,
            scopes=scopes or list(DEFAULT_MCP_CLIENT_SCOPES),
            allowed_tools=allowed_tools,
            allowed_skills=allowed_skills,
            expires_at=expires_at,
            created_by=created_by,
        )
        self.db.add(record)
        await self.db.flush()
        return plain, record

    async def verify_token(self, plain: str) -> McpClientToken | None:
        if not plain or not plain.startswith("ndsk_mcp_"):
            return None

        token_hash = _hash_token(plain)
        prefix = plain.split(".", 1)[0] if "." in plain else plain[:64]

        result = await self.db.execute(
            select(McpClientToken).where(
                not_deleted(McpClientToken),
                McpClientToken.token_hash == token_hash,
                McpClientToken.token_prefix == prefix,
                McpClientToken.revoked_at.is_(None),
            )
        )
        record = result.scalar_one_or_none()
        if record is None:
            return None

        now = datetime.now(timezone.utc)
        if record.expires_at and record.expires_at <= now:
            return None

        record.last_used_at = now
        await self.db.flush()
        return record

    async def revoke_token(self, token_id: str) -> McpClientToken:
        record = await self.get_token_by_id(token_id)
        if record is None:
            raise NotFoundError("MCP Token 不存在", "errors.mcp_gateway.token_not_found")
        if record.revoked_at is not None:
            return record
        record.revoked_at = datetime.now(timezone.utc)
        await self.db.flush()
        return record

    async def revoke_active_for_agent(self, hermes_agent_id: str) -> McpClientToken | None:
        record = await self.get_active_token(hermes_agent_id)
        if record is None or record.revoked_at is not None:
            return None
        if record.expires_at and record.expires_at <= datetime.now(timezone.utc):
            return record
        return await self.revoke_token(record.id)

    @staticmethod
    def is_expired(record: McpClientToken) -> bool:
        if record.expires_at is None:
            return False
        return record.expires_at <= datetime.now(timezone.utc)

    @staticmethod
    def is_revoked(record: McpClientToken) -> bool:
        return record.revoked_at is not None
