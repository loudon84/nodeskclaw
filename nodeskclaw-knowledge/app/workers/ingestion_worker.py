"""Ingestion job polling worker."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import socket
import uuid

from app.core.deps import async_session_factory
from app.integrations.ragflow.client import RagflowClient
from app.services import ingestion_service, reconciliation_service

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 2.0
RECONCILIATION_EVERY_LOOPS = 30


def _lease_owner() -> str:
    return f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"


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
                job = await ingestion_service.claim_next_job(db, lease_owner=lease_owner)
                if job:
                    await ingestion_service.process_leased_job(db, ragflow, job)
                    await db.commit()
                    processed = True

            loop_count += 1
            if with_reconciliation and loop_count % RECONCILIATION_EVERY_LOOPS == 0:
                async with async_session_factory() as db:
                    await reconciliation_service.run_reconciliation(db, ragflow)
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
