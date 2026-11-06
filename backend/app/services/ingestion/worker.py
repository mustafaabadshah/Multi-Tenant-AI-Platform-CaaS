"""Standalone background ingestion worker process."""

import asyncio
import logging
import signal
import sys
import uuid

from sqlalchemy import select

from app.database.session import async_session_factory
from app.models.knowledge import IngestionJob
from app.services.ingestion.service import IngestionService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("mmaip.worker")


class IngestionWorker:
    """Lightweight durable background worker polling for QUEUED ingestion jobs."""

    def __init__(self, poll_interval_seconds: float = 2.0) -> None:
        self.poll_interval = poll_interval_seconds
        self._running = False

    async def start(self) -> None:
        self._running = True
        logger.info("Ingestion Worker started. Polling for jobs...")

        while self._running:
            try:
                await self._process_next_job()
            except Exception as e:
                logger.error(f"Error in worker loop: {e}", exc_info=True)
            await asyncio.sleep(self.poll_interval)

    def stop(self) -> None:
        logger.info("Stopping Ingestion Worker...")
        self._running = False

    async def _process_next_job(self) -> None:
        async with async_session_factory() as session:
            # Pick oldest QUEUED job
            stmt = (
                select(IngestionJob)
                .where(IngestionJob.status == "QUEUED")
                .order_by(IngestionJob.created_at.asc())
                .limit(1)
            )
            res = await session.execute(stmt)
            job = res.scalars().first()

            if not job:
                return

            job_id = job.id
            tenant_id = job.tenant_id

        # Execute job in its own service context
        async with async_session_factory() as session:
            service = IngestionService(session, tenant_id)
            logger.info(f"Worker picked up job {job_id} for tenant {tenant_id}")
            await service.execute_job(job_id)


def main() -> None:
    worker = IngestionWorker()

    def handle_signal(*args: object) -> None:
        worker.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    asyncio.run(worker.start())


if __name__ == "__main__":
    main()
