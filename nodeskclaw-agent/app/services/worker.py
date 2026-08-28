"""Central RunWorker: claim local runs, execute Hermes or connector routes.

Hybrid placement: when placement.engine == "hybrid" or snapshot.edge_jobs is set,
Hermes runs centrally first; edge connector jobs are detected via needs_edge_jobs()
but dispatch is intentionally a no-op until the Central edge-job queue is wired.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text

from app.config import settings
from app.db import SessionLocal
from app.services import run_service
from app.services.connector_router import execute_connector_run
from app.services.hermes_engine import execute_hermes_run

logger = logging.getLogger(__name__)

SCHEMA = settings.SKILL_AGENT_SCHEMA


def build_hybrid_step_plan(snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Build a deterministic list of steps (central vs edge) for hybrid execution.
    Returns:
      [
        {"step": "central_hermes", "role": "central", "engine": "hermes"},
        {"step": "edge_connector", "role": "edge", "engine": "connector", "binding_id": ...}
      ]
    """
    if not snapshot:
        return [{"step": "central", "role": "central", "engine": "hermes"}]
    
    steps: list[dict[str, Any]] = []
    placement = snapshot.get("placement") or {}
    if placement.get("role") == "hybrid" or placement.get("engine") == "hybrid":
        steps.append({"step": "central_hermes", "role": "central", "engine": "hermes"})
        policy = snapshot.get("runtime_policy") or {}
        bindings = policy.get("connector_bindings") or []
        if isinstance(bindings, dict):
            bindings = [bindings]
        for b in bindings:
            if isinstance(b, dict) and b.get("placement") == "edge":
                steps.append({
                    "step": f"edge_connector_{b.get('id') or b.get('binding_id') or 'job'}",
                    "role": "edge",
                    "engine": "connector",
                    "binding": b,
                })
    elif placement.get("role") == "edge" or placement.get("engine") == "connector":
        steps.append({"step": "edge_connector", "role": "edge", "engine": "connector"})
    else:
        steps.append({"step": "central", "role": "central", "engine": placement.get("engine", "hermes")})
    return steps


def needs_edge_jobs(snapshot: dict[str, Any] | None) -> bool:
    """True when any connector_binding in runtime_policy has placement=edge."""
    if not snapshot:
        return False
    policy = snapshot.get("runtime_policy") or {}
    bindings = policy.get("connector_bindings")
    if bindings is None:
        return False
    if isinstance(bindings, dict):
        bindings = [bindings]
    if not isinstance(bindings, list):
        return False
    for binding in bindings:
        if isinstance(binding, dict) and binding.get("placement") == "edge":
            return True
    return False


