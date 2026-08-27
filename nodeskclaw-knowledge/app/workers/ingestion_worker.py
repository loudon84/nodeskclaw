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
from app.services import ingestion_service, metrics_service

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 2.0
_TERMINAL_JOB_STATUSES = {
    "active",
    "failed",
    "cancelled",
}


def _lease_owner() -> str:
    return f"ingestion:{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"


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
async def _run_loop() -> None:
    lease_owner = _lease_owner()
    ragflow = RagflowClient()
    logger.info("ingestion worker started lease_owner=%s", lease_owner)
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

            if not processed:
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
    finally:
        await ragflow.aclose()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    parser = argparse.ArgumentParser(description="Knowledge ingestion worker")
    parser.parse_args()
    asyncio.run(_run_loop())


if __name__ == "__main__":
    main()
