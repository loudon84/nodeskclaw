"""Central RunWorker: claim local runs, execute Hermes or connector routes.

Hybrid placement: when placement.engine == "hybrid" or snapshot.edge_jobs is set,
Hermes runs centrally first; edge connector jobs are detected via needs_edge_jobs()
but dispatch is intentionally a no-op until the Central edge-job queue is wired.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import text

from app.config import settings
from app.db import SessionLocal
from app.schemas import is_semantic_event_type
from app.services import run_service
from app.services.context_revalidate import ContextRevalidationError, revalidate_execution_context
from app.services.engine_port import execute_engine
from app.services.execution_observability import bind_from_snapshot, observe_stage, record_metric

logger = logging.getLogger(__name__)

SCHEMA = settings.SKILL_AGENT_SCHEMA


def build_hybrid_step_plan(snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Build a deterministic list of steps (central vs edge) for hybrid execution.
    Returns:
      [
        {"step_id": "central_hermes", "step": "central_hermes", "role": "central", "engine": "hermes", "required": True, "dependencies": []},
        {"step_id": "edge_connector_xxx", "step": "edge_connector_xxx", "role": "edge", "engine": "connector", "required": True, "dependencies": ["central_hermes"], ...}
      ]
    """
    if not snapshot:
        return [{"step_id": "central", "step": "central", "role": "central", "engine": "hermes", "required": True, "dependencies": []}]

    steps: list[dict[str, Any]] = []
    placement = snapshot.get("placement") or {}
    if placement.get("role") == "hybrid" or placement.get("engine") == "hybrid":
        central_step_id = "central_hermes"
        steps.append({
            "step_id": central_step_id,
            "step": central_step_id,
            "role": "central",
            "engine": "hermes",
            "required": True,
            "dependencies": [],
        })
        policy = snapshot.get("runtime_policy") or {}
        bindings = policy.get("connector_bindings") or []
        if isinstance(bindings, dict):
            bindings = [bindings]
        for b in bindings:
            if isinstance(b, dict) and b.get("placement") == "edge":
                binding_id = str(b.get("id") or b.get("binding_id") or "job")
                step_id = f"edge_connector_{binding_id}"
                steps.append({
                    "step_id": step_id,
                    "step": step_id,
                    "role": "edge",
                    "engine": "connector",
                    "required": True,
                    "dependencies": [central_step_id],
                    "binding": b,
                })
    elif placement.get("role") == "edge" or (
        placement.get("engine") == "connector" and placement.get("role") != "central"
    ):
        steps.append({
            "step_id": "edge_connector",
            "step": "edge_connector",
            "role": "edge",
            "engine": "connector",
            "required": True,
            "dependencies": [],
        })
    else:
        steps.append({
            "step_id": "central",
            "step": "central",
            "role": "central",
            "engine": placement.get("engine", "hermes"),
            "required": True,
            "dependencies": [],
        })
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


def build_edge_step_snapshot(snapshot: dict[str, Any] | None, edge_step: dict[str, Any]) -> dict[str, Any]:
    binding = edge_step.get("binding") or {}
    edge_node_id = binding.get("edge_node_id") or binding.get("node_id")
    prepared = {
        "placement": {"role": "edge", "engine": "connector", "edge_node_id": edge_node_id},
        "runtime_policy": {
            "connector_kind": binding.get("connector_kind"),
            "connector_config": dict(binding.get("connector_config") or {}),
            "connector_secret_ref_id": binding.get("connector_secret_ref_id"),
            "network_policy": dict(binding.get("network_policy") or {}),
        },
    }
    if snapshot:
        for key in ("org_id", "user_id", "request_trace_id", "run_session_id", "execution_context", "context_version"):
            if key in snapshot:
                prepared[key] = snapshot[key]
    return prepared


