import hashlib
import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gateway.gateway_api_key import McpGatewayApiKey
from app.models.base import not_deleted

logger = logging.getLogger(__name__)


@dataclass
class ApiKeyAuthResult:
    is_valid: bool
    org_id: str | None = None
    api_key_id: str | None = None
    error_code: int | None = None
    error_message: str | None = None


class ApiKeyAuth:
    @staticmethod
    async def authenticate(db: AsyncSession, api_key_value: str) -> ApiKeyAuthResult:
        try:
            key_hash = hashlib.sha256(api_key_value.encode()).hexdigest()
            key_prefix = api_key_value[:8]
        except Exception:
            return ApiKeyAuthResult(is_valid=False, error_code=40102, error_message="API Key 格式无效")

        try:
            result = await db.execute(
                select(McpGatewayApiKey).where(
                    not_deleted(McpGatewayApiKey),
                    McpGatewayApiKey.key_hash == key_hash,
                    McpGatewayApiKey.key_prefix == key_prefix,
                    McpGatewayApiKey.is_active.is_(True),
                )
            )
            api_key = result.scalar_one_or_none()
        except Exception:
            logger.exception("API Key 认证服务不可用，fail-closed 拒绝")
            return ApiKeyAuthResult(is_valid=False, error_code=50303, error_message="认证服务不可用")

        if api_key is None:
            return ApiKeyAuthResult(is_valid=False, error_code=40102, error_message="API Key 无效")

        if api_key.status == "revoked":
            return ApiKeyAuthResult(is_valid=False, error_code=40103, error_message="API Key 已吊销")

        api_key.last_used_at = api_key_value
        await db.flush()

        return ApiKeyAuthResult(is_valid=True, org_id=api_key.org_id, api_key_id=api_key.id)
