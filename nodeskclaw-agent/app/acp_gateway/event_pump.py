from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.acp_gateway.event_mapping import TERMINAL_EVENTS, map_event
from app.acp_gateway.jsonrpc import notify_frame
from app.services import run_service

SendFn = Callable[[dict[str, Any]], Awaitable[None]]


async def pump_run_events(
    db: AsyncSession,
    *,
    run_id: str,
    session_id: str,
    agent_ref: str,
    org_id: str,
    after_seq: int,
    send: SendFn,
    seen_source_ids: set[str] | None = None,
    poll_seconds: float = 0.2,
    cancel_event: asyncio.Event | None = None,
) -> str:
    seen = seen_source_ids if seen_source_ids is not None else set()
    cursor = after_seq
    stop_reason = "end_turn"
    while True:
        if cancel_event is not None and cancel_event.is_set():
            return "cancelled"
        events = await run_service.list_events(db, run_id, after_seq=cursor)
        for event in events:
            cursor = max(cursor, event.event_seq)
            source_id = event.source_event_id or f"{event.run_id}:{event.event_seq}"
            if source_id in seen:
                continue
            seen.add(source_id)
            updates, mapped_stop, permission = map_event(event, agent_ref=agent_ref)
            for update in updates:
                await send(notify_frame("session/update", {"sessionId": session_id, **update}))
            if permission:
                await send(
                    {
                        "jsonrpc": "2.0",
                        "id": f"perm-{permission.get('approval_id') or event.event_seq}",
                        "method": "session/request_permission",
                        "params": {
                            "sessionId": session_id,
                            "toolCall": {
                                "toolCallId": permission.get("approval_id"),
                                "title": permission.get("summary"),
                            },
                            "options": [
                                {"optionId": "allow_once", "name": "Allow once", "kind": "allow_once"},
                                {"optionId": "reject_once", "name": "Reject", "kind": "reject_once"},
                            ],
                            "_meta": {
                                "nodeskclaw": {
                                    "approval_id": permission.get("approval_id"),
                                    "event_type": permission.get("event_type"),
                                    "run_id": run_id,
                                }
                            },
                        },
                    }
                )
            if mapped_stop:
                stop_reason = mapped_stop
            if event.event_type in TERMINAL_EVENTS:
                return stop_reason
        run = await run_service.get_run(db, run_id, org_id=org_id)
        if run and run.status in {"COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"}:
            if run.status == "CANCELLED":
                return "cancelled"
            if run.status in {"FAILED", "TIMED_OUT"}:
                return "ACP_REMOTE_RUN_FAILED"
            return stop_reason
        await asyncio.sleep(poll_seconds)
