"""Integration tests for document upload, ingestion pipeline, chunks, and reprocessing."""

import io
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeBase
from app.services.ingestion.service import IngestionService


@pytest.fixture
async def kb_a(db_session: AsyncSession, seed_data: dict) -> KnowledgeBase:
    tenant_a = seed_data["tenant_a"]
    kb = KnowledgeBase(
        tenant_id=tenant_a.id,
        name="Company A Engineering Base",
        description="Core technical documents",
        status="ACTIVE",
    )
    db_session.add(kb)
    await db_session.commit()
    await db_session.refresh(kb)
    return kb


@pytest.mark.asyncio
async def test_document_upload_and_ingestion_flow(
    client: AsyncClient,
    db_session: AsyncSession,
    seed_data: dict,
    kb_a: KnowledgeBase,
):
    """Test full ingestion pipeline: upload -> parse -> chunk -> inspect content and chunks."""
    tenant_a = seed_data["tenant_a"]
    token_a = seed_data["token_a_owner"]
    headers = {"Authorization": f"Bearer {token_a}", "X-Tenant-ID": str(tenant_a.id)}

    # 1. Upload a markdown document
    md_content = b"# System Architecture\n\nModular monolith built with FastAPI and Next.js.\n\n## Multi-Tenancy\nStrict tenant isolation on every layer."
    files = {"files": ("architecture.md", md_content, "text/markdown")}

    upload_res = await client.post(
        f"/api/v1/knowledge/{kb_a.id}/documents",
        files=files,
        headers=headers,
    )
    assert upload_res.status_code == 201
    upload_data = upload_res.json()
    assert len(upload_data) == 1
    doc_info = upload_data[0]["document"]
    job_info = upload_data[0]["job"]
    doc_id = doc_info["id"]
    job_id = job_info["id"]
    assert upload_data[0]["is_duplicate"] is False
    assert doc_info["filename"] == "architecture.md"

    # 2. Run ingestion service execution directly on job
    service = IngestionService(db_session, tenant_a.id)
    executed_job = await service.execute_job(job_id)
    assert executed_job.status == "COMPLETED"
    assert executed_job.progress_pct == 100

    # 3. Verify Document is COMPLETED
    doc_res = await client.get(f"/api/v1/documents/{doc_id}", headers=headers)
    assert doc_res.status_code == 200
    doc_data = doc_res.json()
    assert doc_data["status"] == "COMPLETED"
    assert doc_data["total_chunks"] >= 1

    # 4. Inspect Extracted Content
    content_res = await client.get(f"/api/v1/documents/{doc_id}/content", headers=headers)
    assert content_res.status_code == 200
    content_data = content_res.json()
    assert "System Architecture" in content_data["extracted_text"]
    assert "Multi-Tenancy" in content_data["extracted_text"]

    # 5. Inspect Chunks
    chunks_res = await client.get(f"/api/v1/documents/{doc_id}/chunks", headers=headers)
    assert chunks_res.status_code == 200
    chunks_data = chunks_res.json()
    assert len(chunks_data) >= 1
    assert chunks_data[0]["document_id"] == doc_id
    assert chunks_data[0]["token_count"] > 0
    assert chunks_data[0]["chunk_hash"] is not None

    # 6. Inspect Processing History Events
    history_res = await client.get(f"/api/v1/documents/{doc_id}/processing-history", headers=headers)
    assert history_res.status_code == 200
    history_data = history_res.json()
    stages = [h["stage"] for h in history_data]
    assert "UPLOAD" in stages
    assert "PARSING" in stages
    assert "COMPLETION" in stages


@pytest.mark.asyncio
async def test_duplicate_upload_detection(
    client: AsyncClient,
    seed_data: dict,
    kb_a: KnowledgeBase,
):
    """Test duplicate upload detection in same knowledge base."""
    tenant_a = seed_data["tenant_a"]
    token_a = seed_data["token_a_owner"]
    headers = {"Authorization": f"Bearer {token_a}", "X-Tenant-ID": str(tenant_a.id)}

    content = b"Exact identical document content for duplicate testing."
    files = {"files": ("sample.txt", content, "text/plain")}

    # First upload
    res1 = await client.post(f"/api/v1/knowledge/{kb_a.id}/documents", files=files, headers=headers)
    assert res1.status_code == 201
    assert res1.json()[0]["is_duplicate"] is False

    # Second upload with same content
    files2 = {"files": ("sample_copy.txt", content, "text/plain")}
    res2 = await client.post(f"/api/v1/knowledge/{kb_a.id}/documents", files=files2, headers=headers)
    assert res2.status_code == 201
    assert res2.json()[0]["is_duplicate"] is True


@pytest.mark.asyncio
async def test_ingestion_config_management(
    client: AsyncClient,
    seed_data: dict,
    kb_a: KnowledgeBase,
):
    """Test fetching and updating KB ingestion configuration."""
    tenant_a = seed_data["tenant_a"]
    token_a = seed_data["token_a_owner"]
    headers = {"Authorization": f"Bearer {token_a}", "X-Tenant-ID": str(tenant_a.id)}

    # Get default config
    get_res = await client.get(f"/api/v1/knowledge/{kb_a.id}/ingestion-config", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["chunking_strategy"] == "recursive"

    # Patch config
    patch_payload = {
        "chunking_strategy": "markdown",
        "chunk_size": 1200,
        "chunk_overlap": 250,
        "ocr_enabled": True,
        "ocr_provider": "tesseract",
        "ocr_language": "eng",
    }
    patch_res = await client.patch(
        f"/api/v1/knowledge/{kb_a.id}/ingestion-config",
        json=patch_payload,
        headers=headers,
    )
    assert patch_res.status_code == 200
    data = patch_res.json()
    assert data["chunking_strategy"] == "markdown"
    assert data["chunk_size"] == 1200
    assert data["ocr_enabled"] is True
