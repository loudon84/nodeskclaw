"""LLM Proxy HTTP client for Knowledge Service."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.config import settings
from app.integrations.llm_proxy.exceptions import LlmProxyError
from app.integrations.llm_proxy.models import ChatCompletionRequest, ChatCompletionResponse

logger = logging.getLogger(__name__)


# @lat: [[decisions/knowledge-ragflow-split#Llm Proxy Boundary]]
class LlmProxyClient:
    def __init__(
        self,
        base_url: str | None = None,
        service_token: str | None = None,
        provider: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ):
        self.base_url = (base_url or settings.LLM_PROXY_URL).rstrip("/")
        self.service_token = service_token if service_token is not None else settings.KNOWLEDGE_SERVICE_TOKEN
        self.provider = provider or settings.LLM_PROXY_PROVIDER
        self._http_client = http_client
        self._owns_client = http_client is None

    async def aclose(self) -> None:
        if self._owns_client and self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=120.0)
            self._owns_client = True
        return self._http_client

    def _headers(self, *, org_id: str, member_id: str, session_id: str | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.service_token}",
            "X-NoDeskClaw-Org-Id": org_id,
            "X-NoDeskClaw-Member-Id": member_id,
            "Content-Type": "application/json",
        }
        if session_id:
            headers["X-NoDeskClaw-Knowledge-Session-Id"] = session_id
        return headers

    async def chat_completions(
        self,
        request: ChatCompletionRequest,
        *,
        org_id: str,
        member_id: str,
        session_id: str | None = None,
    ) -> ChatCompletionResponse:
        client = await self._ensure_client()
        url = f"{self.base_url}/{self.provider}/v1/chat/completions"
        try:
            resp = await client.post(
                url,
                headers=self._headers(org_id=org_id, member_id=member_id, session_id=session_id),
                json=request.model_dump(exclude_none=True),
            )
        except Exception as exc:
            raise LlmProxyError(f"LLM Proxy 调用失败: {type(exc).__name__}") from exc
        if resp.status_code >= 400:
            raise LlmProxyError(f"LLM Proxy 返回 {resp.status_code}")
        return ChatCompletionResponse.model_validate(resp.json())

    async def chat_completions_stream(
        self,
        request: ChatCompletionRequest,
        *,
        org_id: str,
        member_id: str,
        session_id: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        payload = request.model_dump(exclude_none=True)
        payload["stream"] = True
        client = await self._ensure_client()
        url = f"{self.base_url}/{self.provider}/v1/chat/completions"
        try:
            async with client.stream(
                "POST",
                url,
                headers=self._headers(org_id=org_id, member_id=member_id, session_id=session_id),
                json=payload,
            ) as resp:
                if resp.status_code >= 400:
                    body = await resp.aread()
                    raise LlmProxyError(f"LLM Proxy 流式返回 {resp.status_code}: {body[:200]!r}")
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data:"):
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            yield json.loads(data)
                        except json.JSONDecodeError:
                            logger.warning("skip invalid SSE chunk")
        except LlmProxyError:
            raise
        except Exception as exc:
            raise LlmProxyError(f"LLM Proxy 流式调用失败: {type(exc).__name__}") from exc
