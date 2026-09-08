from __future__ import annotations

from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services import run_service


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
    session_db: AsyncSession | None = None,
) -> None:
    execution_context = snapshot.get("execution_context")
    context_version = snapshot.get("context_version")
    resolved_org_id = org_id or str(snapshot.get("org_id") or "")
    resolved_user_id = user_id or str(snapshot.get("user_id") or "")

    run_session_id = snapshot.get("run_session_id")
    if run_session_id and session_db is not None:
        try:
            await run_service.revalidate_run_session(
                session_db,
                run_session_id=str(run_session_id),
                org_id=resolved_org_id,
                user_id=resolved_user_id,
                context_version=int(context_version) if context_version is not None else None,
            )
        except (ValueError, httpx.HTTPError) as exc:
            raise ContextRevalidationError("run session revalidation denied") from exc

    if execution_context is None and context_version is None:
        raise ContextRevalidationError("execution context missing")
    if not isinstance(execution_context, dict) or not execution_context:
        raise ContextRevalidationError("execution context missing")
    if context_version is None:
        context_version = execution_context.get("context_version")
    if context_version is None:
        raise ContextRevalidationError("context version missing")

    central_url = (settings.SKILL_AGENT_CENTRAL_BASE_URL or "http://localhost:4510").rstrip("/")
    url = f"{central_url}/api/v1/internal/edge/skill-run/revalidate"
    headers = {
        "X-Skill-Agent-Token": settings.SKILL_AGENT_INTERNAL_TOKEN,
        "X-Exec-Org-Id": resolved_org_id,
        "Content-Type": "application/json",
    }
    payload = {
        "run_id": run_id,
        "attempt_id": attempt_id,
        "generation": generation,
        "context_version": int(context_version),
        "execution_context": execution_context,
        "user_id": resolved_user_id,
        "run_session_id": str(run_session_id) if run_session_id else None,
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=3.0)) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        raise ContextRevalidationError("context revalidation unreachable") from exc

    if response.status_code != 200:
        raise ContextRevalidationError("context revalidation denied")
