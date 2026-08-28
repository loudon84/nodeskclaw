from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from app.services.connector_router import execute_connector_run
from app.services.hermes_engine import execute_hermes_run


async def execute_engine(
    *,
    engine: str,
    tool_name: str,
    arguments: dict[str, Any],
    route_snapshot: dict[str, Any],
    org_id: str | None = None,
    run_id: str | None = None,
    attempt_id: str | None = None,
    cancel_event: asyncio.Event | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Unified execution port for Hermes and Connector engines.

    Dispatches directly to adapter engines and fails-closed on unknown engine.
    """
    engine_type = (engine or "").lower().strip()
    if engine_type == "hermes":
        async for event in execute_hermes_run(
            tool_name=tool_name,
            arguments=arguments,
            route_snapshot=route_snapshot,
            org_id=org_id,
            run_id=run_id,
            attempt_id=attempt_id,
            cancel_event=cancel_event,
        ):
            yield event
    elif engine_type in ("connector", "http_connector", "mcp_connector"):
        async for event in execute_connector_run(
            tool_name=tool_name,
            arguments=arguments,
            route_snapshot=route_snapshot,
            org_id=org_id,
            cancel_event=cancel_event,
        ):
            yield event
    else:
        yield {
            "event_type": "run.failed",
            "payload": {"error": f"Unsupported engine type: {engine} (fail-closed)"},
        }
