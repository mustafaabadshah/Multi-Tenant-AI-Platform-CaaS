"""Tests for Stage 5: Durable Background Processing & Recovery.

Verifies:
1. Orphaned ingestion jobs in PROCESSING on process crash/restart are recovered to FAILED
   with error_category=PROCESS_RESTART and error_message indicating application process restart.
2. Associated documents are safely transitioned out of PROCESSING to FAILED.
3. IngestionEvents are created to maintain auditability.
4. Orphaned embedding jobs in PROCESSING are recovered.
5. Recovered jobs can be safely retried via POST /api/v1/ingestion/jobs/{id}/retry.
6. In-flight jobs can be cancelled via POST /api/v1/ingestion/jobs/{id}/cancel.
7. Cross-tenant isolation prevents Tenant B from retrying or cancelling Tenant A's jobs.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import Document, EmbeddingJob, IngestionEvent, IngestionJob, KnowledgeBase
from app.services.ingestion.recovery import recover_orphaned_jobs


@pytest.fixture
async def kb_test(db_session: AsyncSession, seed_data: dict) -> KnowledgeBase:
    tenant_a = seed_data["tenant_a"]
    kb = KnowledgeBase(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        name="Recovery Test Knowledge Base",
        description="Testing background recovery",
        status="ACTIVE",
    )
    db_session.add(kb)
    await db_session.commit()
    await db_session.refresh(kb)
    return kb


@pytest.mark.asyncio
async def test_orphaned_ingestion_job_recovery(
    db_session: AsyncSession,
    seed_data: dict,
    kb_test: KnowledgeBase,
):
    """Test that jobs interrupted during execution are cleanly transitioned on recovery."""
    tenant_a = seed_data["tenant_a"]

    # 1. Seed a document stuck in PROCESSING
    doc = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb_test.id,
        filename="stuck_file.txt",
        safe_filename="stuck_file.txt",
        file_path="uploads/stuck_file.txt",
        file_hash="hash_123",
        file_size=1024,
        mime_type="text/plain",
        status="PROCESSING",
    )
    db_session.add(doc)

    # 2. Seed an ingestion job stuck in PROCESSING (simulating mid-flight crash)
    job = IngestionJob(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb_test.id,
        document_id=doc.id,
        status="PROCESSING",
        stage="CHUNKING",
        progress_pct=60,
    )
    db_session.add(job)
    await db_session.commit()

    # 3. Execute recovery routine
    stats = await recover_orphaned_jobs(db_session)
    assert stats["recovered_ingestion_jobs"] >= 1

    # 4. Verify job transition
    await db_session.refresh(job)
    assert job.status == "FAILED"
    assert job.stage == "INTERRUPTED"
    assert job.error_category == "PROCESS_RESTART"
    assert "interrupted by an application process restart" in job.error_message.lower()
    assert job.completed_at is not None

    # 5. Verify document transition
    await db_session.refresh(doc)
    assert doc.status == "FAILED"

    # 6. Verify audit event
    stmt = (
        select(IngestionEvent)
        .where(IngestionEvent.job_id == job.id)
        .order_by(IngestionEvent.created_at.desc())
    )
    res = await db_session.execute(stmt)
    events = res.scalars().all()
    assert len(events) >= 1
    recovery_event = events[0]
    assert recovery_event.stage == "PROCESS_RESTART"
    assert recovery_event.status == "FAILED"
    assert "restart" in recovery_event.message.lower()


@pytest.mark.asyncio
async def test_orphaned_embedding_job_recovery(
    db_session: AsyncSession,
    seed_data: dict,
    kb_test: KnowledgeBase,
):
    """Test that embedding jobs stuck in PROCESSING are recovered on restart."""
    tenant_a = seed_data["tenant_a"]

    emb_job = EmbeddingJob(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb_test.id,
        status="PROCESSING",
        stage="EMBEDDING",
        total_chunks=100,
        processed_chunks=45,
    )
    db_session.add(emb_job)
    await db_session.commit()

    # Run recovery
    stats = await recover_orphaned_jobs(db_session)
    assert stats["recovered_embedding_jobs"] >= 1

    await db_session.refresh(emb_job)
    assert emb_job.status == "FAILED"
    assert emb_job.stage == "INTERRUPTED"
    assert "interrupted by an application process restart" in emb_job.error_message.lower()
    assert emb_job.completed_at is not None


@pytest.mark.asyncio
async def test_retry_recovered_ingestion_job(
    client: AsyncClient,
    db_session: AsyncSession,
    seed_data: dict,
    kb_test: KnowledgeBase,
):
    """Test that a recovered/interrupted job can be retried via the retry endpoint."""
    tenant_a = seed_data["tenant_a"]
    token_a = seed_data["token_a_owner"]
    headers = {"Authorization": f"Bearer {token_a}", "X-Tenant-ID": str(tenant_a.id)}

    doc = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb_test.id,
        filename="retry_test.txt",
        safe_filename="retry_test.txt",
        file_path="uploads/retry_test.txt",
        file_hash="hash_retry_456",
        file_size=512,
        mime_type="text/plain",
        status="FAILED",
    )
    db_session.add(doc)

    job = IngestionJob(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb_test.id,
        document_id=doc.id,
        status="FAILED",
        stage="INTERRUPTED",
        error_category="PROCESS_RESTART",
        error_message="Job was interrupted by an application process restart. Safe to retry.",
    )
    db_session.add(job)
    await db_session.commit()

    # Request retry
    retry_res = await client.post(
        f"/api/v1/ingestion/jobs/{job.id}/retry",
        headers=headers,
    )
    assert retry_res.status_code == 200
    data = retry_res.json()
    assert data["status"] == "QUEUED"
    assert data["stage"] == "QUEUED"
    assert data["error_category"] is None
    assert data["error_message"] is None

    # Check document status
    await db_session.refresh(doc)
    assert doc.status == "QUEUED"


@pytest.mark.asyncio
async def test_cancel_running_ingestion_job(
    client: AsyncClient,
    db_session: AsyncSession,
    seed_data: dict,
    kb_test: KnowledgeBase,
):
    """Test that an active/queued job can be explicitly cancelled."""
    tenant_a = seed_data["tenant_a"]
    token_a = seed_data["token_a_owner"]
    headers = {"Authorization": f"Bearer {token_a}", "X-Tenant-ID": str(tenant_a.id)}

    doc = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb_test.id,
        filename="cancel_test.txt",
        safe_filename="cancel_test.txt",
        file_path="uploads/cancel_test.txt",
        file_hash="hash_cancel_789",
        file_size=256,
        mime_type="text/plain",
        status="PROCESSING",
    )
    db_session.add(doc)

    job = IngestionJob(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb_test.id,
        document_id=doc.id,
        status="QUEUED",
        stage="QUEUED",
        progress_pct=10,
    )
    db_session.add(job)
    await db_session.commit()

    # Cancel job
    cancel_res = await client.post(
        f"/api/v1/ingestion/jobs/{job.id}/cancel",
        headers=headers,
    )
    assert cancel_res.status_code == 200
    data = cancel_res.json()
    assert data["status"] == "CANCELLED"
    assert data["stage"] == "CANCELLED"

    await db_session.refresh(job)
    assert job.status == "CANCELLED"


@pytest.mark.asyncio
async def test_cross_tenant_isolation_on_recovery_and_ingestion(
    client: AsyncClient,
    db_session: AsyncSession,
    seed_data: dict,
    kb_test: KnowledgeBase,
):
    """Test that Tenant B cannot read, retry, or cancel Tenant A's ingestion jobs."""
    tenant_a = seed_data["tenant_a"]
    tenant_b = seed_data["tenant_b"]
    token_b = seed_data["token_b_owner"]
    headers_b = {"Authorization": f"Bearer {token_b}", "X-Tenant-ID": str(tenant_b.id)}

    doc = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb_test.id,
        filename="secret_a.txt",
        safe_filename="secret_a.txt",
        file_path="uploads/secret_a.txt",
        file_hash="hash_secret_a",
        file_size=128,
        mime_type="text/plain",
        status="FAILED",
    )
    db_session.add(doc)

    job = IngestionJob(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb_test.id,
        document_id=doc.id,
        status="FAILED",
        stage="INTERRUPTED",
        error_category="PROCESS_RESTART",
        error_message="Job was interrupted.",
    )
    db_session.add(job)
    await db_session.commit()

    # 1. Tenant B attempts to get job details -> 404
    get_res = await client.get(f"/api/v1/ingestion/jobs/{job.id}", headers=headers_b)
    assert get_res.status_code == 404

    # 2. Tenant B attempts to retry job -> 404
    retry_res = await client.post(f"/api/v1/ingestion/jobs/{job.id}/retry", headers=headers_b)
    assert retry_res.status_code == 404

    # 3. Tenant B attempts to cancel job -> 404
    cancel_res = await client.post(f"/api/v1/ingestion/jobs/{job.id}/cancel", headers=headers_b)
    assert cancel_res.status_code == 404
