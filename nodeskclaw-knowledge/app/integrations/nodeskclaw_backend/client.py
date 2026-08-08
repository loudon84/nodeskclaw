"""Backend knowledge-context client."""

from __future__ import annotations

import logging

import httpx

from app.core.config import settings
from app.core.exceptions import BackendUnavailableError, ForbiddenError, NotFoundError
from app.schemas.principal import KnowledgePrincipal

logger = logging.getLogger(__name__)


class NodeskclawBackendClient:
    def __init__(self, base_url: str | None = None, path: str | None = None):
        self.base_url = (base_url or settings.NODESKCLAW_BACKEND_URL).rstrip("/")
        self.path = path or settings.NODESKCLAW_KNOWLEDGE_CONTEXT_PATH

    async def fetch_knowledge_context(self, bearer_token: str) -> KnowledgePrincipal:
        url = f"{self.base_url}{self.path}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers={"Authorization": f"Bearer {bearer_token}"})
        except Exception as exc:
            logger.warning("knowledge-context call failed: %s", type(exc).__name__)
            raise BackendUnavailableError() from exc

        if resp.status_code == 401:
            raise ForbiddenError(message="认证失败", message_key="errors.auth.token_invalid")
        if resp.status_code == 403:
            raise ForbiddenError()
        if resp.status_code == 404:
            raise NotFoundError(message="组织上下文不存在", message_key="errors.org.user_has_no_org")
        if resp.status_code >= 500:
            raise BackendUnavailableError()
        if resp.status_code >= 400:
            payload = resp.json() if resp.content else {}
            raise ForbiddenError(
                message=str(payload.get("message") or "无法获取知识上下文"),
                message_key=str(payload.get("message_key") or "errors.knowledge.forbidden"),
            )

        payload = resp.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            raise BackendUnavailableError(message="Backend 返回格式异常")
        return KnowledgePrincipal.model_validate(data)
