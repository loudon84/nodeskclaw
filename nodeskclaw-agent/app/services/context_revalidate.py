from __future__ import annotations

from typing import Any

import httpx

from app.config import settings


class ContextRevalidationError(RuntimeError):
    pass


async def revalidate_execution_context(
    *,
    snapshot: dict[str, Any],
    run_id: str,
    attempt_id: str | None,
    generation: int | None,
    org_id: str | None,
    user_id: str | None,
) -> None:
    execution_context = snapshot.get("execution_context")
    if not isinstance(execution_context, dict) or not execution_context:
        return

    context_version = snapshot.get("context_version")
    if context_version is None:
        context_version = execution_context.get("context_version")
    if context_version is None:
        return

    central_url = (settings.SKILL_AGENT_CENTRAL_BASE_URL or "http://localhost:4510").rstrip("/")
    url = f"{central_url}/api/v1/internal/edge/skill-run/revalidate"
    headers = {
        "X-Skill-Agent-Token": settings.SKILL_AGENT_INTERNAL_TOKEN,
        "X-Exec-Org-Id": org_id or str(snapshot.get("org_id") or ""),
        "Content-Type": "application/json",
    }
    payload = {
        "run_id": run_id,
        "attempt_id": attempt_id,
        "generation": generation,
        "context_version": int(context_version),
        "execution_context": execution_context,
        "user_id": user_id or str(snapshot.get("user_id") or ""),
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=3.0)) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        raise ContextRevalidationError("context revalidation unreachable") from exc

    if response.status_code != 200:
        raise ContextRevalidationError("context revalidation denied")
