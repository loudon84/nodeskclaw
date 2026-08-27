"""MinerU HTTP client for PDF parsing and layout extraction."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class MinerUError(RuntimeError):
    pass


class MinerUClient:
    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
        http_client: httpx.AsyncClient | None = None,
    ):
        self.base_url = (base_url or settings.MINERU_BASE_URL).rstrip("/")
        self.timeout = timeout if timeout is not None else settings.MINERU_TIMEOUT_SECONDS
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
        files: Any = None,
        retry: bool = True,
    ) -> Any:
        attempts = 3 if retry else 1
        last_exc: Exception | None = None
        client = await self._ensure_client()
        for attempt in range(attempts):
            try:
                resp = await client.request(method, path, json=json, files=files)
                if resp.status_code >= 400:
                    raise MinerUError(f"MinerU HTTP {resp.status_code}")
                if not resp.content:
                    return {}
                payload = resp.json()
                if isinstance(payload, dict) and payload.get("error"):
                    raise MinerUError(str(payload.get("error")))
                return payload
            except MinerUError:
                raise
            except (httpx.TimeoutException, TimeoutError) as exc:
                last_exc = exc
                logger.warning(
                    "MinerU request failed attempt=%s path=%s err=%s",
                    attempt + 1,
                    path,
                    type(exc).__name__,
                )
                if attempt + 1 < attempts:
                    await asyncio.sleep(0.2 * (2**attempt))
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "MinerU request failed attempt=%s path=%s err=%s",
                    attempt + 1,
                    path,
                    type(exc).__name__,
                )
                if attempt + 1 < attempts:
                    await asyncio.sleep(0.2 * (2**attempt))
        raise MinerUError(f"MinerU unavailable: {type(last_exc).__name__}") from last_exc

    async def health(self) -> bool:
        try:
            client = await self._ensure_client()
            resp = await client.get("/health", timeout=5.0)
            return resp.status_code < 400
        except Exception:
            return False

    async def extract_page_text(
        self,
        *,
        file_bytes: bytes,
        filename: str,
        page_no: int = 1,
    ) -> str:
        files = {"file": (filename, file_bytes, "application/octet-stream")}
        data = await self._request(
            "POST",
            "/api/v1/parse",
            files=files,
            json={"page_no": page_no},
        )
        if isinstance(data, dict):
            text = data.get("text") or data.get("content")
            if text is not None:
                return str(text)
        raise MinerUError("MinerU extract_page_text returned no text")
