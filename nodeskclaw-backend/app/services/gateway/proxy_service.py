import asyncio
import logging
import time
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.instance_mcp_server import InstanceMcpServer
from app.models.base import not_deleted
from app.schemas.gateway.proxy import AggregatedTool, AggregatedToolList, McpProxyResponse
from app.services.gateway.audit_service import AuditService
from app.services.gateway.policy_engine import PolicyEngine
from app.services.gateway.route_matcher import RouteMatcher
from app.services.gateway.tool_cache import ToolCache
from app.services.gateway.types import PolicyDenyReason, UpstreamTarget
from app.services.gateway.security.ssrf_guard import SSRFGuard
from app.core.exceptions import AppException

logger = logging.getLogger(__name__)


class ProxyService:
    def __init__(
        self,
        route_matcher: RouteMatcher,
        policy_engine: PolicyEngine,
        tool_cache: ToolCache,
    ) -> None:
        self._route_matcher = route_matcher
        self._policy_engine = policy_engine
        self._tool_cache = tool_cache

    async def handle_mcp_request(
        self,
        db: AsyncSession,
        *,
        method: str,
        params: dict | None,
        instance_id: str,
        org_id: str,
        user_id: str | None = None,
        tool_name: str | None = None,
        caller_ip: str | None = None,
        auth_type: str | None = None,
        auth_key_id: str | None = None,
    ) -> McpProxyResponse:
        request_id = str(uuid.uuid4())
        start_time = time.time()

        policy_result = await self._policy_engine.evaluate(
            db, org_id, instance_id, tool_name, user_id
        )

        if not policy_result.is_allowed:
            duration_ms = int((time.time() - start_time) * 1000)
            await AuditService.record(
                db,
                request_id=request_id,
                caller_user_id=user_id,
                caller_org_id=org_id,
                instance_id=instance_id,
                method=method,
                tool_name=tool_name,
                response_status="rejected",
                duration_ms=duration_ms,
                error_code=self._deny_to_error_code(policy_result.deny_reason),
                policy_id=policy_result.policy_id,
                is_default_policy=policy_result.is_default_policy,
                caller_ip=caller_ip,
                auth_type=auth_type,
                auth_key_id=auth_key_id,
            )
            return McpProxyResponse(
                id=None,
                error={
                    "code": self._deny_to_error_code(policy_result.deny_reason),
                    "message": f"Policy denied: {policy_result.deny_reason}",
                },
            )

        if method == "tools/list":
            result = await self._handle_tools_list(db, instance_id, org_id)
        elif method == "tools/call":
            result = await self._handle_tools_call(
                db, instance_id, org_id, params, policy_result.timeout_seconds
            )
        else:
            result = await self._handle_generic(
                db, instance_id, org_id, method, params, policy_result.timeout_seconds
            )

        duration_ms = int((time.time() - start_time) * 1000)
        response_status = "error" if result.error else "success"
        await AuditService.record(
            db,
            request_id=request_id,
            caller_user_id=user_id,
            caller_org_id=org_id,
            instance_id=instance_id,
            method=method,
            tool_name=tool_name,
            request_params=params,
            response_status=response_status,
            duration_ms=duration_ms,
            policy_id=policy_result.policy_id,
            is_default_policy=policy_result.is_default_policy,
        )

        return result

    async def _handle_tools_list(
        self,
        db: AsyncSession,
        instance_id: str,
        org_id: str,
    ) -> McpProxyResponse:
        async def fetcher():
            return await self._aggregate_tools(db, instance_id)

        aggregated = await self._tool_cache.get_or_fetch(f"tools:{instance_id}", fetcher)

        tools_data = [t.model_dump() for t in aggregated.tools]
        result_dict: dict = {"tools": tools_data}
        if aggregated.partial_failure:
            result_dict["partial_failure"] = True
            result_dict["unavailable_servers"] = aggregated.unavailable_servers

        return McpProxyResponse(result=result_dict)

    async def _aggregate_tools(
        self,
        db: AsyncSession,
        instance_id: str,
    ) -> AggregatedToolList:
        result = await db.execute(
            select(InstanceMcpServer).where(
                not_deleted(InstanceMcpServer),
                InstanceMcpServer.instance_id == instance_id,
                InstanceMcpServer.is_active.is_(True),
            )
        )
        servers = result.scalars().all()

        all_tools: list[AggregatedTool] = []
        unavailable: list[str] = []
        partial_failure = False

        for server in servers:
            try:
                server_tools = await self._fetch_server_tools(server)
                for t in server_tools:
                    t.source_server = server.name
                    t.source_server_id = server.id
                    all_tools.append(t)
            except Exception:
                unavailable.append(server.name)
                partial_failure = True

        return AggregatedToolList(
            tools=all_tools,
            partial_failure=partial_failure,
            unavailable_servers=unavailable,
        )

    async def _fetch_server_tools(self, server: InstanceMcpServer) -> list[AggregatedTool]:
        if not server.url:
            return []
        if not SSRFGuard.check_url(server.url):
            raise AppException(code=40310, message="上游地址 SSRF 拦截", status_code=403)
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(connect=5.0, read=10.0)) as client:
                resp = await client.post(
                    server.url,
                    json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
                )
                data = resp.json()
                tools = data.get("result", {}).get("tools", [])
                return [
                    AggregatedTool(
                        name=t.get("name", ""),
                        description=t.get("description"),
                        inputSchema=t.get("inputSchema"),
                    )
                    for t in tools
                ]
        except Exception:
            logger.warning("从 MCP Server %s 获取工具列表失败", server.name, exc_info=True)
            raise

    async def _handle_tools_call(
        self,
        db: AsyncSession,
        instance_id: str,
        org_id: str,
        params: dict | None,
        timeout_seconds: int,
    ) -> McpProxyResponse:
        targets = self._route_matcher.match(instance_id, org_id=org_id)
        if not targets:
            targets = await self._default_targets(db, instance_id)

        if not targets:
            return McpProxyResponse(
                error={"code": 50302, "message": "No available upstream server"},
            )

        target = targets[0]
        server = await self._get_server(db, target.mcp_server_id)
        if not server or not server.url:
            return McpProxyResponse(
                error={"code": 50301, "message": "Upstream server unavailable"},
            )

        return await self._forward_to_server(server, "tools/call", params, timeout_seconds)

    async def _handle_generic(
        self,
        db: AsyncSession,
        instance_id: str,
        org_id: str,
        method: str,
        params: dict | None,
        timeout_seconds: int,
    ) -> McpProxyResponse:
        targets = self._route_matcher.match(instance_id, org_id=org_id)
        if not targets:
            targets = await self._default_targets(db, instance_id)

        if not targets:
            return McpProxyResponse(
                error={"code": 50302, "message": "No available upstream server"},
            )

        target = targets[0]
        server = await self._get_server(db, target.mcp_server_id)
        if not server or not server.url:
            return McpProxyResponse(
                error={"code": 50301, "message": "Upstream server unavailable"},
            )

        return await self._forward_to_server(server, method, params, timeout_seconds)

    async def _forward_to_server(
        self,
        server: InstanceMcpServer,
        method: str,
        params: dict | None,
        timeout_seconds: int,
    ) -> McpProxyResponse:
        if server.url and not SSRFGuard.check_url(server.url):
            return McpProxyResponse(
                error={"code": 40310, "message": "上游地址 SSRF 拦截"},
            )
        connect_timeout = 5.0
        read_timeout = max(timeout_seconds - 5, 5)
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(connect=connect_timeout, read=read_timeout)) as client:
                resp = await client.post(
                    server.url,
                    json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
                )
                data = resp.json()
                return McpProxyResponse(
                    id=data.get("id"),
                    result=data.get("result"),
                    error=data.get("error"),
                )
        except asyncio.TimeoutError:
            return McpProxyResponse(
                error={"code": 50401, "message": "Gateway timeout"},
            )
        except Exception as e:
            return McpProxyResponse(
                error={"code": 50301, "message": f"Upstream error: {e}"},
            )

    async def _default_targets(
        self,
        db: AsyncSession,
        instance_id: str,
    ) -> list[UpstreamTarget]:
        result = await db.execute(
            select(InstanceMcpServer).where(
                not_deleted(InstanceMcpServer),
                InstanceMcpServer.instance_id == instance_id,
                InstanceMcpServer.is_active.is_(True),
            )
        )
        servers = result.scalars().all()
        return [
            UpstreamTarget(
                mcp_server_id=s.id,
                mcp_server_name=s.name,
                transport=s.transport,
                url=s.url,
                command=s.command,
                instance_id=instance_id,
            )
            for s in servers
        ]

    async def _get_server(
        self,
        db: AsyncSession,
        server_id: str,
    ) -> InstanceMcpServer | None:
        result = await db.execute(
            select(InstanceMcpServer).where(
                InstanceMcpServer.id == server_id,
                not_deleted(InstanceMcpServer),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _deny_to_error_code(reason: PolicyDenyReason | None) -> int:
        mapping = {
            PolicyDenyReason.ACCESS_DENIED: 40300,
            PolicyDenyReason.RATE_LIMITED: 42901,
            PolicyDenyReason.CONNECTION_LIMITED: 42902,
            PolicyDenyReason.SENSITIVE_TOOL_DENIED: 40320,
            PolicyDenyReason.APPROVAL_TIMEOUT: 40801,
        }
        return mapping.get(reason, 40300)
