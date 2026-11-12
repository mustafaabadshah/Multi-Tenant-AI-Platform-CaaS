"""Durable background processing recovery.

Detects orphaned background ingestion and embedding jobs interrupted by process
restarts, crashes, or unhandled terminates, safely transitioning them to a terminal
FAILED / INTERRUPTED state with actionable error metadata so they can be reviewed
and safely retried.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import TypedDict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import Document, EmbeddingJob, IngestionEvent, IngestionJob

logger = logging.getLogger("mmaip.recovery")


class RecoveryStats(TypedDict):
    recovered_ingestion_jobs: int
    recovered_embedding_jobs: int


async def recover_orphaned_jobs(session: AsyncSession) -> RecoveryStats:
    """Find all background jobs stuck in transient states on startup and recover them."""
    now = datetime.now(timezone.utc)
    recovered_ingestion = 0
    recovered_embedding = 0

    # 1. Recover IngestionJobs stuck in PROCESSING
    stmt_ingestion = select(IngestionJob).where(IngestionJob.status == "PROCESSING")
    result_ingestion = await session.execute(stmt_ingestion)
    orphaned_ingestion_jobs = result_ingestion.scalars().all()

    for job in orphaned_ingestion_jobs:
        job.status = "FAILED"
        job.stage = "INTERRUPTED"
        job.error_category = "PROCESS_RESTART"
        job.error_message = (
            "Job was interrupted by an application process restart. Safe to retry."
        )
        job.completed_at = now

        # Update associated document status if it was left in PROCESSING
        if job.document_id:
            doc = await session.get(Document, job.document_id)
            if doc and doc.status == "PROCESSING":
                doc.status = "FAILED"

        # Record audit event
        event = IngestionEvent(
            id=uuid.uuid4(),
            tenant_id=job.tenant_id,
            job_id=job.id,
            document_id=job.document_id,
            stage="PROCESS_RESTART",
            status="FAILED",
            message="Ingestion was interrupted by an application process restart. Safe to retry.",
            details={"error_category": "PROCESS_RESTART", "recovered_at": now.isoformat()},
        )
        session.add(event)
        recovered_ingestion += 1

    # 2. Recover EmbeddingJobs stuck in PROCESSING
    stmt_embedding = select(EmbeddingJob).where(EmbeddingJob.status == "PROCESSING")
    result_embedding = await session.execute(stmt_embedding)
    orphaned_embedding_jobs = result_embedding.scalars().all()

    for emb_job in orphaned_embedding_jobs:
        emb_job.status = "FAILED"
        emb_job.stage = "INTERRUPTED"
        emb_job.error_message = (
            "Embedding job was interrupted by an application process restart. Safe to retry."
        )
        emb_job.completed_at = now
        recovered_embedding += 1

    if recovered_ingestion > 0 or recovered_embedding > 0:
        await session.commit()
        logger.warning(
            f"Startup recovery complete: recovered {recovered_ingestion} orphaned ingestion jobs "
            f"and {recovered_embedding} orphaned embedding jobs."
        )

    return {
        "recovered_ingestion_jobs": recovered_ingestion,
        "recovered_embedding_jobs": recovered_embedding,
    }
