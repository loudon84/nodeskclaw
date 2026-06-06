import hashlib
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gateway.gateway_audit_log import McpGatewayAuditLog
from app.services.gateway.security.param_masker import ParamMasker

logger = logging.getLogger(__name__)


class AuditService:
    @staticmethod
    async def record(
        db: AsyncSession,
        *,
        request_id: str | None = None,
        caller_user_id: str | None = None,
        caller_org_id: str | None = None,
        instance_id: str | None = None,
        mcp_server_id: str | None = None,
        method: str = "",
        tool_name: str | None = None,
        request_params: dict | None = None,
        response_status: str = "success",
        duration_ms: int | None = None,
        error_code: int | None = None,
        policy_id: str | None = None,
        is_default_policy: bool = False,
        caller_ip: str | None = None,
        auth_type: str | None = None,
        auth_key_id: str | None = None,
        security_event: str | None = None,
        sensitive_param_names: list[str] | None = None,
    ) -> None:
        params_hash = None
        params_masked = None
        if request_params:
            raw = str(sorted(request_params.items()))
            params_hash = hashlib.sha256(raw.encode()).hexdigest()
            params_masked = ParamMasker.mask_params(request_params, sensitive_param_names)

        log_entry = McpGatewayAuditLog(
            id=str(uuid.uuid4()),
            request_id=request_id or str(uuid.uuid4()),
            caller_user_id=caller_user_id,
            caller_org_id=caller_org_id,
            instance_id=instance_id,
            mcp_server_id=mcp_server_id,
            method=method,
            tool_name=tool_name,
            request_params_hash=params_hash,
            response_status=response_status,
            duration_ms=duration_ms,
            error_code=error_code,
            policy_id=policy_id,
            is_default_policy=is_default_policy,
            caller_ip=caller_ip,
            auth_type=auth_type,
            auth_key_id=auth_key_id,
            params_masked=params_masked,
            security_event=security_event,
        )
        try:
            db.add(log_entry)
            await db.flush()
        except Exception:
            logger.warning("Gateway 审计日志写入失败", exc_info=True)
