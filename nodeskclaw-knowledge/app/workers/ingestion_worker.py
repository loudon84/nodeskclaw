"""Ingestion job polling worker with Job Leasing v2."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import socket
import uuid

from app.core.deps import async_session_factory
from app.integrations.ragflow.client import RagflowClient
from app.services import evaluation_runner, evaluation_service, ingestion_service, metrics_service, reconciliation_service
from app.core.config import settings

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 2.0
RECONCILIATION_EVERY_LOOPS = 30
_TERMINAL_JOB_STATUSES = {
    "active",
    "failed",
    "cancelled",
}


def _lease_owner() -> str:
    return f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"


def _observe_job_metrics(job) -> None:
    if job.status not in _TERMINAL_JOB_STATUSES:
        return
    duration = None
    if job.finished_at is not None and getattr(job, "created_at", None) is not None:
        try:
            duration = (job.finished_at - job.created_at).total_seconds()
        except Exception:
            duration = None
    metrics_service.observe_ingestion_job(status=job.status, duration_seconds=duration)


# @lat: [[knowledge#Ingestion Worker]]
async def _run_loop(*, with_reconciliation: bool) -> None:
    lease_owner = _lease_owner()
    ragflow = RagflowClient()
    loop_count = 0
    logger.info("ingestion worker started lease_owner=%s reconciliation=%s", lease_owner, with_reconciliation)
    try:
        while True:
            processed = False
            async with async_session_factory() as db:
                claimed = await ingestion_service.claim_next_job(db, lease_owner=lease_owner)
                if claimed:
                    job, lease_token = claimed
                    await ingestion_service.process_leased_job(
                        db,
                        ragflow,
                        job,
                        lease_owner=lease_owner,
                        lease_token=lease_token,
                    )
                    owned = await ingestion_service.finalize_leased_job(
                        db,
                        job,
                        lease_owner=lease_owner,
                        lease_token=lease_token,
                    )
                    if owned:
                        _observe_job_metrics(job)
                    else:
                        logger.warning("lease stolen, discard mutations job_id=%s", job.id)
                    processed = True

            async with async_session_factory() as db:
                claimed_eval = await evaluation_service.claim_next_evaluation_run(db, lease_owner=lease_owner)
                if claimed_eval:
                    eval_run, lease_token = claimed_eval
                    await evaluation_runner.process_evaluation_run(db, ragflow, eval_run)
                    owned = await evaluation_service.finalize_evaluation_run(
                        db,
                        eval_run,
                        lease_owner=lease_owner,
                        lease_token=lease_token,
                    )
                    if not owned:
                        logger.warning("evaluation lease stolen run_id=%s", eval_run.id)
                    processed = True

            if settings.KNOWLEDGE_V2_BUILD_ENABLED:
                from app.services import build_orchestrator

                async with async_session_factory() as db:
                    claimed_build = await build_orchestrator.claim_next_build_job(
                        db, lease_owner=lease_owner
                    )
                    if claimed_build:
                        build_job, lease_token = claimed_build
                        await build_orchestrator.process_build_job(db, build_job)
                        owned = await build_orchestrator.finalize_build_job(
                            db,
                            build_job,
                            lease_owner=lease_owner,
                            lease_token=lease_token,
                        )
                        if not owned:
                            logger.warning("build lease stolen job_id=%s", build_job.id)
                        processed = True

            if settings.KNOWLEDGE_TRANSLATION_ENABLED:
                from app.services import translation_service

                async with async_session_factory() as db:
                    claimed_tr = await translation_service.claim_next_translation_job(
                        db, lease_owner=lease_owner
                    )
                    if claimed_tr:
                        tr_job, lease_token = claimed_tr
                        await translation_service.process_translation_job(db, tr_job)
                        owned = await translation_service.finalize_translation_job(
                            db,
                            tr_job,
                            lease_owner=lease_owner,
                            lease_token=lease_token,
                        )
                        if not owned:
                            logger.warning("translation lease stolen job_id=%s", tr_job.id)
                        processed = True

            loop_count += 1
            if with_reconciliation and loop_count % RECONCILIATION_EVERY_LOOPS == 0:
                async with async_session_factory() as db:
                    await reconciliation_service.run_reconciliation(db, ragflow)
                    from app.services import connector_reconciliation_service

                    await connector_reconciliation_service.reconcile_connector_links(db)
                    await db.commit()

            if not processed:
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
    finally:
        await ragflow.aclose()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    parser = argparse.ArgumentParser(description="Knowledge ingestion worker")
    parser.add_argument(
        "--with-reconciliation",
        action="store_true",
        help="run reconciliation every N poll loops",
    )
    args = parser.parse_args()
    asyncio.run(_run_loop(with_reconciliation=args.with_reconciliation))


if __name__ == "__main__":
    main()
