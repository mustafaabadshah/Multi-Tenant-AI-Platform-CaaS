"""Durable background processing recovery.

Ingestion jobs are recovered through the lease-aware queue recovery routine so
interrupted work is requeued while retries remain and only becomes terminal
when the retry budget is exhausted. Embedding jobs keep the fail-on-restart
semantics because they have no lease/retry model in this milestone.
"""

import logging
from datetime import datetime, timezone
from typing import TypedDict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.knowledge import EmbeddingJob
from app.services.ingestion.job_queue import recover_stale_jobs

logger = logging.getLogger("mmaip.recovery")


class RecoveryStats(TypedDict):
    recovered_ingestion_jobs: int
    recovered_embedding_jobs: int


async def recover_orphaned_jobs(session: AsyncSession) -> RecoveryStats:
    """Recover interrupted background jobs on startup.

    Ingestion recovery is lease based: PROCESSING jobs older than
    ``INGESTION_LEASE_SECONDS`` are requeued while ``retry_count`` is below
    ``max_retries``; fresh PROCESSING jobs (for example a sibling process that
    is still working) are left untouched.
    """
    now = datetime.now(timezone.utc)

    stale_stats = await recover_stale_jobs(session, settings.INGESTION_LEASE_SECONDS)
    recovered_ingestion = stale_stats["recovered"]

    # Recover EmbeddingJobs stuck in PROCESSING. They have no retry/lease
    # columns, so an interrupted embedding run remains a manual reindex.
    stmt_embedding = select(EmbeddingJob).where(EmbeddingJob.status == "PROCESSING")
    result_embedding = await session.execute(stmt_embedding)
    orphaned_embedding_jobs = result_embedding.scalars().all()

    recovered_embedding = 0
    for emb_job in orphaned_embedding_jobs:
        emb_job.status = "FAILED"
        emb_job.stage = "INTERRUPTED"
        emb_job.error_message = (
            "Embedding job was interrupted by an application process restart. Safe to retry."
        )
        emb_job.completed_at = now
        recovered_embedding += 1

    if recovered_embedding > 0:
        await session.commit()

    if recovered_ingestion > 0 or recovered_embedding > 0:
        logger.warning(
            f"Startup recovery complete: recovered {recovered_ingestion} orphaned ingestion jobs "
            f"and {recovered_embedding} orphaned embedding jobs."
        )

    return {
        "recovered_ingestion_jobs": recovered_ingestion,
        "recovered_embedding_jobs": recovered_embedding,
    }