class RunWorker:
    def __init__(self) -> None:
        self._running = False
        self._worker_id = uuid.uuid4().hex[:12]

    async def start(self) -> None:
        self._running = True
        logger.info("SkillAgent RunWorker started worker_id=%s", self._worker_id)
        while self._running:
            try:
                await self._recover_stale_runs()
                claimed = await self._claim_one()
                if claimed:
                    await self._execute(claimed)
                else:
                    await asyncio.sleep(settings.SKILL_AGENT_WORKER_INTERVAL_SECONDS)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("RunWorker poll error")
                await asyncio.sleep(settings.SKILL_AGENT_WORKER_INTERVAL_SECONDS)

    def stop(self) -> None:
        self._running = False

    async def _recover_stale_runs(self) -> None:
        async with SessionLocal() as db:
            rows = (
                await db.execute(
                    text(
                        f"""
                        SELECT id, attempt_id, worker_id
                        FROM "{SCHEMA}".runs
                        WHERE status IN ('PREPARING', 'RUNNING')
                          AND lease_until < NOW()
                        FOR UPDATE SKIP LOCKED
                        """
                    )
                )
            ).mappings().all()
            for r in rows:
                run_id = r["id"]
                att_id = r["attempt_id"]
                logger.warning("recovering stale run_id=%s attempt_id=%s", run_id, att_id)
                if att_id:
                    await db.execute(
                        text(
                            f"""
                            UPDATE "{SCHEMA}".run_attempts
                            SET status = 'TIMED_OUT', completed_at = NOW(), error_message = 'lease expired'
                            WHERE id = :id AND status IN ('PREPARING', 'RUNNING')
                            """
                        ),
                        {"id": att_id},
                    )
                await db.execute(
                    text(
                        f"""
                        UPDATE "{SCHEMA}".runs
                        SET status = 'QUEUED',
                            attempt_id = NULL,
                            worker_id = NULL,
                            lease_until = NULL,
                            updated_at = NOW()
                        WHERE id = :id
                        """
                    ),
                    {"id": run_id},
                )
                await run_service.append_event(
                    db,
                    run_id,
                    "run.recovered",
                    {"reason": "lease_expired", "previous_attempt_id": att_id},
                )
            await db.commit()

    async def _claim_one(self) -> dict | None:
        lease_until = datetime.now(timezone.utc) + timedelta(seconds=settings.SKILL_AGENT_LEASE_SECONDS)
        attempt_id = str(uuid.uuid4())
        async with SessionLocal() as db:
            row = (
                await db.execute(
                    text(
                        f"""
                        SELECT id, org_id, tool_name, arguments, snapshot, status
                        FROM "{SCHEMA}".runs
                        WHERE status IN ('QUEUED', 'RESUMING')
                          AND (lease_until IS NULL OR lease_until < NOW())
                          AND (
                            snapshot->'placement'->>'role' IS NULL
                            OR snapshot->'placement'->>'role' != 'edge'
                          )
                        ORDER BY created_at ASC
                        FOR UPDATE SKIP LOCKED
                        LIMIT 1
                        """
                    )
                )
            ).mappings().first()
            if not row:
                await db.commit()
                return None

            max_attempt = (
                await db.execute(
                    text(
                        f"""
                        SELECT COALESCE(MAX(attempt_no), 0)
                        FROM "{SCHEMA}".run_attempts
                        WHERE run_id = :run_id
                        """
                    ),
                    {"run_id": row["id"]},
                )
            ).scalar_one()
            attempt_no = int(max_attempt) + 1

            await db.execute(
                text(
                    f"""
                    INSERT INTO "{SCHEMA}".run_attempts (
                        id, run_id, attempt_no, generation, worker_id, status, lease_until, started_at, heartbeat_at
                    ) VALUES (
                        :id, :run_id, :attempt_no, :attempt_no, :worker_id, 'PREPARING', :lease_until, NOW(), NOW()
                    )
                    """
                ),
                {
                    "id": attempt_id,
                    "run_id": row["id"],
                    "attempt_no": attempt_no,
                    "worker_id": self._worker_id,
                    "lease_until": lease_until,
                },
            )

            await db.execute(
                text(
                    f"""
                    UPDATE "{SCHEMA}".runs
                    SET status = 'PREPARING',
                        attempt_id = :attempt_id,
                        generation = :attempt_no,
                        worker_id = :worker_id,
                        lease_until = :lease_until,
                        updated_at = NOW()
                    WHERE id = :id
                    """
                ),
                {
                    "id": row["id"],
                    "attempt_id": attempt_id,
                    "attempt_no": attempt_no,
                    "worker_id": self._worker_id,
                    "lease_until": lease_until,
                },
            )
            await db.commit()
            return {
                "id": row["id"],
                "org_id": row.get("org_id"),
                "tool_name": row["tool_name"],
                "arguments": row["arguments"] or {},
                "snapshot": row["snapshot"] or {},
                "attempt_id": attempt_id,
                "generation": attempt_no,
            }

    async def _renew_lease(self, run_id: str, attempt_id: str, generation: int | None = None) -> bool:
        lease_until = datetime.now(timezone.utc) + timedelta(seconds=settings.SKILL_AGENT_LEASE_SECONDS)
        conditions = [
            'id = :id',
            'attempt_id = :attempt_id',
            "status IN ('PREPARING', 'RUNNING')",
        ]
        params: dict[str, Any] = {"id": run_id, "attempt_id": attempt_id, "lease_until": lease_until}
        if generation is not None:
            conditions.append('generation = :generation')
            params["generation"] = generation

        where_clause = " AND ".join(conditions)
        async with SessionLocal() as db:
            res = await db.execute(
                text(
                    f"""
                    UPDATE "{SCHEMA}".runs
                    SET lease_until = :lease_until, updated_at = NOW()
                    WHERE {where_clause}
                    """
                ),
                params,
            )
            if res.rowcount == 0:
                return False
            await db.execute(
                text(
                    f"""
                    UPDATE "{SCHEMA}".run_attempts
                    SET lease_until = :lease_until, heartbeat_at = NOW(), updated_at = NOW()
                    WHERE id = :attempt_id AND status IN ('PREPARING', 'RUNNING')
                    """
                ),
                {"attempt_id": attempt_id, "lease_until": lease_until},
            )
            await db.commit()
            return True

    async def _execute(self, claimed: dict) -> None:
        run_id = claimed["id"]
        attempt_id = claimed["attempt_id"]
        generation = claimed.get("generation")
        org_id = claimed.get("org_id")

        stop_renew = asyncio.Event()

        async def _renew_loop():
            interval = max(1.0, float(settings.SKILL_AGENT_LEASE_SECONDS) / 3.0)
            while not stop_renew.is_set():
                try:
                    await asyncio.sleep(interval)
                    if stop_renew.is_set():
                        break
                    ok = await self._renew_lease(run_id, attempt_id, generation)
                    if not ok:
                        logger.warning("failed to renew lease for run_id=%s attempt_id=%s (fenced)", run_id, attempt_id)
                        cancel_event.set()
                        break
                except Exception:
                    logger.debug("lease renew exception", exc_info=True)

        cancel_event = asyncio.Event()

        async def _cancel_check_loop():
            while not stop_renew.is_set():
                try:
                    await asyncio.sleep(1.0)
                    if stop_renew.is_set():
                        break
                    async with SessionLocal() as chk_db:
                        run_row = await run_service.get_run(chk_db, run_id, org_id=claimed.get("org_id") or "")
                        if run_row and run_row.status in ("CANCELLING", "CANCELLED"):
                            cancel_event.set()
                            break
                except Exception:
                    pass

        cancel_task = asyncio.create_task(_cancel_check_loop())
        renew_task = asyncio.create_task(_renew_loop())

        async with SessionLocal() as db:
            try:
                await run_service.set_status(
                    db,
                    run_id,
                    "RUNNING",
                    org_id=org_id,
                    attempt_id=attempt_id,
                    generation=generation,
                    expected_status=["PREPARING", "QUEUED", "RESUMING"],
                )
                await run_service.append_event(
                    db,
                    run_id,
                    "run.started",
                    {"status": "RUNNING", "attempt_id": attempt_id},
                    org_id=org_id,
                    attempt_id=attempt_id,
                    generation=generation,
                )
                await db.commit()

                snapshot = claimed["snapshot"] or {}
                route_snapshot = snapshot.get("runtime_policy") or {}
                placement = snapshot.get("placement") or {}
                org_id = snapshot.get("org_id")

                step_plan = build_hybrid_step_plan(snapshot)
                await run_service.append_event(
                    db,
                    run_id,
                    "run.plan",
                    {"step_plan": step_plan, "total_steps": len(step_plan)},
                    org_id=org_id,
                    attempt_id=attempt_id,
                    generation=generation,
                )
                await db.commit()

                if placement.get("engine") == "connector":
                    event_iter = execute_connector_run(
                        tool_name=claimed["tool_name"],
                        arguments=claimed["arguments"] or {},
                        snapshot=snapshot,
                    )
                else:
                    event_iter = execute_hermes_run(
                        tool_name=claimed["tool_name"],
                        arguments=claimed["arguments"] or {},
                        route_snapshot=route_snapshot,
                        org_id=org_id,
                        cancel_event=cancel_event,
                    )
                is_hybrid = placement.get("engine") == "hybrid" or needs_edge_jobs(snapshot)
                has_pending_edge_steps = is_hybrid and needs_edge_jobs(snapshot)

                async for event in event_iter:
                    event_type = event["event_type"]
                    payload = event.get("payload") or {}
                    source = event.get("source") or "agent"
                    source_event_id = event.get("source_event_id")
                    if event_type == "run.completed":
                        if has_pending_edge_steps:
                            # Central step completed; do not mark run as COMPLETED.
                            # Instead, transition to RUNNING/WAITING_EDGE and enqueue edge steps.
                            await run_service.append_event(
                                db,
                                run_id,
                                "run.central_step_completed",
                                payload,
                                org_id=org_id,
                                attempt_id=attempt_id,
                                generation=generation,
                                source=source,
                                source_event_id=source_event_id,
                            )
                        else:
                            await run_service.set_status(
                                db,
                                run_id,
                                "COMPLETED",
                                org_id=org_id,
                                attempt_id=attempt_id,
                                generation=generation,
                                expected_status=["RUNNING", "PREPARING", "RESUMING"],
                                result=payload,
                            )
                            await run_service.append_event(
                                db,
                                run_id,
                                "run.completed",
                                payload,
                                org_id=org_id,
                                attempt_id=attempt_id,
                                generation=generation,
                                source=source,
                                source_event_id=source_event_id,
                            )
                            content = payload.get("content")
                            if content is None:
                                content = payload.get("summary") or ""
                            raw = content if isinstance(content, (bytes, bytearray)) else str(content).encode("utf-8")
                            await run_service.store_artifact_bytes(
                                db,
                                run_id,
                                name="result.txt",
                                content=bytes(raw),
                                content_type="text/plain; charset=utf-8",
                                org_id=org_id,
                                attempt_id=attempt_id,
                                generation=generation,
                            )
                    elif event_type == "run.cancelled":
                        await run_service.set_status(
                            db,
                            run_id,
                            "CANCELLED",
                            org_id=org_id,
                            attempt_id=attempt_id,
                            generation=generation,
                            result=payload,
                        )
                        await run_service.append_event(
                            db,
                            run_id,
                            "run.cancelled",
                            payload,
                            org_id=org_id,
                            attempt_id=attempt_id,
                            generation=generation,
                            source=source,
                            source_event_id=source_event_id,
                        )
                    elif event_type == "run.failed":
                        await run_service.set_status(
                            db,
                            run_id,
                            "FAILED",
                            org_id=org_id,
                            attempt_id=attempt_id,
                            generation=generation,
                            result=payload,
                        )
                        await run_service.append_event(
                            db,
                            run_id,
                            "run.failed",
                            payload,
                            org_id=org_id,
                            attempt_id=attempt_id,
                            generation=generation,
                            source=source,
                            source_event_id=source_event_id,
                        )
                    else:
                        await run_service.append_event(
                            db,
                            run_id,
                            event_type,
                            payload,
                            org_id=org_id,
                            attempt_id=attempt_id,
                            generation=generation,
                            source=source,
                            source_event_id=source_event_id,
                        )
                    await db.commit()

                # Hybrid: after central section, dispatch edge jobs to transport port
                if has_pending_edge_steps:
                    edge_steps = [s for s in step_plan if s.get("role") == "edge"]
                    await run_service.append_event(
                        db,
                        run_id,
                        "run.edge_steps_queued",
                        {"step_plan": edge_steps},
                        org_id=org_id,
                        attempt_id=attempt_id,
                        generation=generation,
                    )
                    await db.commit()
            except Exception as exc:
                logger.exception("run execute failed run_id=%s", run_id)
                await db.rollback()
                async with SessionLocal() as err_db:
                    try:
                        await run_service.set_status(
                            err_db,
                            run_id,
                            "FAILED",
                            org_id=org_id,
                            attempt_id=attempt_id,
                            generation=generation,
                            result={"error": str(exc)[:500]},
                        )
                        await run_service.append_event(
                            err_db,
                            run_id,
                            "run.failed",
                            {"error": str(exc)[:500]},
                            org_id=org_id,
                            attempt_id=attempt_id,
                            generation=generation,
                        )
                        await err_db.commit()
                    except Exception:
                        await err_db.rollback()
                        logger.exception("failed to persist run failure run_id=%s", run_id)
            finally:
                stop_renew.set()
                renew_task.cancel()
                cancel_task.cancel()
                try:
                    await renew_task
                except asyncio.CancelledError:
                    pass
