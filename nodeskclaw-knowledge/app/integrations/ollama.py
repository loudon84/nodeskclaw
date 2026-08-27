"""Ollama HTTP client for translation model inference."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
        model: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.timeout = timeout if timeout is not None else settings.OLLAMA_TIMEOUT_SECONDS
        self.model = model or settings.OLLAMA_TRANSLATION_MODEL
        self._http_client = http_client
        self._owns_client = http_client is None

    async def aclose(self) -> None:
        if self._owns_client and self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
            )
            self._owns_client = True
        return self._http_client

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        retry: bool = True,
    ) -> Any:
        attempts = 3 if retry else 1
        last_exc: Exception | None = None
        client = await self._ensure_client()
        for attempt in range(attempts):
            try:
                resp = await client.request(method, path, json=json)
                if resp.status_code >= 400:
                    raise OllamaError(f"Ollama HTTP {resp.status_code}")
                if not resp.content:
                    return {}
                return resp.json()
            except OllamaError:
                raise
            except (httpx.TimeoutException, TimeoutError) as exc:
                last_exc = exc
                logger.warning(
                    "Ollama request failed attempt=%s path=%s err=%s",
                    attempt + 1,
                    path,
                    type(exc).__name__,
                )
                if attempt + 1 < attempts:
                    await asyncio.sleep(0.2 * (2**attempt))
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "Ollama request failed attempt=%s path=%s err=%s",
                    attempt + 1,
                    path,
                    type(exc).__name__,
                )
                if attempt + 1 < attempts:
                    await asyncio.sleep(0.2 * (2**attempt))
        raise OllamaError(f"Ollama unavailable: {type(last_exc).__name__}") from last_exc

    async def health(self) -> bool:
        try:
            client = await self._ensure_client()
            resp = await client.get("/api/tags", timeout=5.0)
            return resp.status_code < 400
        except Exception:
            return False

    async def translate(
        self,
        *,
        text: str,
        target_lang: str,
        source_lang: str | None = None,
    ) -> str:
        prompt = f"Translate the following text to {target_lang}. Return only the translation.\n\n{text}"
        if source_lang:
            prompt = (
                f"Translate the following text from {source_lang} to {target_lang}. "
                f"Return only the translation.\n\n{text}"
            )
        data = await self._request(
            "POST",
            "/api/generate",
            json={"model": self.model, "prompt": prompt, "stream": False},
        )
        if isinstance(data, dict):
            response = data.get("response")
            if response is not None:
                return str(response).strip()
        raise OllamaError("Ollama translate returned no response")
