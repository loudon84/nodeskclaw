"""DocuTranslate HTTP client."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class DocuTranslateError(RuntimeError):
    pass


class DocuTranslateClient:
    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
        http_client: httpx.AsyncClient | None = None,
    ):
        self.base_url = (base_url or settings.DOCUTRANSLATE_BASE_URL).rstrip("/")
        self.timeout = timeout if timeout is not None else settings.DOCUTRANSLATE_TIMEOUT_SECONDS
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
                    raise DocuTranslateError(f"DocuTranslate HTTP {resp.status_code}")
                if not resp.content:
                    return {}
                payload = resp.json()
                if isinstance(payload, dict) and payload.get("error"):
                    raise DocuTranslateError(str(payload.get("error")))
                return payload
            except DocuTranslateError:
                raise
            except (httpx.TimeoutException, TimeoutError) as exc:
                last_exc = exc
                logger.warning(
                    "DocuTranslate request failed attempt=%s path=%s err=%s",
                    attempt + 1,
                    path,
                    type(exc).__name__,
                )
                if attempt + 1 < attempts:
                    await asyncio.sleep(0.2 * (2**attempt))
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "DocuTranslate request failed attempt=%s path=%s err=%s",
                    attempt + 1,
                    path,
                    type(exc).__name__,
                )
                if attempt + 1 < attempts:
                    await asyncio.sleep(0.2 * (2**attempt))
        raise DocuTranslateError(f"DocuTranslate unavailable: {type(last_exc).__name__}") from last_exc

    async def health(self) -> bool:
        try:
            client = await self._ensure_client()
            resp = await client.get("/health", timeout=5.0)
            return resp.status_code < 400
        except Exception:
            return False

    async def translate_page(
        self,
        *,
        source_text: str,
        target_lang: str,
        source_lang: str | None = None,
        page_no: int = 1,
    ) -> str:
        body: dict[str, Any] = {
            "text": source_text,
            "target_lang": target_lang,
            "page_no": page_no,
        }
        if source_lang:
            body["source_lang"] = source_lang
        data = await self._request("POST", "/api/v1/translate/page", json=body)
        if isinstance(data, dict):
            content = data.get("translated_text") or data.get("content")
            if content is not None:
                return str(content)
        raise DocuTranslateError("DocuTranslate translate_page returned no content")

    async def get_job_progress(self, job_id: str) -> dict[str, Any]:
        data = await self._request("GET", f"/api/v1/jobs/{job_id}", retry=True)
        return data if isinstance(data, dict) else {}

    async def cancel_job(self, job_id: str) -> None:
        await self._request("POST", f"/api/v1/jobs/{job_id}/cancel", json={})
