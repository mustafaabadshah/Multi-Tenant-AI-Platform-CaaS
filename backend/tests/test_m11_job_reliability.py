"""Milestone 11: durable ingestion job claim, lease, and dispatcher tests.

These tests use a file-backed SQLite database so concurrent async sessions get
separate connections and exercise the conditional UPDATE claim path. No real
LLM, embedding, OCR, or network provider is used.
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database.base import Base
from app.models.knowledge import Document, IngestionJob, KnowledgeBase, RetrievalConfig
from app.models.tenant import Tenant
from app.services.ingestion.job_queue import (
    claim_job,
    claim_next_job,
    dispatch_pending_jobs,
    recover_stale_jobs,
)
from app.services.ingestion.service import IngestionService


@pytest.fixture
async def queue_session_factory(tmp_path):
    db_path = (tmp_path / "m11_queue.db").as_posix()
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        connect_args={"timeout": 30},
    )
    async with engine.begin() as conn:
        await conn.execute(text("PRAGMA journal_mode=WAL"))
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    yield factory
    await engine.dispose()


async def _seed_job(
    session_factory,
    *,
    status: str = "QUEUED",
    doc_status: str = "QUEUED",
    started_at: datetime | None = None,
    retry_count: int = 0,
    max_retries: int = 3,
    created_at: datetime | None = None,
    with_doc: bool = True,
    vector_store: str | None = None,
):
    suffix = uuid.uuid4().hex[:12]
    async with session_factory() as session:
        tenant = Tenant(
            id=uuid.uuid4(),
            name=f"Tenant {suffix}",
            slug=f"tenant-{suffix}",
        )
        session.add(tenant)
        await session.flush()

        kb = KnowledgeBase(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            name=f"Knowledge Base {suffix}",
            status="ACTIVE",
        )
        session.add(kb)
        await session.flush()

        doc = None
        if with_doc:
            doc = Document(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                knowledge_base_id=kb.id,
                filename="m11.txt",
                safe_filename="m11.txt",
                file_path="m11/m11.txt",
                file_size=64,
                mime_type="text/plain",
                file_hash=suffix,
                status=doc_status,
            )
            session.add(doc)
            await session.flush()

        stage = {
            "QUEUED": "QUEUED",
            "PROCESSING": "PARSING",
            "CANCELLED": "CANCELLED",
            "FAILED": "FAILED",
            "COMPLETED": "COMPLETED",
        }.get(status, "PENDING")

        job = IngestionJob(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            knowledge_base_id=kb.id,
            document_id=doc.id if doc else uuid.uuid4(),
            status=status,
            stage=stage,
            progress_pct=10,
            started_at=started_at,
            retry_count=retry_count,
            max_retries=max_retries,
            job_metadata={},
        )
        if created_at is not None:
            job.created_at = created_at
        session.add(job)

        if vector_store is not None:
            session.add(
                RetrievalConfig(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    knowledge_base_id=kb.id,
                    vector_store=vector_store,
                )
            )

        await session.commit()
        return tenant.id, kb.id, doc.id if doc else None, job.id


class _CountingStorage:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.get_calls = 0

    async def get(self, tenant_id: str, path: str) -> bytes:
        self.get_calls += 1
        await asyncio.sleep(0)
        return self.payload


@pytest.mark.asyncio
async def test_claim_job_is_atomic_single_winner(queue_session_factory):
    _tenant_id, _kb_id, _doc_id, job_id = await _seed_job(queue_session_factory)

    async def attempt() -> bool:
        async with queue_session_factory() as session:
            return await claim_job(session, job_id)

    results = await asyncio.gather(attempt(), attempt())

    assert results.count(True) == 1
    assert results.count(False) == 1

    async with queue_session_factory() as session:
        job = await session.get(IngestionJob, job_id)
        assert job.status == "PROCESSING"
        assert job.started_at is not None
        assert await claim_job(session, job_id) is False

    async with queue_session_factory() as session:
        job = await session.get(IngestionJob, job_id)
        assert job.status == "PROCESSING"


@pytest.mark.asyncio
async def test_claim_next_job_never_returns_an_unclaimed_job(queue_session_factory):
    now = datetime.now(timezone.utc)
    _t1, _k1, _d1, job_one = await _seed_job(
        queue_session_factory,
        created_at=now - timedelta(seconds=2),
    )
    _t2, _k2, _d2, job_two = await _seed_job(
        queue_session_factory,
        created_at=now - timedelta(seconds=1),
    )

    async def attempt() -> uuid.UUID | None:
        async with queue_session_factory() as session:
            return await claim_next_job(session)

    results = await asyncio.gather(attempt(), attempt())
    claimed = {result for result in results if result is not None}

    assert claimed == {job_one, job_two}

    async with queue_session_factory() as session:
        jobs = (await session.execute(select(IngestionJob))).scalars().all()
        assert len(jobs) == 2
        assert all(job.status == "PROCESSING" for job in jobs)
        assert all(job.started_at is not None for job in jobs)

        # Nothing remains QUEUED, so a third claim must return None.
        assert await claim_next_job(session) is None


@pytest.mark.asyncio
async def test_recover_stale_jobs_requeues_and_fails(queue_session_factory):
    now = datetime.now(timezone.utc)

    _ta, _ka, doc_requeue, job_requeue = await _seed_job(
        queue_session_factory,
        status="PROCESSING",
        doc_status="PROCESSING",
        started_at=now - timedelta(hours=2),
        retry_count=0,
        max_retries=3,
    )
    _tb, _kb, doc_fail, job_fail = await _seed_job(
        queue_session_factory,
        status="PROCESSING",
        doc_status="PROCESSING",
        started_at=now - timedelta(hours=2),
        retry_count=3,
        max_retries=3,
    )
    _tc, _kc, doc_fresh, job_fresh = await _seed_job(
        queue_session_factory,
        status="PROCESSING",
        doc_status="PROCESSING",
        started_at=now - timedelta(seconds=5),
        retry_count=0,
        max_retries=3,
    )

    async with queue_session_factory() as session:
        stats = await recover_stale_jobs(session, lease_seconds=3600)

    assert stats == {"requeued": 1, "failed": 1, "recovered": 2}

    async with queue_session_factory() as session:
        requeued = await session.get(IngestionJob, job_requeue)
        failed = await session.get(IngestionJob, job_fail)
        fresh = await session.get(IngestionJob, job_fresh)
        requeued_doc = await session.get(Document, doc_requeue)
        failed_doc = await session.get(Document, doc_fail)
        fresh_doc = await session.get(Document, doc_fresh)

    assert requeued.status == "QUEUED"
    assert requeued.stage == "RETRY_QUEUED"
    assert requeued.retry_count == 1
    assert requeued.started_at is None
    assert requeued.completed_at is None
    assert requeued.error_category == "LEASE_EXPIRED"
    assert "lease expired" in requeued.error_message.lower()
    assert requeued.job_metadata["lease_recovery_notes"][0]["action"] == "REQUEUED"
    assert requeued_doc.status == "QUEUED"

    assert failed.status == "FAILED"
    assert failed.stage == "FAILED"
    assert failed.error_category == "LEASE_EXPIRED"
    assert failed.completed_at is not None
    assert "lease expired" in failed.error_message.lower()
    assert failed.job_metadata["lease_recovery_notes"][0]["action"] == "FAILED"
    assert failed_doc.status == "FAILED"

    assert fresh.status == "PROCESSING"
    assert fresh.started_at is not None
    assert fresh_doc.status == "PROCESSING"


@pytest.mark.asyncio
async def test_duplicate_execution_runs_pipeline_once(queue_session_factory):
    tenant_id, _kb_id, doc_id, job_id = await _seed_job(
        queue_session_factory,
        vector_store="fts",
    )
    storage = _CountingStorage(b"# Title\n\nDurable job claim test content.")

    async def run() -> IngestionJob:
        async with queue_session_factory() as session:
            service = IngestionService(session, tenant_id)
            service.storage = storage
            return await service.execute_job(job_id)

    results = await asyncio.gather(run(), run(), return_exceptions=True)
    errors = [result for result in results if isinstance(result, BaseException)]
    assert errors == []

    assert storage.get_calls == 1

    async with queue_session_factory() as session:
        job = await session.get(IngestionJob, job_id)
        doc = await session.get(Document, doc_id)
        assert job.status == "COMPLETED"
        assert job.retry_count == 0
        assert doc.status == "COMPLETED"
        assert doc.total_chunks >= 1


@pytest.mark.asyncio
async def test_processing_job_without_claim_handoff_is_not_processed(queue_session_factory):
    tenant_id, _kb_id, doc_id, job_id = await _seed_job(
        queue_session_factory,
        status="PROCESSING",
        doc_status="PROCESSING",
        started_at=datetime.now(timezone.utc),
        vector_store="fts",
    )
    storage = _CountingStorage(b"must not be processed")

    async with queue_session_factory() as session:
        service = IngestionService(session, tenant_id)
        service.storage = storage
        returned = await service.execute_job(job_id)

    assert returned.status == "PROCESSING"
    assert storage.get_calls == 0

    async with queue_session_factory() as session:
        job = await session.get(IngestionJob, job_id)
        doc = await session.get(Document, doc_id)
        assert job.status == "PROCESSING"
        assert doc.status == "PROCESSING"


@pytest.mark.asyncio
async def test_cancelled_job_is_never_claimed_or_processed(queue_session_factory):
    tenant_id, _kb_id, doc_id, job_id = await _seed_job(
        queue_session_factory,
        status="CANCELLED",
        doc_status="QUEUED",
        vector_store="fts",
    )

    async with queue_session_factory() as session:
        assert await claim_job(session, job_id) is False
        assert await claim_next_job(session) is None

    storage = _CountingStorage(b"cancelled job must not read content")
    async with queue_session_factory() as session:
        service = IngestionService(session, tenant_id)
        service.storage = storage
        returned = await service.execute_job(job_id)

    assert returned.status == "CANCELLED"
    assert storage.get_calls == 0

    async with queue_session_factory() as session:
        doc = await session.get(Document, doc_id)
        assert doc.status == "CANCELLED"


@pytest.mark.asyncio
async def test_dispatcher_processes_one_job_then_stops(queue_session_factory, monkeypatch):
    _t1, _k1, _d1, first_job = await _seed_job(queue_session_factory, with_doc=False)
    _t2, _k2, _d2, second_job = await _seed_job(queue_session_factory, with_doc=False)

    stop_event = asyncio.Event()
    executed: list[tuple[uuid.UUID, bool]] = []

    async def fake_execute(self, job_id, *, claimed: bool = False):
        executed.append((uuid.UUID(str(job_id)), claimed))
        await self.session.execute(
            update(IngestionJob)
            .where(IngestionJob.id == job_id)
            .values(status="COMPLETED", stage="COMPLETED", completed_at=datetime.now(timezone.utc))
        )
        await self.session.commit()
        stop_event.set()
        return await self.session.get(IngestionJob, job_id)

    monkeypatch.setattr(IngestionService, "execute_job", fake_execute)

    await asyncio.wait_for(
        dispatch_pending_jobs(
            queue_session_factory,
            stop_event,
            poll_seconds=0.01,
            max_concurrency=1,
        ),
        timeout=10,
    )

    assert len(executed) == 1
    processed_job_id, was_claimed = executed[0]
    assert was_claimed is True

    remaining_job_id = second_job if processed_job_id == first_job else first_job

    async with queue_session_factory() as session:
        processed = await session.get(IngestionJob, processed_job_id)
        remaining = await session.get(IngestionJob, remaining_job_id)
        assert processed.status == "COMPLETED"
        assert remaining.status == "QUEUED"
