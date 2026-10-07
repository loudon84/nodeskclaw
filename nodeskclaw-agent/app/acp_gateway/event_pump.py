from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.acp_gateway.assistant_reconciler import AssistantReconciler
from app.acp_gateway.errors import AcpGatewayError
from app.acp_gateway.event_mapping import TERMINAL_EVENTS, map_event
from app.acp_gateway.jsonrpc import notify_frame
from app.services import run_service
from app.services.execution_observability import record_metric

SendFn = Callable[[dict[str, Any]], Awaitable[None]]


async def _restore_reconciler(
    db: AsyncSession,
    *,
    run_id: str,
    agent_ref: str,
    after_seq: int,
    reconciler: AssistantReconciler,
    seen: set[str],
) -> None:
    if after_seq <= 0:
        return
    events = await run_service.list_events(db, run_id, after_seq=0)
    for event in events:
        if event.event_seq > after_seq:
            break
        source_id = event.source_event_id or f"{event.run_id}:{event.event_seq}"
        seen.add(source_id)
        map_event(event, agent_ref=agent_ref, reconciler=reconciler, silent=True)


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
    reconciler = AssistantReconciler()
    await _restore_reconciler(
        db,
        run_id=run_id,
        agent_ref=agent_ref,
        after_seq=after_seq,
        reconciler=reconciler,
        seen=seen,
    )
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
            try:
                updates, mapped_stop, permission = map_event(
                    event, agent_ref=agent_ref, reconciler=reconciler
                )
            except AcpGatewayError as exc:
                if exc.error_code == "ACP_STREAM_RECONCILIATION_MISMATCH":
                    record_metric(
                        "remote_acp_reconciliation_total",
                        labels={"outcome": "mismatch"},
                    )
                raise
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
            if event.event_type in TERMINAL_EVENTS or (
                event.event_type == "clarify.requested" and mapped_stop == "end_turn"
            ):
                if stop_reason in {
                    "ACP_REMOTE_RUN_FAILED",
                    "ACP_RUNTIME_SESSION_BINDING_MISSING",
                }:
                    raise AcpGatewayError(stop_reason, "remote run failed")
                if event.event_type in {"run.completed", "run.cancelled"} or (
                    event.event_type == "clarify.requested" and mapped_stop == "end_turn"
                ):
                    record_metric(
                        "remote_acp_reconciliation_total",
                        labels={"outcome": "ok"},
                    )
                return stop_reason
        run = await run_service.get_run(db, run_id, org_id=org_id)
        if run and run.status in {"COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"}:
            if run.status == "CANCELLED":
                return "cancelled"
            if run.status in {"FAILED", "TIMED_OUT"}:
                raise AcpGatewayError("ACP_REMOTE_RUN_FAILED", "remote run failed")
            return stop_reason
        await asyncio.sleep(poll_seconds)
