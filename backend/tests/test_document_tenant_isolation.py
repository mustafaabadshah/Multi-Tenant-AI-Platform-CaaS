"""Negative security tests verifying strict multi-tenant isolation for documents, chunks, and ingestion jobs."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeBase
from app.services.ingestion.service import IngestionService
from app.storage.local import LocalStorageProvider


@pytest.fixture
async def kb_tenant_a(db_session: AsyncSession, seed_data: dict) -> KnowledgeBase:
    tenant_a = seed_data["tenant_a"]
    kb = KnowledgeBase(
        tenant_id=tenant_a.id,
        name="Confidential Company A Knowledge Base",
        description="Internal trade secrets and documentation",
        status="ACTIVE",
    )
    db_session.add(kb)
    await db_session.commit()
    await db_session.refresh(kb)
    return kb


@pytest.mark.asyncio
async def test_cross_tenant_document_access_denied(
    client: AsyncClient,
    db_session: AsyncSession,
    seed_data: dict,
    kb_tenant_a: KnowledgeBase,
):
    """Verify that Tenant B cannot access, read, reprocess, or delete Tenant A's documents."""
    tenant_a = seed_data["tenant_a"]
    tenant_b = seed_data["tenant_b"]
    token_a = seed_data["token_a_owner"]
    token_b = seed_data["token_b_owner"]

    headers_a = {"Authorization": f"Bearer {token_a}", "X-Tenant-ID": str(tenant_a.id)}
    headers_b = {"Authorization": f"Bearer {token_b}", "X-Tenant-ID": str(tenant_b.id)}

    # 1. Tenant A uploads a document
    doc_content = b"Confidential business strategy for Company A."
    files = {"files": ("strategy.txt", doc_content, "text/plain")}

    upload_res = await client.post(
        f"/api/v1/knowledge/{kb_tenant_a.id}/documents",
        files=files,
        headers=headers_a,
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()[0]["document"]["id"]
    job_id = upload_res.json()[0]["job"]["id"]

    # Process job so chunks exist
    service = IngestionService(db_session, tenant_a.id)
    await service.execute_job(job_id)

    # 2. Tenant B attempts to read Tenant A's document details -> MUST BE 404
    b_get_res = await client.get(f"/api/v1/documents/{doc_id}", headers=headers_b)
    assert b_get_res.status_code == 404
    assert "not found" in b_get_res.json()["detail"].lower()

    # 3. Tenant B attempts to read Tenant A's extracted content -> MUST BE 404
    b_content_res = await client.get(f"/api/v1/documents/{doc_id}/content", headers=headers_b)
    assert b_content_res.status_code == 404

    # 4. Tenant B attempts to read Tenant A's chunks -> MUST BE 404
    b_chunks_res = await client.get(f"/api/v1/documents/{doc_id}/chunks", headers=headers_b)
    assert b_chunks_res.status_code == 404

    # 5. Tenant B attempts to reprocess Tenant A's document -> MUST BE 404
    b_reprocess_res = await client.post(f"/api/v1/documents/{doc_id}/reprocess", headers=headers_b)
    assert b_reprocess_res.status_code == 404

    # 6. Tenant B attempts to delete Tenant A's document -> MUST BE 404
    b_del_res = await client.delete(f"/api/v1/documents/{doc_id}", headers=headers_b)
    assert b_del_res.status_code == 404

    # 7. Tenant B attempts to view Tenant A's ingestion job -> MUST BE 404
    b_job_res = await client.get(f"/api/v1/ingestion/jobs/{job_id}", headers=headers_b)
    assert b_job_res.status_code == 404

    # 8. Tenant B attempts to upload into Tenant A's knowledge base -> MUST BE 404
    files_b = {"files": ("hack.txt", b"evil", "text/plain")}
    b_upload_res = await client.post(
        f"/api/v1/knowledge/{kb_tenant_a.id}/documents",
        files=files_b,
        headers=headers_b,
    )
    assert b_upload_res.status_code == 404


@pytest.mark.asyncio
async def test_storage_path_traversal_prevention(tmp_path):
    """Verify LocalStorageProvider detects and strictly blocks path traversal attacks."""
    provider = LocalStorageProvider(base_dir=str(tmp_path))
    tenant_id = "tenant-12345"

    # Attempt path traversal
    with pytest.raises(PermissionError, match="Path traversal detected"):
        provider._resolve_tenant_path(tenant_id, "../../etc/passwd")

    with pytest.raises(PermissionError, match="Path traversal detected"):
        provider._resolve_tenant_path(tenant_id, "../other-tenant/secret.txt")
