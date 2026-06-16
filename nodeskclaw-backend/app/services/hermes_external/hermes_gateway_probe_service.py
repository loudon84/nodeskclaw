from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

PROBE_PATHS = ("/health", "/api/health", "/v1/health", "/")


@dataclass
class GatewayProbeResult:
    gateway_status: str
    probe_path: str | None
    status_code: int | None
    last_error: str | None
    last_probe_at: datetime


class HermesGatewayProbeService:
    def __init__(self) -> None:
        self._timeout = float(settings.HERMES_GATEWAY_PROBE_TIMEOUT_SECONDS)
        self._concurrency = max(1, settings.HERMES_GATEWAY_PROBE_CONCURRENCY)

    async def probe_url(self, gateway_url: str | None) -> GatewayProbeResult:
        now = datetime.now(timezone.utc)
        if not gateway_url:
            return GatewayProbeResult(
                gateway_status="unconfigured",
                probe_path=None,
                status_code=None,
                last_error="gateway_url missing",
                last_probe_at=now,
            )

        url = self._normalize_url(gateway_url)
        timeout = httpx.Timeout(self._timeout)
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                for path in PROBE_PATHS:
                    probe_url = url.rstrip("/") + path
                    try:
                        resp = await client.get(probe_url)
                        if resp.status_code in (401, 403):
                            return GatewayProbeResult(
                                gateway_status="unauthorized",
                                probe_path=path,
                                status_code=resp.status_code,
                                last_error="gateway unauthorized",
                                last_probe_at=now,
                            )
                        if resp.status_code in (200, 204):
                            return GatewayProbeResult(
                                gateway_status="online",
                                probe_path=path,
                                status_code=resp.status_code,
                                last_error=None,
                                last_probe_at=now,
                            )
                    except httpx.TimeoutException:
                        return GatewayProbeResult(
                            gateway_status="timeout",
                            probe_path=None,
                            status_code=None,
                            last_error="gateway probe timeout",
                            last_probe_at=now,
                        )
                    except httpx.ConnectError:
                        return GatewayProbeResult(
                            gateway_status="offline",
                            probe_path=None,
                            status_code=None,
                            last_error="gateway connection failed",
                            last_probe_at=now,
                        )
                    except Exception as exc:
                        logger.debug("gateway probe failed for %s: %s", probe_url, exc)
                        continue
        except Exception as exc:
            return GatewayProbeResult(
                gateway_status="offline",
                probe_path=None,
                status_code=None,
                last_error=str(exc),
                last_probe_at=now,
            )

        return GatewayProbeResult(
            gateway_status="invalid_response",
            probe_path=None,
            status_code=None,
            last_error="gateway probe failed",
            last_probe_at=now,
        )

    async def probe_many(self, gateway_urls: list[str | None]) -> list[GatewayProbeResult]:
        sem = asyncio.Semaphore(self._concurrency)

        async def _run(url: str | None) -> GatewayProbeResult:
            async with sem:
                return await self.probe_url(url)

        return await asyncio.gather(*[_run(url) for url in gateway_urls])

    def _normalize_url(self, gateway_url: str) -> str:
        url = gateway_url.strip()
        if os.path.exists("/.dockerenv") or settings.DOCKER_DATA_DIR:
            host = "host.docker.internal"
            url = url.replace("localhost", host).replace("127.0.0.1", host)
        return url
