from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class HermesApiResponse:
    status_code: int | None
    ok: bool
    data: dict | list | str | None
    error: str | None = None


class HermesApiServerClient:
    def __init__(self, *, base_url: str, api_key: str) -> None:
        self.base_url = str(base_url).rstrip("/")
        self.api_key = api_key

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def health(self) -> HermesApiResponse:
        return await self._get("/health", timeout_seconds=settings.HERMES_API_SERVER_PROBE_TIMEOUT_SECONDS)

    async def list_models(self) -> HermesApiResponse:
        return await self._get("/v1/models", timeout_seconds=settings.HERMES_API_SERVER_PROBE_TIMEOUT_SECONDS)

    async def get_capabilities(self) -> HermesApiResponse:
        return await self._get(
            "/v1/capabilities",
            timeout_seconds=settings.HERMES_API_SERVER_PROBE_TIMEOUT_SECONDS,
            allow_404=True,
        )

    async def chat_completions(self, payload: dict) -> HermesApiResponse:
        return await self._post(
            "/v1/chat/completions",
            payload,
            timeout_seconds=settings.HERMES_API_SERVER_CALL_TIMEOUT_SECONDS,
        )

    async def _get(self, path: str, *, timeout_seconds: int, allow_404: bool = False) -> HermesApiResponse:
        url = f"{self.base_url}{path}"
        timeout = httpx.Timeout(float(timeout_seconds))
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
                headers=self._headers(),
            ) as client:
                resp = await client.get(url)
        except httpx.TimeoutException:
            return HermesApiResponse(status_code=None, ok=False, data=None, error="timeout")
        except httpx.ConnectError:
            return HermesApiResponse(status_code=None, ok=False, data=None, error="offline")
        except Exception as exc:
            logger.debug("Hermes API GET failed %s: %s", url, exc)
            return HermesApiResponse(status_code=None, ok=False, data=None, error="offline")

        if resp.status_code in (401, 403):
            return HermesApiResponse(status_code=resp.status_code, ok=False, data=None, error="unauthorized")
        if allow_404 and resp.status_code == 404:
            return HermesApiResponse(status_code=404, ok=False, data=None, error="unsupported")
        if resp.status_code >= 400:
            return HermesApiResponse(status_code=resp.status_code, ok=False, data=None, error="invalid_response")

        try:
            return HermesApiResponse(status_code=resp.status_code, ok=True, data=resp.json(), error=None)
        except Exception:
            return HermesApiResponse(status_code=resp.status_code, ok=False, data=None, error="invalid_response")

    async def _post(self, path: str, payload: dict, *, timeout_seconds: int) -> HermesApiResponse:
        url = f"{self.base_url}{path}"
        timeout = httpx.Timeout(float(timeout_seconds))
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
                headers=self._headers(),
            ) as client:
                resp = await client.post(url, json=payload)
        except httpx.TimeoutException:
            return HermesApiResponse(status_code=None, ok=False, data=None, error="timeout")
        except httpx.ConnectError:
            return HermesApiResponse(status_code=None, ok=False, data=None, error="offline")
        except Exception as exc:
            logger.debug("Hermes API POST failed %s: %s", url, exc)
            return HermesApiResponse(status_code=None, ok=False, data=None, error="offline")

        if resp.status_code in (401, 403):
            return HermesApiResponse(status_code=resp.status_code, ok=False, data=None, error="unauthorized")
        if resp.status_code >= 400:
            return HermesApiResponse(status_code=resp.status_code, ok=False, data=None, error="invalid_response")

        try:
            return HermesApiResponse(status_code=resp.status_code, ok=True, data=resp.json(), error=None)
        except Exception:
            return HermesApiResponse(status_code=resp.status_code, ok=False, data=None, error="invalid_response")