class RunWorker:
    def __init__(self) -> None:
        self._running = False
        self._worker_id = uuid.uuid4().hex[:12]
        self.last_loop_at: datetime | None = None
        self.last_successful_loop_at: datetime | None = None

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
                self.last_loop_at = datetime.now(timezone.utc)
                self.last_successful_loop_at = datetime.now(timezone.utc)
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

            # Also recover and attempt aggregation for WAITING_EDGE / CANCELLING runs
            waiting_rows = (
                await db.execute(
                    text(
                        f"""
                        SELECT id, org_id, status
                        FROM "{SCHEMA}".runs
                        WHERE status IN ('WAITING_EDGE', 'CANCELLING')
                        ORDER BY updated_at ASC
                        LIMIT 50
                        """
                    )
                )
            ).mappings().all()
            for wr in waiting_rows:
                try:
                    await run_service.aggregate_run_terminal(db, wr["id"], org_id=wr["org_id"])
                except Exception:
                    logger.debug("recovering WAITING_EDGE / CANCELLING run %s failed", wr["id"], exc_info=True)
            if rows:
                observe_stage("recover", outcome="ok", role="central")
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
            snapshot = row["snapshot"] or {}
            placement = snapshot.get("placement") or {}
            role = str(placement.get("role") or "central")
            bind_from_snapshot(
                snapshot,
                run_id=row["id"],
                attempt_id=attempt_id,
                generation=attempt_no,
            )
            record_metric("runs_claimed_total", labels={"role": role, "outcome": "ok"})
            observe_stage("claim", outcome="ok", role=role)
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
                record_metric("lease_renew_total", labels={"outcome": "fenced"})
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
            record_metric("lease_renew_total", labels={"outcome": "ok"})
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

        snapshot = claimed["snapshot"] or {}
        placement = snapshot.get("placement") or {}
        engine_name = str(placement.get("engine") or "hermes")
        if engine_name == "hybrid":
            engine_name = "hermes"
        bind_from_snapshot(
            snapshot,
            run_id=run_id,
            attempt_id=attempt_id,
            generation=generation,
        )
        observe_stage("execute", outcome="started", engine=engine_name)
        execute_started = time.monotonic()
        execute_outcome = "ok"

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
                user_id = snapshot.get("user_id")

                await revalidate_execution_context(
                    snapshot=snapshot,
                    run_id=run_id,
                    attempt_id=attempt_id,
                    generation=generation,
                    org_id=org_id,
                    user_id=user_id,
                    session_db=db,
                )

                step_plan = build_hybrid_step_plan(snapshot)
                await run_service.persist_step_plan(
                    db,
                    run_id,
                    step_plan,
                    org_id=org_id,
                    attempt_id=attempt_id,
                    run_generation=generation or 0,
                )
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

                central_step_id = "central_hermes" if any(s.get("step_id") == "central_hermes" for s in step_plan) else "central"
                await run_service.update_step_state(
                    db,
                    run_id,
                    central_step_id,
                    "RUNNING",
                    attempt_id=attempt_id,
                    run_generation=generation,
                )
                await db.commit()

                engine_name = str(placement.get("engine") or "hermes")
                if engine_name == "hybrid":
                    engine_name = "hermes"

                event_iter = execute_engine(
                    engine=engine_name,
                    tool_name=claimed["tool_name"],
                    arguments=claimed["arguments"] or {},
                    route_snapshot=route_snapshot if engine_name == "hermes" else snapshot,
                    org_id=org_id,
                    run_id=run_id,
                    attempt_id=attempt_id,
                    cancel_event=cancel_event,
                )
                is_hybrid = placement.get("engine") == "hybrid" or needs_edge_jobs(snapshot)
                has_pending_edge_steps = is_hybrid and needs_edge_jobs(snapshot)

                async for event in event_iter:
                    event_type = event["event_type"]
                    payload = event.get("payload") or {}
                    source = event.get("source") or "agent"
                    source_event_id = event.get("source_event_id")
                    if is_semantic_event_type(event_type):
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
                    elif event_type == "run.completed":
                        await run_service.update_step_state(
                            db,
                            run_id,
                            central_step_id,
                            "SUCCEEDED",
                            attempt_id=attempt_id,
                            run_generation=generation,
                            result=payload,
                        )
                        if has_pending_edge_steps:
                            # Central step completed; do not mark run as COMPLETED.
                            # Instead, transition to WAITING_EDGE and enqueue edge steps via Backend internal API.
                            await run_service.set_status(
                                db,
                                run_id,
                                "WAITING_EDGE",
                                org_id=org_id,
                                attempt_id=attempt_id,
                                generation=generation,
                                expected_status=["RUNNING", "PREPARING", "RESUMING"],
                            )
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
                            await run_service.append_event(
                                db,
                                run_id,
                                "run.waiting_edge",
                                {"status": "WAITING_EDGE", "attempt_id": attempt_id},
                                org_id=org_id,
                                attempt_id=attempt_id,
                                generation=generation,
                            )
                        else:
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
                            await run_service.aggregate_run_terminal(
                                db,
                                run_id,
                                org_id=org_id,
                                attempt_id=attempt_id,
                                generation=generation,
                            )
                    elif event_type == "run.cancelled":
                        await run_service.update_step_state(
                            db,
                            run_id,
                            central_step_id,
                            "CANCELLED",
                            attempt_id=attempt_id,
                            run_generation=generation,
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
                        await run_service.aggregate_run_terminal(
                            db,
                            run_id,
                            org_id=org_id,
                            attempt_id=attempt_id,
                            generation=generation,
                        )
                    elif event_type == "run.failed":
                        await run_service.update_step_state(
                            db,
                            run_id,
                            central_step_id,
                            "FAILED",
                            attempt_id=attempt_id,
                            run_generation=generation,
                            error_message=str(payload.get("error") or "central engine failed"),
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
                        await run_service.aggregate_run_terminal(
                            db,
                            run_id,
                            org_id=org_id,
                            attempt_id=attempt_id,
                            generation=generation,
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
                    await revalidate_execution_context(
                        snapshot=snapshot,
                        run_id=run_id,
                        attempt_id=attempt_id,
                        generation=generation,
                        org_id=org_id,
                        user_id=user_id,
                        session_db=db,
                    )
                    edge_steps = [s for s in step_plan if s.get("role") == "edge"]
                    dispatched_jobs = []
                    central_url = (settings.SKILL_AGENT_CENTRAL_BASE_URL or "http://localhost:4510").rstrip("/")
                    enqueue_url = f"{central_url}/api/v1/internal/edge/jobs/enqueue"
                    req_headers = {
                        "X-Skill-Agent-Token": settings.SKILL_AGENT_INTERNAL_TOKEN,
                        "X-Exec-Org-Id": org_id or "",
                    }

                    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as http_client:
                        for edge_step in edge_steps:
                            step_id = edge_step.get("step_id") or edge_step.get("step")
                            binding = edge_step.get("binding") or {}
                            edge_node_id = binding.get("edge_node_id") or binding.get("node_id") or snapshot.get("edge_node_id") or "default-edge-node"
                            idempotency_key = f"{run_id}:{attempt_id}:{generation}:{step_id}"

                            enqueue_payload = {
                                "edge_node_id": edge_node_id,
                                "run_id": run_id,
                                "attempt_id": attempt_id,
                                "step_id": step_id,
                                "run_generation": generation or 1,
                                "request_trace_id": snapshot.get("request_trace_id"),
                                "tool_name": claimed["tool_name"],
                                "arguments": claimed["arguments"] or {},
                                "snapshot": snapshot,
                                "idempotency_key": idempotency_key,
                            }
                            try:
                                resp = await http_client.post(enqueue_url, headers=req_headers, json=enqueue_payload)
                                resp.raise_for_status()
                                job_data = resp.json().get("data") or {}
                                edge_job_id = job_data.get("job_id")
                                dispatched_jobs.append({"step_id": step_id, "job_id": edge_job_id, "status": job_data.get("status")})
                                await run_service.update_step_state(
                                    db,
                                    run_id,
                                    step_id,
                                    "DISPATCHED",
                                    edge_job_id=edge_job_id,
                                    attempt_id=attempt_id,
                                    run_generation=generation,
                                )
                            except Exception as exc:
                                logger.error("failed to enqueue edge step %s for run_id=%s: %s", step_id, run_id, exc)
                                raise RuntimeError(f"Edge job enqueue failed for step {step_id}: {exc}") from exc

                    await run_service.append_event(
                        db,
                        run_id,
                        "run.edge_steps_queued",
                        {"step_plan": edge_steps, "dispatched_jobs": dispatched_jobs},
                        org_id=org_id,
                        attempt_id=attempt_id,
                        generation=generation,
                    )
                    await db.commit()
            except ContextRevalidationError as exc:
                execute_outcome = "error"
                logger.warning("context revalidation denied run_id=%s: %s", run_id, exc)
                await db.rollback()
                async with SessionLocal() as err_db:
                    snap_ctx = (claimed.get("snapshot") or {}).get("context_version")
                    try:
                        await run_service.set_status(
                            err_db,
                            run_id,
                            "FAILED",
                            org_id=org_id,
                            attempt_id=attempt_id,
                            generation=generation,
                            result={"error": "context revalidation denied"},
                        )
                        await run_service.append_event(
                            err_db,
                            run_id,
                            "run.failed",
                            {"error": "context revalidation denied", "reason": "context_revalidation_denied"},
                            org_id=org_id,
                            attempt_id=attempt_id,
                            generation=generation,
                            context_version=snap_ctx,
                        )
                        await err_db.commit()
                    except Exception:
                        await err_db.rollback()
                        logger.exception("failed to persist context revalidation failure run_id=%s", run_id)
            except Exception as exc:
                execute_outcome = "error"
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
                record_metric(
                    "run_execute_seconds",
                    labels={"engine": engine_name, "outcome": execute_outcome},
                    observe_seconds=time.monotonic() - execute_started,
                )
                observe_stage("execute", outcome=execute_outcome, engine=engine_name)
                stop_renew.set()
                renew_task.cancel()
                cancel_task.cancel()
                try:
                    await renew_task
                except asyncio.CancelledError:
                    pass
