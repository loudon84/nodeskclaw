"""Proxy ExternalName Service dedup helpers.

Provides shared logic for identifying physical K8s clusters and deduplicating
ExternalName Services across multiple logical cluster records.
"""

from __future__ import annotations

import hashlib
import logging

logger = logging.getLogger(__name__)

API_HASH_LABEL = "nodeskclaw/api-server-hash"
PROXY_TYPE_LABEL = "nodeskclaw/proxy-type"
PROXY_TYPE_VALUE = "inst-cluster"


def compute_api_server_hash(api_server_url: str) -> str:
    return hashlib.sha256(api_server_url.encode()).hexdigest()[:12]


async def find_proxy_svc_for_cluster(
    core_api,
    namespace: str,
    api_server_hash: str,
) -> str | None:
    """Find an existing ExternalName Service for the given physical cluster.

    Returns the service name if found, None otherwise.
    """
    svcs = await core_api.list_namespaced_service(
        namespace,
        label_selector=f"{PROXY_TYPE_LABEL}={PROXY_TYPE_VALUE},{API_HASH_LABEL}={api_server_hash}",
    )
    if svcs.items:
        return svcs.items[0].metadata.name
    return None
