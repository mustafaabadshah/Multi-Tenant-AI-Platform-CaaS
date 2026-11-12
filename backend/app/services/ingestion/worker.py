"""Standalone background ingestion worker process.

Jobs are claimed atomically through ``claim_next_job`` before execution, so
multiple worker processes (or a worker plus the API dispatcher) cannot process
the same job. A startup lease sweep requeues jobs abandoned by a previous
worker process.
"""

import asyncio
import logging
import signal

from app.core.config import settings
from app.database.session import async_session_factory
from app.models.knowledge import IngestionJob
from app.services.ingestion.job_queue import claim_next_job, recover_stale_jobs
from app.services.ingestion.service import IngestionService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("mmaip.worker")


class IngestionWorker:
    """Durable worker polling for and atomically claiming QUEUED ingestion jobs."""

    def __init__(self, poll_interval_seconds: float | None = None) -> None:
        self.poll_interval = (
            poll_interval_seconds
            if poll_interval_seconds is not None
            else float(settings.INGESTION_DISPATCHER_POLL_SECONDS)
        )
        self._running = False

    async def start(self) -> None:
        self._running = True
        logger.info("Ingestion Worker started. Polling for jobs...")

        try:
            async with async_session_factory() as session:
                stats = await recover_stale_jobs(session, settings.INGESTION_LEASE_SECONDS)
                if stats["recovered"]:
                    logger.warning("Worker startup lease recovery: %s", stats)
        except Exception:
            logger.exception("Worker startup lease recovery failed")

        while self._running:
            try:
                await self._process_next_job()
            except Exception:
                logger.exception("Error in worker loop")
            await asyncio.sleep(self.poll_interval)

    def stop(self) -> None:
        logger.info("Stopping Ingestion Worker after the current job...")
        self._running = False

    async def _process_next_job(self) -> None:
        async with async_session_factory() as session:
            job_id = await claim_next_job(session)

        if job_id is None:
            return

        async with async_session_factory() as session:
            job = await session.get(IngestionJob, job_id)
            if job is None:
                logger.error("Claimed ingestion job disappeared before execution: %s", job_id)
                return

            service = IngestionService(session, job.tenant_id)
            logger.info("Worker claimed job %s for tenant %s", job_id, job.tenant_id)
            await service.execute_job(job_id, claimed=True)


def main() -> None:
    worker = IngestionWorker()

    def handle_signal(*args: object) -> None:
        # Let the loop finish the in-flight job and exit cleanly. A hard
        # process death leaves a PROCESSING lease that startup recovery handles.
        worker.stop()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    asyncio.run(worker.start())


if __name__ == "__main__":
    main()
