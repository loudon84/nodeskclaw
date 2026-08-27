"""Maintenance worker — evaluation runs and reconciliation."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import socket
import uuid

from app.core.deps import async_session_factory
from app.runtime.ragflow import RagflowRuntimeAdapter
from app.services import evaluation_runner, evaluation_service, metrics_service, reconciliation_service

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 2.0
RECONCILIATION_EVERY_LOOPS = 30


def _lease_owner() -> str:
    return f"maintenance:{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"


async def _run_loop(*, with_reconciliation: bool) -> None:
    lease_owner = _lease_owner()
    ragflow = RagflowRuntimeAdapter()
    loop_count = 0
    logger.info(
        "maintenance worker started lease_owner=%s reconciliation=%s",
        lease_owner,
        with_reconciliation,
    )
    try:
        while True:
            metrics_service.observe_worker_heartbeat(worker_role="maintenance")
            processed = False
            async with async_session_factory() as db:
                claimed_eval = await evaluation_service.claim_next_evaluation_run(
                    db, lease_owner=lease_owner
                )
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
    parser = argparse.ArgumentParser(description="Knowledge maintenance worker")
    parser.add_argument(
        "--with-reconciliation",
        action="store_true",
        help="run reconciliation every N poll loops",
    )
    args = parser.parse_args()
    asyncio.run(_run_loop(with_reconciliation=args.with_reconciliation))


if __name__ == "__main__":
    main()
