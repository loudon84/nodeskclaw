import logging
import time
from collections import deque
from threading import Lock

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gateway.gateway_policy import McpGatewayPolicy
from app.models.base import not_deleted
from app.services.gateway.types import PolicyDenyReason, PolicyResult

logger = logging.getLogger(__name__)

_SCOPE_PRIORITY = {"tool": 4, "instance": 3, "org": 2, "global": 1}


class PolicyEngine:
    def __init__(self) -> None:
        self._rate_limit_lock = Lock()
        self._rate_limit_counters: dict[str, deque] = {}

    async def evaluate(
        self,
        db: AsyncSession,
        org_id: str,
        instance_id: str,
        tool_name: str | None = None,
        user_id: str | None = None,
    ) -> PolicyResult:
        policy = await self._find_policy(db, org_id, instance_id, tool_name)
        if policy is None:
            return PolicyResult(
                is_allowed=True,
                is_default_policy=True,
                timeout_seconds=30,
                retry_count=0,
            )

        if tool_name and tool_name in (policy.sensitive_tools or []):
            return PolicyResult(
                is_allowed=False,
                deny_reason=PolicyDenyReason.SENSITIVE_TOOL_DENIED,
                policy_id=policy.id,
                sensitive_tools=policy.sensitive_tools or [],
            )

        if policy.rate_limit_rpm is not None:
            limit_key = f"{org_id}:{instance_id}:{tool_name or '_all'}"
            if not self._check_rate_limit(limit_key, policy.rate_limit_rpm):
                return PolicyResult(
                    is_allowed=False,
                    deny_reason=PolicyDenyReason.RATE_LIMITED,
                    policy_id=policy.id,
                    rate_limit_rpm=policy.rate_limit_rpm,
                )

        return PolicyResult(
            is_allowed=True,
            timeout_seconds=policy.timeout_seconds,
            retry_count=policy.retry_count,
            rate_limit_rpm=policy.rate_limit_rpm,
            max_connections=policy.max_connections,
            sensitive_tools=policy.sensitive_tools or [],
            policy_id=policy.id,
        )

    async def _find_policy(
        self,
        db: AsyncSession,
        org_id: str,
        instance_id: str,
        tool_name: str | None,
    ) -> McpGatewayPolicy | None:
        candidates = []
        if tool_name:
            candidates.append(("tool", tool_name))
        candidates.append(("instance", instance_id))
        candidates.append(("org", org_id))
        candidates.append(("global", None))

        for scope, ref_id in candidates:
            query = (
                select(McpGatewayPolicy)
                .where(
                    not_deleted(McpGatewayPolicy),
                    McpGatewayPolicy.is_active.is_(True),
                    McpGatewayPolicy.org_id == org_id,
                    McpGatewayPolicy.scope == scope,
                )
            )
            if ref_id is not None:
                query = query.where(McpGatewayPolicy.scope_ref_id == ref_id)
            else:
                query = query.where(McpGatewayPolicy.scope_ref_id.is_(None))
            result = await db.execute(query)
            policy = result.scalar_one_or_none()
            if policy:
                return policy

        return None

    def _check_rate_limit(self, key: str, rpm: int) -> bool:
        now = time.time()
        window = 60.0
        with self._rate_limit_lock:
            if key not in self._rate_limit_counters:
                self._rate_limit_counters[key] = deque()
            counter = self._rate_limit_counters[key]
            while counter and counter[0] < now - window:
                counter.popleft()
            if len(counter) >= rpm:
                return False
            counter.append(now)
            return True
