"""启动时补建缺失的 proxy Ingress + 物理集群去重（不限 CE/EE）。

查询所有活跃 K8s 实例，对配了 proxy_endpoint 的集群：
1. 按 api_server_url 分组，同物理集群使用同一 ExternalName Service
2. 修正不一致的 externalName，补充 api-server-hash label
3. 补建缺失的 proxy Ingress

网关 API 不可达时仅记 WARNING，不阻塞启动。
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

_ACTIVE_STATUSES = {"running", "learning", "restarting", "updating", "rebuilding", "restoring"}


async def reconcile_proxy_ingresses(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    try:
        await _do_reconcile(session_factory)
    except Exception:
        logger.warning("proxy Ingress 修复跳过（网关 API 不可达或其他异常）", exc_info=True)


async def _do_reconcile(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from kubernetes_asyncio import client as k8s_client

    from app.models.cluster import Cluster
    from app.models.instance import Instance
    from app.services.k8s.client_manager import GATEWAY_NS, k8s_manager
    from app.services.k8s.k8s_client import K8sClient
    from app.services.k8s.proxy_helpers import (
        API_HASH_LABEL,
        compute_api_server_hash,
    )
    from app.services.k8s.resource_builder import (
        build_external_name_service,
        build_proxy_ingress,
    )

    async with session_factory() as db:
        rows = await db.execute(
            select(Instance, Cluster)
            .join(Cluster, Instance.cluster_id == Cluster.id)
            .where(
                Instance.compute_provider == "k8s",
                Instance.ingress_domain.isnot(None),
                Instance.deleted_at.is_(None),
                Instance.status.in_(_ACTIVE_STATUSES),
                Cluster.proxy_endpoint.isnot(None),
                Cluster.proxy_endpoint != "",
                Cluster.deleted_at.is_(None),
            )
        )
        pairs: list[tuple[Any, Any]] = rows.all()

    if not pairs:
        logger.info("proxy reconcile: 无需修复的实例")
        return

    gateway_api = await k8s_manager.get_gateway_client()
    gateway_k8s = K8sClient(gateway_api)

    cluster_map: dict[str, Any] = {}
    instances_by_cluster: dict[str, list[Any]] = defaultdict(list)
    for inst, cluster in pairs:
        cluster_map[cluster.id] = cluster
        instances_by_cluster[cluster.id].append(inst)

    # --- Phase 1: group clusters by physical identity (api_server_url) ---
    physical_groups: dict[str, list[str]] = defaultdict(list)  # api_hash -> [cluster_ids]
    ungrouped: list[str] = []
    for cid, cluster in cluster_map.items():
        api_url = cluster.api_server_url
        if api_url:
            physical_groups[compute_api_server_hash(api_url)].append(cid)
        else:
            ungrouped.append(cid)

    # --- Phase 2: resolve primary ExternalName Service per physical cluster ---
    svc_name_map: dict[str, str] = {}
    patched = 0

    for api_hash, cluster_ids in physical_groups.items():
        existing_svcs: list[tuple[str, str, Any]] = []  # (svc_name, externalName, creationTS)
        for cid in cluster_ids:
            svc_candidate = f"proxy-inst-{cid[:8]}"
            try:
                svc = await gateway_k8s.core.read_namespaced_service(svc_candidate, GATEWAY_NS)
                existing_svcs.append((
                    svc.metadata.name,
                    svc.spec.external_name,
                    svc.metadata.creation_timestamp,
                ))
            except k8s_client.ApiException as e:
                if e.status != 404:
                    logger.warning("proxy reconcile: 读取 %s 失败 (status=%d)", svc_candidate, e.status)

        if existing_svcs:
            existing_svcs.sort(key=lambda x: x[2] or "")
            primary_name, primary_endpoint, _ = existing_svcs[0]

            for svc_name, ext_name, _ in existing_svcs:
                needs_patch = False
                patch_body: dict[str, Any] = {}

                if ext_name != primary_endpoint:
                    patch_body.setdefault("spec", {})["externalName"] = primary_endpoint
                    needs_patch = True
                    logger.warning(
                        "proxy reconcile: 修正 %s externalName: %s -> %s",
                        svc_name, ext_name, primary_endpoint,
                    )

                try:
                    cur_svc = await gateway_k8s.core.read_namespaced_service(svc_name, GATEWAY_NS)
                    cur_labels = cur_svc.metadata.labels or {}
                except k8s_client.ApiException:
                    cur_labels = {}

                if cur_labels.get(API_HASH_LABEL) != api_hash:
                    patch_body.setdefault("metadata", {}).setdefault("labels", {})[API_HASH_LABEL] = api_hash
                    needs_patch = True

                if needs_patch:
                    await gateway_k8s.core.patch_namespaced_service(svc_name, GATEWAY_NS, patch_body)
                    patched += 1

            for cid in cluster_ids:
                svc_name_map[cid] = primary_name
        else:
            primary_cid = cluster_ids[0]
            primary_cluster = cluster_map[primary_cid]
            ext_svc = build_external_name_service(
                primary_cid, primary_cluster.proxy_endpoint, primary_cluster.api_server_url,
            )
            await gateway_k8s.create_or_skip(
                gateway_k8s.core.create_namespaced_service, GATEWAY_NS, ext_svc,
            )
            for cid in cluster_ids:
                svc_name_map[cid] = ext_svc.metadata.name

    for cid in ungrouped:
        cluster = cluster_map[cid]
        ext_svc = build_external_name_service(cid, cluster.proxy_endpoint)
        await gateway_k8s.create_or_skip(
            gateway_k8s.core.create_namespaced_service, GATEWAY_NS, ext_svc,
        )
        svc_name_map[cid] = ext_svc.metadata.name

    # --- Phase 3: reconcile proxy Ingresses ---
    created = 0
    for cid, insts in instances_by_cluster.items():
        svc_name = svc_name_map[cid]
        for inst in insts:
            proxy_name = f"proxy-{inst.slug}"
            try:
                await gateway_k8s.networking.read_namespaced_ingress(proxy_name, GATEWAY_NS)
            except k8s_client.ApiException as e:
                if e.status == 404:
                    proxy_ing = build_proxy_ingress(inst.slug, inst.ingress_domain, svc_name)
                    await gateway_k8s.create_or_skip(
                        gateway_k8s.networking.create_namespaced_ingress, GATEWAY_NS, proxy_ing,
                    )
                    created += 1
                    logger.info("proxy reconcile: 补建 %s -> %s", proxy_name, inst.ingress_domain)
                else:
                    logger.warning("proxy reconcile: 查询 %s 失败 (status=%d)", proxy_name, e.status)

    logger.info(
        "proxy reconcile: 检查 %d 个实例，补建 %d 个 proxy Ingress，修正 %d 个 Service",
        len(pairs), created, patched,
    )
