"""Reconciliation worker for RAGFlow drift and delete recovery."""

from __future__ import annotations

import argparse
import asyncio
import logging

from app.core.deps import async_session_factory
from app.integrations.ragflow.client import RagflowClient
from app.services import reconciliation_service

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_SECONDS = 60.0


async def _run_loop(*, interval_seconds: float) -> None:
    ragflow = RagflowClient()
    logger.info("reconciliation worker started interval=%ss", interval_seconds)
    try:
        while True:
            async with async_session_factory() as db:
                await reconciliation_service.run_reconciliation(db, ragflow)
                await db.commit()
            await asyncio.sleep(interval_seconds)
    finally:
        await ragflow.aclose()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    parser = argparse.ArgumentParser(description="Knowledge reconciliation worker")
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL_SECONDS)
    args = parser.parse_args()
    asyncio.run(_run_loop(interval_seconds=args.interval))


if __name__ == "__main__":
    main()
