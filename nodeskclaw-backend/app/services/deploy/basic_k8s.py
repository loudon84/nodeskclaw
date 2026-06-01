"""BasicK8sAdapter — 基础 K8s 部署适配器。

不做组织配额检查、不做专属集群覆盖。
跨集群网关代理（ExternalName Service + Proxy Ingress）按 cluster.proxy_endpoint 配置自动生效。
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.deploy.adapter import DeploymentAdapter

logger = logging.getLogger(__name__)


class BasicK8sAdapter(DeploymentAdapter):

    async def resolve_cluster(
        self,
        cluster_id: str,
        db: AsyncSession,
        org_id: str | None,
        *,
        cpu_limit: str = "0",
        mem_limit: str = "0",
        storage_size: str = "0",
    ) -> tuple[str, Any]:
        return cluster_id, None

    def build_namespace(self, slug: str, org: Any) -> str:
        return f"nodeskclaw-default-{slug}"

    def get_namespace_labels(self, org_id: str | None) -> dict[str, str] | None:
        return None

    async def setup_proxy(self, ctx: Any, ingress_host: str) -> None:
        if not ctx.proxy_endpoint:
            return
        try:
            from app.services.k8s.client_manager import GATEWAY_NS, k8s_manager
            from app.services.k8s.k8s_client import K8sClient
            from app.services.k8s.resource_builder import (
                build_external_name_service,
                build_proxy_ingress,
            )

            gateway_api = await k8s_manager.get_gateway_client()
            gateway_k8s = K8sClient(gateway_api)

            api_url = getattr(ctx, "api_server_url", None)
            svc_name: str | None = None

            if api_url:
                from app.services.k8s.proxy_helpers import (
                    compute_api_server_hash,
                    find_proxy_svc_for_cluster,
                )
                api_hash = compute_api_server_hash(api_url)
                svc_name = await find_proxy_svc_for_cluster(
                    gateway_k8s.core, GATEWAY_NS, api_hash,
                )
                if svc_name:
                    logger.info(
                        "复用已有 ExternalName Service %s（同物理集群）", svc_name,
                    )

            if not svc_name:
                ext_svc = build_external_name_service(
                    ctx.cluster_id, ctx.proxy_endpoint, api_url,
                )
                await gateway_k8s.create_or_skip(
                    gateway_k8s.core.create_namespaced_service, GATEWAY_NS, ext_svc,
                )
                svc_name = ext_svc.metadata.name

            proxy_ing = build_proxy_ingress(ctx.name, ingress_host, svc_name)
            await gateway_k8s.create_or_skip(
                gateway_k8s.networking.create_namespaced_ingress, GATEWAY_NS, proxy_ing,
            )
            logger.info(
                "已在网关集群创建代理 Ingress: %s -> %s (svc=%s)",
                ingress_host, ctx.proxy_endpoint, svc_name,
            )
        except Exception as e:
            logger.warning("创建网关代理 Ingress 失败（非致命）: %s", e)

    async def cleanup_proxy(self, ctx: Any) -> None:
        if not ctx.proxy_endpoint:
            return
        try:
            from app.services.k8s.client_manager import GATEWAY_NS, k8s_manager
            from app.services.k8s.k8s_client import K8sClient

            gateway_api = await k8s_manager.get_gateway_client()
            gateway_k8s = K8sClient(gateway_api)
            await gateway_k8s.networking.delete_namespaced_ingress(
                f"proxy-{ctx.name}", GATEWAY_NS,
            )
            logger.info("已清理网关代理 Ingress: proxy-%s", ctx.name)
        except Exception:
            logger.debug("清理网关代理 Ingress proxy-%s 失败（可能不存在）", ctx.name)

    def get_network_policy_org_id(self, org_id: str | None) -> str | None:
        return None

    def get_tls_secret(
        self, tls_secret_name: str | None, has_proxy: bool,
    ) -> str | None:
        if has_proxy:
            return None
        return tls_secret_name
