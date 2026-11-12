"""Atomic ingestion job claim, lease recovery, and in-process dispatch.

The queue is built on the existing ``IngestionJob`` columns so no schema
migration is required:

* ``QUEUED`` -> ``PROCESSING`` happens through an atomic conditional UPDATE.
* ``started_at`` is the lease timestamp. There is no heartbeat in this
  milestone, so the lease must be sized above the longest expected job.
* ``job_metadata`` keeps an append-only (bounded) recovery note trail.

All functions are system-level queue operations. API reads and mutations stay
tenant scoped through the existing repositories.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import (
    ChunkEmbedding,
    Document,
    DocumentChunk,
    IngestionEvent,
    IngestionJob,
)

logger = logging.getLogger("mmaip.job_queue")

TERMINAL_JOB_STATUSES = frozenset({"COMPLETED", "FAILED", "CANCELLED"})
LEASE_EXPIRED_CATEGORY = "LEASE_EXPIRED"
MAX_RECOVERY_NOTES = 10
_CLAIM_SELECTION_ATTEMPTS = 10


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def sanitize_error_message(value: object, max_length: int = 1000) -> str:
    """Collapse control whitespace and cap persisted error text."""
    text = value if isinstance(value, str) else str(value)
    text = " ".join(text.split())
    return text[:max_length] if text else "Unknown error"


async def purge_failed_version_artifacts(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    document_id: uuid.UUID | None,
    document_version_id: uuid.UUID | None,
) -> int:
    """Delete chunks and embeddings produced by a terminally failed attempt.

    Only rows tied to the failed job's document version are removed; a legacy
    job without a version id only clears unversioned rows for that document.
    This is shared by the pipeline failure handler, lease recovery, and the
    dispatcher safety net so every terminal failure path is consistent.
    """
    if not document_id:
        return 0

    if document_version_id:
        version_filter = DocumentChunk.document_version_id == document_version_id
    else:
        version_filter = DocumentChunk.document_version_id.is_(None)

    chunk_filter = (
        DocumentChunk.tenant_id == tenant_id,
        DocumentChunk.document_id == document_id,
        version_filter,
    )
    chunk_ids = select(DocumentChunk.id).where(*chunk_filter)

    embedding_filter = (
        ChunkEmbedding.tenant_id == tenant_id,
        ChunkEmbedding.document_id == document_id,
    )
    if document_version_id:
        embedding_filter += (ChunkEmbedding.document_version_id == document_version_id,)
    else:
        embedding_filter += (ChunkEmbedding.document_version_id.is_(None),)
    await session.execute(delete(ChunkEmbedding).where(*embedding_filter))
    await session.execute(
        delete(ChunkEmbedding).where(
            ChunkEmbedding.tenant_id == tenant_id,
            ChunkEmbedding.document_id == document_id,
            ChunkEmbedding.chunk_id.in_(chunk_ids),
        )
    )

    chunk_result = await session.execute(delete(DocumentChunk).where(*chunk_filter))
    removed = int(chunk_result.rowcount or 0)

    remaining = await session.execute(
        select(func.count())
        .select_from(DocumentChunk)
        .where(
            DocumentChunk.tenant_id == tenant_id,
            DocumentChunk.document_id == document_id,
        )
    )
    await session.execute(
        update(Document)
        .where(
            Document.id == document_id,
            Document.tenant_id == tenant_id,
        )
        .values(total_chunks=int(remaining.scalar_one() or 0))
        .execution_options(synchronize_session=False)
    )
    return removed


def _dialect_name(session: AsyncSession) -> str:
    try:
        return session.get_bind().dialect.name
    except Exception:
        return ""


async def claim_job(session: AsyncSession, job_id: uuid.UUID) -> bool:
    """Atomically claim one QUEUED job.

    Returns ``True`` only for the caller whose conditional UPDATE changed the
    row. A ``False`` result means the job is already claimed, terminal, or does
    not exist; the caller must not process it.
    """
    result = await session.execute(
        update(IngestionJob)
        .where(IngestionJob.id == job_id, IngestionJob.status == "QUEUED")
        .values(status="PROCESSING", started_at=_utcnow())
        .execution_options(synchronize_session=False)
    )
    if result.rowcount == 1:
        await session.commit()
        return True
    await session.rollback()
    return False


async def claim_next_job(session: AsyncSession) -> uuid.UUID | None:
    """Claim and return the oldest QUEUED job, or ``None``.

    PostgreSQL uses ``SELECT ... FOR UPDATE SKIP LOCKED`` so concurrent
    claimers do not contend for the same row. SQLite ignores row locking, so
    the conditional UPDATE is retried until it either wins a row or observes
    an empty queue; a job is never returned unless this caller flipped it.
    """
    dialect = _dialect_name(session)

    for _ in range(_CLAIM_SELECTION_ATTEMPTS):
        stmt = (
            select(IngestionJob.id)
            .where(IngestionJob.status == "QUEUED")
            .order_by(IngestionJob.created_at.asc(), IngestionJob.id.asc())
            .limit(1)
        )
        if dialect == "postgresql":
            stmt = stmt.with_for_update(skip_locked=True)

        job_id = (await session.execute(stmt)).scalar_one_or_none()
        if job_id is None:
            await session.rollback()
            return None

        result = await session.execute(
            update(IngestionJob)
            .where(IngestionJob.id == job_id, IngestionJob.status == "QUEUED")
            .values(status="PROCESSING", started_at=_utcnow())
            .execution_options(synchronize_session=False)
        )
        if result.rowcount == 1:
            await session.commit()
            return job_id

        # Another claimer won the row (or a concurrent cancel changed it).
        # Release the transaction and try the next QUEUED candidate.
        await session.rollback()

    return None


def _append_recovery_note(job_metadata: dict[str, Any] | None, note: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(job_metadata or {})
    notes = list(metadata.get("lease_recovery_notes") or [])
    notes.append(note)
    metadata["lease_recovery_notes"] = notes[-MAX_RECOVERY_NOTES:]
    return metadata


async def _set_document_status(session: AsyncSession, job: IngestionJob, status: str) -> None:
    """Update the document through the ORM so identity-map callers stay fresh."""
    stmt = select(Document).where(
        Document.id == job.document_id,
        Document.tenant_id == job.tenant_id,
        Document.status.notin_(("DELETED", "CANCELLED")),
    )
    doc = (await session.execute(stmt)).scalars().first()
    if doc is not None:
        doc.status = status


async def recover_stale_jobs(session: AsyncSession, lease_seconds: int) -> dict[str, int]:
    """Recover PROCESSING jobs whose ``started_at`` lease has expired.

    ``started_at IS NULL`` is treated as stale. Every fresh claim writes
    ``started_at``, so a null value only comes from legacy/interrupted rows;
    leaving them PROCESSING forever would lock the document indefinitely.

    Returns ``{"requeued": n, "failed": m, "recovered": n + m}``.
    """
    now = _utcnow()
    cutoff = now - timedelta(seconds=max(0, int(lease_seconds)))
    stale_condition = or_(
        IngestionJob.started_at.is_(None),
        IngestionJob.started_at < cutoff,
    )

    stmt = select(IngestionJob).where(
        IngestionJob.status == "PROCESSING",
        stale_condition,
    )
    stale_jobs = list((await session.execute(stmt)).scalars().all())

    requeued = 0
    failed = 0

    for job in stale_jobs:
        note = {
            "at": now.isoformat(),
            "event": LEASE_EXPIRED_CATEGORY,
            "lease_seconds": int(lease_seconds),
            "prior_started_at": job.started_at.isoformat() if job.started_at else None,
            "retry_count": job.retry_count,
            "max_retries": job.max_retries,
        }

        if job.retry_count < job.max_retries:
            new_retry_count = job.retry_count + 1
            note["action"] = "REQUEUED"
            metadata = _append_recovery_note(job.job_metadata, note)
            result = await session.execute(
                update(IngestionJob)
                .where(
                    IngestionJob.id == job.id,
                    IngestionJob.status == "PROCESSING",
                    stale_condition,
                )
                .values(
                    status="QUEUED",
                    stage="RETRY_QUEUED",
                    progress_pct=10,
                    started_at=None,
                    completed_at=None,
                    retry_count=new_retry_count,
                    error_category=LEASE_EXPIRED_CATEGORY,
                    error_message="Processing lease expired. Job requeued for retry.",
                    job_metadata=metadata,
                )
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                continue

            # Keep the selected ORM instance (same identity map entry that
            # callers may still hold) in sync with the conditional UPDATE.
            await session.refresh(job)
            await _set_document_status(session, job, "QUEUED")
            session.add(
                IngestionEvent(
                    id=uuid.uuid4(),
                    tenant_id=job.tenant_id,
                    job_id=job.id,
                    document_id=job.document_id,
                    stage=LEASE_EXPIRED_CATEGORY,
                    status="RETRY_QUEUED",
                    message="Processing lease expired. Job requeued for retry.",
                    details={
                        "error_category": LEASE_EXPIRED_CATEGORY,
                        "lease_seconds": int(lease_seconds),
                        "retry_count": new_retry_count,
                        "max_retries": job.max_retries,
                        "recovered_at": now.isoformat(),
                    },
                )
            )
            requeued += 1
        else:
            note["action"] = "FAILED"
            metadata = _append_recovery_note(job.job_metadata, note)
            result = await session.execute(
                update(IngestionJob)
                .where(
                    IngestionJob.id == job.id,
                    IngestionJob.status == "PROCESSING",
                    stale_condition,
                )
                .values(
                    status="FAILED",
                    stage="FAILED",
                    completed_at=now,
                    error_category=LEASE_EXPIRED_CATEGORY,
                    error_message="Processing lease expired after the maximum number of retries.",
                    job_metadata=metadata,
                )
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                continue

            await session.refresh(job)
            await _set_document_status(session, job, "FAILED")
            await purge_failed_version_artifacts(
                session, job.tenant_id, job.document_id, job.document_version_id
            )
            session.add(
                IngestionEvent(
                    id=uuid.uuid4(),
                    tenant_id=job.tenant_id,
                    job_id=job.id,
                    document_id=job.document_id,
                    stage=LEASE_EXPIRED_CATEGORY,
                    status="FAILED",
                    message="Processing lease expired after the maximum number of retries.",
                    details={
                        "error_category": LEASE_EXPIRED_CATEGORY,
                        "lease_seconds": int(lease_seconds),
                        "retry_count": job.retry_count,
                        "max_retries": job.max_retries,
                        "recovered_at": now.isoformat(),
                    },
                )
            )
            failed += 1

    if requeued or failed:
        await session.commit()
        logger.warning(
            "Lease recovery complete: requeued=%s failed=%s lease_seconds=%s",
            requeued,
            failed,
            lease_seconds,
        )

    return {"requeued": requeued, "failed": failed, "recovered": requeued + failed}


async def _wait_for_stop(stop_event: asyncio.Event | None, seconds: float) -> bool:
    """Wait for the poll interval or the stop event.

    Returns ``True`` when the dispatcher may continue, ``False`` when a stop
    was requested.
    """
    if stop_event is not None and stop_event.is_set():
        return False
    if seconds <= 0:
        await asyncio.sleep(0)
        return not (stop_event is not None and stop_event.is_set())
    if stop_event is None:
        await asyncio.sleep(seconds)
        return True
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=seconds)
    except TimeoutError:
        return True
    return False


async def _ensure_recoverable(session_factory: Callable[[], Any], job_id: uuid.UUID) -> None:
    """Safety net for dispatcher-level failures outside execute_job's handler."""
    try:
        async with session_factory() as session:
            job = await session.get(IngestionJob, job_id)
            if job is None or job.status != "PROCESSING":
                return

            job.retry_count += 1
            job.error_category = "DISPATCHER_ERROR"
            job.error_message = (
                "Background execution failed unexpectedly. Job state was reconciled."
            )

            if job.retry_count <= job.max_retries:
                job.status = "QUEUED"
                job.stage = "RETRY_QUEUED"
                job.started_at = None
                job.completed_at = None
                document_status = "QUEUED"
            else:
                job.status = "FAILED"
                job.stage = "FAILED"
                job.completed_at = _utcnow()
                document_status = "FAILED"

            if job.document_id:
                await session.execute(
                    update(Document)
                    .where(
                        Document.id == job.document_id,
                        Document.tenant_id == job.tenant_id,
                        Document.status.notin_(("DELETED", "CANCELLED")),
                    )
                    .values(status=document_status)
                    .execution_options(synchronize_session=False)
                )
                if document_status == "FAILED":
                    await purge_failed_version_artifacts(
                        session, job.tenant_id, job.document_id, job.document_version_id
                    )

            await session.commit()
    except Exception:
        logger.exception("Dispatcher reconciliation failed for job %s", job_id)


