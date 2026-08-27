"""Build job worker — only processes KnowledgeBuildJob."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import socket
import uuid

from app.core.config import settings
from app.core.deps import async_session_factory
from app.services import build_orchestrator, metrics_service

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 2.0


def _lease_owner() -> str:
    return f"build:{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"


async def _run_loop() -> None:
    if not settings.KNOWLEDGE_V2_BUILD_ENABLED:
        logger.warning("build worker exiting: KNOWLEDGE_V2_BUILD_ENABLED=false")
        return
    lease_owner = _lease_owner()
    logger.info("build worker started lease_owner=%s", lease_owner)
    while True:
        metrics_service.observe_worker_heartbeat(worker_role="build")
        processed = False
        async with async_session_factory() as db:
            claimed = await build_orchestrator.claim_next_build_job(db, lease_owner=lease_owner)
            if claimed:
                build_job, lease_token = claimed
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
        if not processed:
            await asyncio.sleep(POLL_INTERVAL_SECONDS)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    parser = argparse.ArgumentParser(description="Knowledge build worker")
    parser.parse_args()
    asyncio.run(_run_loop())


if __name__ == "__main__":
    main()
