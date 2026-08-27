"""Translation job worker — only processes TranslationJob."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import socket
import uuid

from app.core.config import settings
from app.core.deps import async_session_factory
from app.services import metrics_service, translation_service

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 2.0


def _lease_owner() -> str:
    return f"translation:{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"


async def _run_loop() -> None:
    if not settings.KNOWLEDGE_TRANSLATION_ENABLED:
        logger.warning("translation worker exiting: KNOWLEDGE_TRANSLATION_ENABLED=false")
        return
    lease_owner = _lease_owner()
    logger.info("translation worker started lease_owner=%s", lease_owner)
    while True:
        metrics_service.observe_worker_heartbeat(worker_role="translation")
        processed = False
        async with async_session_factory() as db:
            claimed = await translation_service.claim_next_translation_job(
                db, lease_owner=lease_owner
            )
            if claimed:
                tr_job, lease_token = claimed
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
        if not processed:
            await asyncio.sleep(POLL_INTERVAL_SECONDS)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    parser = argparse.ArgumentParser(description="Knowledge translation worker")
    parser.parse_args()
    asyncio.run(_run_loop())


if __name__ == "__main__":
    main()
