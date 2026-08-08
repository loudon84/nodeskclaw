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
        import time

        from app.services import metrics_service

        client = await self._ensure_client()
        url = f"{self.base_url}/{self.provider}/v1/chat/completions"
        started = time.perf_counter()
        try:
            resp = await client.post(
                url,
                headers=self._headers(org_id=org_id, member_id=member_id, session_id=session_id),
                json=request.model_dump(exclude_none=True),
            )
        except Exception as exc:
            metrics_service.observe_llm_request(
                status="error",
                duration_seconds=time.perf_counter() - started,
            )
            raise LlmProxyError(f"LLM Proxy 调用失败: {type(exc).__name__}") from exc
        if resp.status_code >= 400:
            metrics_service.observe_llm_request(
                status="error",
                duration_seconds=time.perf_counter() - started,
            )
            raise LlmProxyError(f"LLM Proxy 返回 {resp.status_code}")
        parsed = ChatCompletionResponse.model_validate(resp.json())
        usage = parsed.usage
        metrics_service.observe_llm_request(
            status="ok",
            duration_seconds=time.perf_counter() - started,
            prompt_tokens=int(usage.prompt_tokens) if usage else 0,
            completion_tokens=int(usage.completion_tokens) if usage else 0,
        )
        return parsed

    async def chat_completions_stream(
        self,
        request: ChatCompletionRequest,
        *,
        org_id: str,
        member_id: str,
        session_id: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        import time

        from app.services import metrics_service

        payload = request.model_dump(exclude_none=True)
        payload["stream"] = True
        client = await self._ensure_client()
        url = f"{self.base_url}/{self.provider}/v1/chat/completions"
        started = time.perf_counter()
        prompt_tokens = 0
        completion_tokens = 0
        status = "ok"
        try:
            async with client.stream(
                "POST",
                url,
                headers=self._headers(org_id=org_id, member_id=member_id, session_id=session_id),
                json=payload,
            ) as resp:
                if resp.status_code >= 400:
                    body = await resp.aread()
                    status = "error"
                    raise LlmProxyError(f"LLM Proxy 流式返回 {resp.status_code}: {body[:200]!r}")
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data:"):
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError:
                            logger.warning("skip invalid SSE chunk")
                            continue
                        usage = chunk.get("usage") if isinstance(chunk, dict) else None
                        if isinstance(usage, dict):
                            prompt_tokens = int(usage.get("prompt_tokens") or prompt_tokens)
                            completion_tokens = int(usage.get("completion_tokens") or completion_tokens)
                        yield chunk
        except LlmProxyError:
            status = "error"
            raise
        except Exception as exc:
            status = "error"
            raise LlmProxyError(f"LLM Proxy 流式调用失败: {type(exc).__name__}") from exc
        finally:
            metrics_service.observe_llm_request(
                status=status,
                duration_seconds=time.perf_counter() - started,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
