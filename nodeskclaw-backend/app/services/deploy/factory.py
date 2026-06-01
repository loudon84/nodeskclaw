"""DeploymentAdapter 工厂 — 根据 edition 返回对应适配器。"""

from __future__ import annotations

import logging
from functools import lru_cache

from app.services.deploy.adapter import DeploymentAdapter

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_deploy_adapter() -> DeploymentAdapter:
    from app.core.feature_gate import feature_gate

    if feature_gate.is_ee:
        try:
            from ee.backend.services.deploy.full_k8s import FullK8sAdapter
            return FullK8sAdapter()
        except Exception:
            logger.warning("FullK8sAdapter 加载失败，回退到 BasicK8sAdapter", exc_info=True)

    from app.services.deploy.basic_k8s import BasicK8sAdapter
    return BasicK8sAdapter()
