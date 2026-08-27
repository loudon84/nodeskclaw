"""Optional LLM planner — propose only; authorization stays deterministic."""

from __future__ import annotations

import asyncio
from typing import Any


async def propose_plan(query: str, *, timeout_seconds: float = 2.0) -> tuple[dict[str, Any] | None, bool]:
    try:
        return await asyncio.wait_for(_propose_plan_inner(query), timeout=timeout_seconds)
    except TimeoutError:
        return None, True
    except Exception:
        return None, True


async def _propose_plan_inner(query: str) -> tuple[dict[str, Any] | None, bool]:
    from app.core.config import settings

    if not settings.KNOWLEDGE_V23_LLM_PLANNER_ENABLED:
        return None, False
    lowered = query.lower()
    if any(token in lowered for token in ("graph", "关系", "图谱")):
        return {"preferred_mode": "graph_assisted", "source": "deterministic_stub"}, False
    if any(token in lowered for token in ("table", "表格")):
        return {"preferred_mode": "semantic", "artifact_types": ["table"], "source": "deterministic_stub"}, False
    return None, False
