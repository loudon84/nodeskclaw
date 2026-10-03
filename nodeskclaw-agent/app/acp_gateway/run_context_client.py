from __future__ import annotations

from typing import Any

import httpx

from app.acp_gateway.errors import AcpGatewayError
from app.config import settings


async def fetch_run_context(
    *,
    capability: str,
    body: dict[str, Any],
    trace_id: str,
) -> dict[str, Any]:
    url = f"{settings.SKILL_AGENT_CENTRAL_BASE_URL.rstrip('/')}/api/v1/internal/remote-acp/run-context"
    headers = {
        "X-Skill-Agent-Token": settings.SKILL_AGENT_INTERNAL_TOKEN,
        "X-NodeSkClaw-Execution-Capability": capability,
        "X-Trace-Id": trace_id,
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
            response = await client.post(url, json=body, headers=headers)
    except httpx.HTTPError as exc:
        raise AcpGatewayError("ACP_RUNTIME_UNAVAILABLE", "run context unavailable") from exc
    if response.status_code in (401, 403):
        raise AcpGatewayError("ACP_CONTEXT_REVALIDATION_DENIED", "execution context denied")
    if response.status_code == 404:
        raise AcpGatewayError("ACP_RESOURCE_DENIED", "resource not found")
    if response.status_code >= 400:
        payload = {}
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        code = str(payload.get("error_code") or "ACP_RUNTIME_UNAVAILABLE")
        raise AcpGatewayError(code, str(payload.get("message") or "run context failed"))
    data = response.json()
    if not isinstance(data, dict):
        raise AcpGatewayError("ACP_RUNTIME_UNAVAILABLE", "invalid run context")
    return data.get("data") if isinstance(data.get("data"), dict) else data