async def _execute_claimed_job(session_factory: Callable[[], Any], job_id: uuid.UUID) -> None:
    try:
        async with session_factory() as session:
            job = await session.get(IngestionJob, job_id)
            if job is None:
                logger.error("Claimed ingestion job disappeared before execution: %s", job_id)
                return

            # Local import avoids a module cycle: service imports the queue
            # helpers for its own claim guard.
            from app.services.ingestion.service import IngestionService

            service = IngestionService(session, job.tenant_id)
            await service.execute_job(job_id, claimed=True)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.exception(
            "Ingestion dispatcher execution failed for job %s (%s)",
            job_id,
            type(exc).__name__,
        )
        await _ensure_recoverable(session_factory, job_id)


async def dispatch_pending_jobs(
    session_factory: Callable[[], Any],
    stop_event: asyncio.Event | None,
    poll_seconds: int,
    max_concurrency: int = 1,
) -> None:
    """Bounded in-process dispatcher for staging deployments.

    Each slot claims at most one job and executes it in a fresh session. The
    claim is atomic, so running this alongside the API task or a standalone
    worker cannot double-process a job. On ``stop_event`` the slots stop
    claiming new work and the current job is allowed to finish.
    """
    concurrency = max(1, int(max_concurrency or 1))
    interval = max(0.0, float(poll_seconds))

    async def slot() -> None:
        while True:
            if stop_event is not None and stop_event.is_set():
                return

            job_id: uuid.UUID | None = None
            try:
                async with session_factory() as session:
                    job_id = await claim_next_job(session)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Ingestion dispatcher failed to claim a job")

            if job_id is None:
                if not await _wait_for_stop(stop_event, interval):
                    return
                continue

            await _execute_claimed_job(session_factory, job_id)

    tasks = [
        asyncio.create_task(slot(), name=f"ingestion-dispatcher-{index}")
        for index in range(concurrency)
    ]
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
