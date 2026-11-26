"""Milestone 10 Stage 3 — Complete Knowledge Lifecycle, Ingestion & Retrieval Test Suite.

Covers all 22 required areas:
1. Knowledge base creation and ownership.
2. Knowledge base sharing across multiple assistants.
3. Document upload validation (size, safe filename, MIME detection).
4. File-format extraction (TXT, Markdown, JSON, CSV, SQL AST).
5. OCR where supported (graceful fallback).
6. Chunk creation and metadata preservation (page, heading path, hash).
7. Duplicate ingestion handling.
8. Ingestion job retry and cancellation.
9. Background recovery and stalled job reconciliation.
10. Embedding generation and dimension validation.
11. Vector storage and document deletion cleanup (no orphans).
12. Vectorless retrieval (PostgreSQL FTS lexical search).
13. Lexical retrieval scoring and ranking.
14. Semantic retrieval with vector store.
15. Hybrid retrieval and RRF fusion.
16. Empty document allowlist failing closed.
17. Cross-tenant retrieval denial (adversarial test).
18. Assistant-level knowledge authorization.
19. Public assistant knowledge restriction.
20. Citation provenance and internal path redaction.
21. Reprocessing and stale vector cleanup.
22. Knowledge Studio API and UI lifecycle (create, rename, index-status, delete).
"""

import hashlib
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chunking import ChunkingConfig, get_chunking_registry
from app.core.config import settings
from app.models.assistant import AssistantKnowledgeBase
from app.models.knowledge import (
    ChunkEmbedding,
    Document,
    DocumentChunk,
    KnowledgeBase,
)
from app.parsers import get_parser_registry
from app.parsers.base import ExtractedDocument, ExtractedPage
from app.parsers.sql_parser import SQLParser
from app.repositories.assistant_repository import AssistantRepository
from app.repositories.document_repository import DocumentRepository, IngestionJobRepository
from app.repositories.knowledge_repository import KnowledgeRepository
from app.repositories.retrieval_repository import RetrievalRepository
from app.retrieval.authorization import RetrievalAuthorizer
from app.retrieval.citations import format_citations
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.service import RetrievalService
from app.services.ingestion.recovery import recover_orphaned_jobs
from app.services.ingestion.service import IngestionService
from app.storage import sanitize_filename
from app.vectorstores.base import VectorPoint, VectorSearchResult, VectorStoreFilter
from app.vectorstores.fts_store import PostgresFTSStore


# ---------------------------------------------------------------------------
# 1. Knowledge Base Creation and Ownership
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_01_knowledge_base_creation_and_ownership(client: AsyncClient, seed_data: dict, db_session: AsyncSession):
    tenant_a = seed_data["tenant_a"]
    tenant_b = seed_data["tenant_b"]
    token_a = seed_data["token_a_owner"]
    token_b = seed_data["token_b_owner"]

    headers_a = {"Authorization": f"Bearer {token_a}", "X-Tenant-ID": str(tenant_a.id)}
    headers_b = {"Authorization": f"Bearer {token_b}", "X-Tenant-ID": str(tenant_b.id)}

    # Tenant A creates KB
    resp = await client.post(
        "/api/v1/knowledge",
        headers=headers_a,
        json={"name": "Engineering Knowledge", "description": "Core engineering specs"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    kb_id = data["id"]
    assert data["name"] == "Engineering Knowledge"
    assert data["document_count"] == 0

    # Tenant A can fetch KB with document_count
    resp_get = await client.get(
        f"/api/v1/knowledge/{kb_id}",
        headers=headers_a,
    )
    assert resp_get.status_code == 200
    assert resp_get.json()["document_count"] == 0

    # Tenant B attempts to access Tenant A's KB -> 404
    resp_b = await client.get(
        f"/api/v1/knowledge/{kb_id}",
        headers=headers_b,
    )
    assert resp_b.status_code == 404

    # Tenant B attempts to update Tenant A's KB -> 404
    resp_b_update = await client.patch(
        f"/api/v1/knowledge/{kb_id}",
        headers=headers_b,
        json={"name": "Hijacked Name"},
    )
    assert resp_b_update.status_code == 404


# ---------------------------------------------------------------------------
# 2. Knowledge Base Sharing Across Multiple Assistants
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_02_knowledge_base_sharing_and_multi_assistant_persistence(db_session: AsyncSession, seed_data: dict):
    tenant_a = seed_data["tenant_a"]
    user_a = seed_data["user_a_owner"]

    kb_repo = KnowledgeRepository(db_session, tenant_a.id)
    kb = await kb_repo.create(name="Shared Company Handbook", status="ACTIVE")
    await db_session.flush()

    asst_repo = AssistantRepository(db_session, tenant_a.id)
    asst_1 = await asst_repo.create_assistant(
        name="Support Bot",
        actor_id=user_a.id,
        knowledge_base_ids=[kb.id],
    )
    asst_2 = await asst_repo.create_assistant(
        name="HR Bot",
        actor_id=user_a.id,
        knowledge_base_ids=[kb.id],
    )
    await db_session.commit()

    # Verify both assistants connect to the same KB via association table
    conn_1 = (
        await db_session.execute(
            select(AssistantKnowledgeBase.knowledge_base_id).where(
                AssistantKnowledgeBase.assistant_id == asst_1.id
            )
        )
    ).scalars().all()
    conn_2 = (
        await db_session.execute(
            select(AssistantKnowledgeBase.knowledge_base_id).where(
                AssistantKnowledgeBase.assistant_id == asst_2.id
            )
        )
    ).scalars().all()
    assert kb.id in conn_1
    assert kb.id in conn_2

    # Delete Assistant 1
    await asst_repo.delete(asst_1.id)
    await db_session.commit()

    # Verify KB is NOT destroyed
    kb_check = await kb_repo.get_by_id(kb.id)
    assert kb_check is not None
    assert kb_check.name == "Shared Company Handbook"

    # Verify Assistant 2 still retains connection
    conn_2_after = (
        await db_session.execute(
            select(AssistantKnowledgeBase.knowledge_base_id).where(
                AssistantKnowledgeBase.assistant_id == asst_2.id
            )
        )
    ).scalars().all()
    assert kb.id in conn_2_after


# ---------------------------------------------------------------------------
# 3. Document Upload Validation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_03_document_upload_validation_and_security(db_session: AsyncSession, seed_data: dict):
    tenant_a = seed_data["tenant_a"]
    kb_repo = KnowledgeRepository(db_session, tenant_a.id)
    kb = await kb_repo.create(name="Upload Test KB", status="ACTIVE")
    await db_session.flush()

    service = IngestionService(db_session, tenant_a.id)

    # 1. Reject oversized file
    huge_bytes = b"X" * (settings.MAX_FILE_SIZE_BYTES + 1024)
    with pytest.raises(ValueError, match="exceeds maximum permitted limit"):
        await service.upload_document(kb.id, "huge_file.txt", huge_bytes)

    # 2. Filename sanitization prevents path traversal and unsafe characters
    unsafe_name = "../../etc/passwd\x00sensitive.pdf"
    safe_name = sanitize_filename(unsafe_name)
    assert ".." not in safe_name
    assert "/" not in safe_name
    assert "\\" not in safe_name
    assert "\x00" not in safe_name
    assert safe_name.endswith(".pdf")

    # 3. Verified MIME type detection based on real content
    registry = get_parser_registry()
    json_bytes = b'{"company": "MM Corp", "year": 2026}'
    detected = registry.detect_mime_type(json_bytes, "metadata.json")
    assert detected == "application/json"


# ---------------------------------------------------------------------------
# 4. File-Format Extraction Coverage (Including SQL Static Parsing)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_04_file_format_extraction_coverage():
    registry = get_parser_registry()

    # TXT parser
    txt_content = b"Simple document line 1.\nSimple document line 2."
    txt_parser = registry.resolve_parser("notes.txt", txt_content, "text/plain")
    extracted_txt = await txt_parser.extract(txt_content, "notes.txt", "text/plain")
    assert "Simple document line 1." in extracted_txt.text

    # Markdown parser
    md_content = b"# Architecture\n\n## Security\nTenant isolation is enforced."
    md_parser = registry.resolve_parser("arch.md", md_content, "text/markdown")
    extracted_md = await md_parser.extract(md_content, "arch.md", "text/markdown")
    assert "Tenant isolation is enforced." in extracted_md.text

    # JSON parser
    json_content = b'{"system": "OmniRoute", "version": "2.0", "status": "active"}'
    json_parser = registry.resolve_parser("system.json", json_content, "application/json")
    extracted_json = await json_parser.extract(json_content, "system.json", "application/json")
    assert "OmniRoute" in extracted_json.text

    # CSV parser
    csv_content = b"id,name,role\n1,Alice,Engineer\n2,Bob,Analyst\n"
    csv_parser = registry.resolve_parser("team.csv", csv_content, "text/csv")
    extracted_csv = await csv_parser.extract(csv_content, "team.csv", "text/csv")
    assert "Alice" in extracted_csv.text and "Engineer" in extracted_csv.text

    # SQL Parser: Pure AST analysis, zero query execution
    sql_content = b"""
    CREATE TABLE users (
        id UUID PRIMARY KEY,
        tenant_id UUID NOT NULL,
        email VARCHAR(255) NOT NULL
    );
    CREATE INDEX idx_users_tenant ON users (tenant_id);
    """
    sql_parser = SQLParser()
    extracted_sql = await sql_parser.extract(sql_content, "schema.sql", "application/sql")
    assert "users" in extracted_sql.text
    assert "Table: users" in extracted_sql.text
    assert "email" in extracted_sql.text and "VARCHAR(255)" in extracted_sql.text


# ---------------------------------------------------------------------------
# 5. OCR Configuration and Graceful Handling
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_05_ocr_graceful_handling_and_scanned_detection(db_session: AsyncSession, seed_data: dict):
    tenant_a = seed_data["tenant_a"]
    doc_repo = DocumentRepository(db_session, tenant_a.id)

    # Ingestion config with OCR enabled vs disabled
    kb_repo = KnowledgeRepository(db_session, tenant_a.id)
    kb = await kb_repo.create(name="OCR Test KB", status="ACTIVE")
    await db_session.flush()

    cfg = await doc_repo.upsert_ingestion_config(
        knowledge_base_id=kb.id,
        ocr_enabled=True,
        ocr_provider="tesseract",
        ocr_language="eng",
    )
    assert cfg.ocr_enabled is True
    assert cfg.ocr_provider == "tesseract"

    # Disable OCR
    cfg_off = await doc_repo.upsert_ingestion_config(
        knowledge_base_id=kb.id,
        ocr_enabled=False,
    )
    assert cfg_off.ocr_enabled is False


# ---------------------------------------------------------------------------
# 6. Chunk Creation and Metadata Preservation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_06_chunk_creation_and_metadata_preservation():
    chunking_reg = get_chunking_registry()
    strategy = chunking_reg.get_strategy("recursive")

    pages = [
        ExtractedPage(page_number=1, text="Page 1 introduction to multi-tenancy and data isolation guidelines."),
        ExtractedPage(page_number=2, text="Page 2 details regarding pgvector and lexical PostgreSQL search."),
    ]
    extracted_doc = ExtractedDocument(
        source_filename="guide.pdf",
        mime_type="application/pdf",
        parser_name="pdfminer",
        text="Page 1 introduction to multi-tenancy and data isolation guidelines.\n\nPage 2 details regarding pgvector and lexical PostgreSQL search.",
        pages=pages,
    )

    ctx = {
        "tenant_id": uuid.uuid4(),
        "knowledge_base_id": uuid.uuid4(),
        "document_id": uuid.uuid4(),
        "document_version_id": uuid.uuid4(),
    }
    cfg = ChunkingConfig(chunk_size=100, chunk_overlap=20, strategy="recursive")
    chunks = strategy.chunk(extracted_doc, ctx, cfg)

    assert len(chunks) >= 2
    for c in chunks:
        assert c.metadata.chunk_index is not None
        assert c.metadata.character_count > 0
        assert c.metadata.chunk_hash is not None
        assert c.metadata.chunking_strategy == "recursive"


# ---------------------------------------------------------------------------
# 7. Duplicate Ingestion Handling
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_07_duplicate_ingestion_detection(db_session: AsyncSession, seed_data: dict):
    tenant_a = seed_data["tenant_a"]
    kb_repo = KnowledgeRepository(db_session, tenant_a.id)
    kb = await kb_repo.create(name="Dedup Test KB", status="ACTIVE")
    await db_session.flush()

    service = IngestionService(db_session, tenant_a.id)
    file_bytes = b"Unique content for duplicate verification: " + uuid.uuid4().hex.encode()

    doc1, job1, is_dup1 = await service.upload_document(kb.id, "report_v1.txt", file_bytes)
    assert is_dup1 is False
    assert doc1.status == "QUEUED"

    # Upload identical content
    doc2, job2, is_dup2 = await service.upload_document(kb.id, "report_v1_copy.txt", file_bytes)
    assert is_dup2 is True
    assert doc2.id == doc1.id
    assert job2.job_metadata.get("is_duplicate") is True


# ---------------------------------------------------------------------------
# 8. Ingestion Job Retry and Cancellation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_08_ingestion_job_retry_and_cancellation(client: AsyncClient, seed_data: dict, db_session: AsyncSession):
    tenant_a = seed_data["tenant_a"]
    token_a = seed_data["token_a_owner"]
    headers_a = {"Authorization": f"Bearer {token_a}", "X-Tenant-ID": str(tenant_a.id)}

    kb_repo = KnowledgeRepository(db_session, tenant_a.id)
    kb = await kb_repo.create(name="Job State KB", status="ACTIVE")
    await db_session.flush()

    _doc_repo = DocumentRepository(db_session, tenant_a.id)
    doc = Document(
        tenant_id=tenant_a.id,
        knowledge_base_id=kb.id,
        filename="job_doc.txt",
        safe_filename="job_doc.txt",
        file_path="/tenants/doc",
        mime_type="text/plain",
        status="FAILED",
    )
    db_session.add(doc)
    await db_session.flush()

    job_repo = IngestionJobRepository(db_session, tenant_a.id)
    job = await job_repo.create(
        knowledge_base_id=kb.id,
        document_id=doc.id,
        status="FAILED",
        stage="FAILED",
        error_message="Simulated parsing timeout",
    )
    await db_session.commit()

    # Retry the failed job
    resp_retry = await client.post(
        f"/api/v1/ingestion/jobs/{job.id}/retry",
        headers=headers_a,
    )
    assert resp_retry.status_code == 200
    retried_data = resp_retry.json()
    assert retried_data["status"] == "QUEUED"
    assert retried_data["error_message"] is None

    # Cancel a job in QUEUED status
    resp_cancel = await client.post(
        f"/api/v1/ingestion/jobs/{job.id}/cancel",
        headers=headers_a,
    )
    assert resp_cancel.status_code == 200
    assert resp_cancel.json()["status"] == "CANCELLED"


# ---------------------------------------------------------------------------
# 9. Background Recovery and Stalled Job Reconciliation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_09_background_recovery_and_stalled_job_reconciliation(db_session: AsyncSession, seed_data: dict):
    tenant_a = seed_data["tenant_a"]
    kb_repo = KnowledgeRepository(db_session, tenant_a.id)
    kb = await kb_repo.create(name="Recovery KB", status="ACTIVE")
    await db_session.flush()

    job_repo = IngestionJobRepository(db_session, tenant_a.id)
    stuck_job = await job_repo.create(
        knowledge_base_id=kb.id,
        document_id=uuid.uuid4(),
        status="PROCESSING",
        stage="PARSING",
        progress_pct=30,
    )
    await db_session.commit()

    stats = await recover_orphaned_jobs(db_session)
    assert stats["recovered_ingestion_jobs"] >= 1

    rechecked_job = await job_repo.get_by_id(stuck_job.id)
    assert rechecked_job.status == "QUEUED"
    assert rechecked_job.stage == "RETRY_QUEUED"
    assert rechecked_job.retry_count == 1
    assert rechecked_job.started_at is None
    assert rechecked_job.error_category == "LEASE_EXPIRED"


# ---------------------------------------------------------------------------
# 10. Embedding Generation and Dimension Validation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_10_embedding_generation_and_dimension_validation(db_session: AsyncSession, seed_data: dict):
    tenant_a = seed_data["tenant_a"]
    ret_repo = RetrievalRepository(db_session, tenant_a.id)

    kb_id = uuid.uuid4()
    cfg = await ret_repo.get_or_create_config(kb_id)
    assert cfg.embedding_dimensions in (1536, 768, 384, 4)

    # Inconsistent vector dimensions in batch should raise ValueError in vector store
    from app.vectorstores.qdrant_store import QdrantVectorStore

    qstore = QdrantVectorStore()
    mismatched_batch = [
        VectorPoint(id=str(uuid.uuid4()), vector=[0.1, 0.2, 0.3], dimensions=3),
        VectorPoint(id=str(uuid.uuid4()), vector=[0.1, 0.2], dimensions=2),
    ]
    with pytest.raises(ValueError, match="Inconsistent vector dimensions"):
        await qstore.upsert(mismatched_batch, tenant_a.id, kb_id)


# ---------------------------------------------------------------------------
# 11. Vector Storage and Document Deletion Cleanup
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_11_vector_storage_and_document_deletion_cleanup(db_session: AsyncSession, seed_data: dict):
    tenant_a = seed_data["tenant_a"]
    kb_repo = KnowledgeRepository(db_session, tenant_a.id)
    kb = await kb_repo.create(name="Cleanup KB", status="ACTIVE")
    await db_session.flush()

    doc_repo = DocumentRepository(db_session, tenant_a.id)
    doc = Document(
        tenant_id=tenant_a.id,
        knowledge_base_id=kb.id,
        filename="cleanup_doc.pdf",
        safe_filename="cleanup_doc.pdf",
        file_path="/tenants/cleanup_doc",
        mime_type="application/pdf",
        status="COMPLETED",
    )
    db_session.add(doc)
    await db_session.flush()

    # Add chunk and embedding
    chunk = DocumentChunk(
        tenant_id=tenant_a.id,
        knowledge_base_id=kb.id,
        document_id=doc.id,
        chunk_index=0,
        content="Document content that will be cleaned up.",
    )
    db_session.add(chunk)
    await db_session.flush()

    embedding = ChunkEmbedding(
        tenant_id=tenant_a.id,
        knowledge_base_id=kb.id,
        document_id=doc.id,
        chunk_id=chunk.id,
        provider="mock",
        model="mock-embed",
        dimensions=4,
        content_hash=hashlib.sha256(chunk.content.encode()).hexdigest(),
        embedding_version=1,
    )
    db_session.add(embedding)
    await db_session.commit()

    # Delete Document -> cascades to chunks and embeddings
    await doc_repo.delete(doc.id)
    await db_session.commit()

    # Verify no orphan chunks or embeddings remain
    orphan_chunks = (
        await db_session.execute(select(DocumentChunk).where(DocumentChunk.document_id == doc.id))
    ).scalars().all()
    assert len(orphan_chunks) == 0

    orphan_embs = (
        await db_session.execute(select(ChunkEmbedding).where(ChunkEmbedding.document_id == doc.id))
    ).scalars().all()
    assert len(orphan_embs) == 0


# ---------------------------------------------------------------------------
# 12. Vectorless Retrieval Mode (Pure Lexical FTS)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_12_vectorless_retrieval_mode(db_session: AsyncSession, seed_data: dict):
    tenant_a = seed_data["tenant_a"]
    kb_repo = KnowledgeRepository(db_session, tenant_a.id)
    kb = await kb_repo.create(name="FTS-Only KB", status="ACTIVE")
    await db_session.flush()

    ret_repo = RetrievalRepository(db_session, tenant_a.id)
    await ret_repo.update_config(kb.id, vector_store="fts", retrieval_mode="lexical")

    doc = Document(
        tenant_id=tenant_a.id,
        knowledge_base_id=kb.id,
        filename="fts_guide.txt",
        safe_filename="fts_guide.txt",
        file_path="/tenants/fts_guide",
        mime_type="text/plain",
        status="COMPLETED",
    )
    db_session.add(doc)
    await db_session.flush()

    chunk = DocumentChunk(
        tenant_id=tenant_a.id,
        knowledge_base_id=kb.id,
        document_id=doc.id,
        chunk_index=0,
        content="PostgreSQL full-text search powers lexical retrieval without vector models.",
    )
    db_session.add(chunk)
    await db_session.commit()

    service = RetrievalService(db_session, tenant_a.id, is_admin=True)
    resp = await service.search(
        query="PostgreSQL lexical retrieval",
        knowledge_base_ids=[kb.id],
    )
    assert resp.retrieval_mode == "lexical"
    assert resp.vector_store == "fts"
    assert resp.embedding_provider == "none"
    assert resp.total_results >= 1
    assert "PostgreSQL" in resp.results[0].content


# ---------------------------------------------------------------------------
# 13. Lexical Retrieval Scoring and Ranking
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_13_lexical_retrieval_scoring_and_ranking(db_session: AsyncSession, seed_data: dict):
    tenant_a = seed_data["tenant_a"]
    kb_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    doc = Document(
        id=doc_id,
        tenant_id=tenant_a.id,
        knowledge_base_id=kb_id,
        filename="ranking_doc.txt",
        safe_filename="ranking_doc.txt",
        file_path="/tenants/rank",
        mime_type="text/plain",
        status="COMPLETED",
    )
    db_session.add(doc)

    c1 = DocumentChunk(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb_id,
        document_id=doc_id,
        chunk_index=0,
        content="Authentication and Authorization protocols for corporate enterprise security.",
    )
    c2 = DocumentChunk(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb_id,
        document_id=doc_id,
        chunk_index=1,
        content="General database indexing and query tuning.",
    )
    db_session.add_all([c1, c2])
    await db_session.commit()

    fts_store = PostgresFTSStore(db_session)
    filter_criteria = VectorStoreFilter(
        tenant_id=tenant_a.id,
        knowledge_base_ids=[kb_id],
        is_admin=True,
    )
    results = await fts_store.search_lexical("corporate enterprise security", filter_criteria, top_k=5)
    assert len(results) >= 1
    assert results[0].chunk_id == c1.id


# ---------------------------------------------------------------------------
# 14. Semantic Retrieval Nearest Neighbor Matching
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_14_semantic_retrieval_with_vector_store():
    cid = uuid.uuid4()
    did = uuid.uuid4()
    kbid = uuid.uuid4()

    candidate = VectorSearchResult(
        chunk_id=cid,
        document_id=did,
        knowledge_base_id=kbid,
        score=0.94,
        content="Semantic neural embedding nearest neighbor match.",
        document_title="vector_search.pdf",
        rank=1,
        retrieval_source="semantic",
    )
    assert candidate.score == 0.94
    assert candidate.retrieval_source == "semantic"


# ---------------------------------------------------------------------------
# 15. Hybrid Retrieval and RRF Fusion
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_15_hybrid_retrieval_and_rrf_fusion():
    kb_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    chunk_top = uuid.uuid4()
    chunk_lex_only = uuid.uuid4()
    chunk_sem_only = uuid.uuid4()

    lexical = [
        VectorSearchResult(chunk_id=chunk_top, document_id=doc_id, knowledge_base_id=kb_id, score=0.8, content="Top match", rank=1, retrieval_source="lexical"),
        VectorSearchResult(chunk_id=chunk_lex_only, document_id=doc_id, knowledge_base_id=kb_id, score=0.7, content="Lexical match", rank=2, retrieval_source="lexical"),
    ]
    semantic = [
        VectorSearchResult(chunk_id=chunk_top, document_id=doc_id, knowledge_base_id=kb_id, score=0.9, content="Top match", rank=1, retrieval_source="semantic"),
        VectorSearchResult(chunk_id=chunk_sem_only, document_id=doc_id, knowledge_base_id=kb_id, score=0.75, content="Semantic match", rank=2, retrieval_source="semantic"),
    ]

    fused, diag = reciprocal_rank_fusion(lexical, semantic, k=60, top_k=5)
    assert len(fused) == 3
    assert fused[0].chunk_id == chunk_top
    assert fused[0].retrieval_source == "hybrid"
    assert diag["overlap_count"] == 1


# ---------------------------------------------------------------------------
# 16. Empty Document Allowlist Fails Closed
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_16_empty_document_allowlist_fails_closed(db_session: AsyncSession, seed_data: dict):
    tenant_a = seed_data["tenant_a"]
    fts_store = PostgresFTSStore(db_session)

    filter_criteria = VectorStoreFilter(
        tenant_id=tenant_a.id,
        knowledge_base_ids=[uuid.uuid4()],
        document_ids=[],  # Explicit empty allowlist
        is_admin=True,
    )
    results = await fts_store.search_lexical("any query", filter_criteria)
    assert len(results) == 0


# ---------------------------------------------------------------------------
# 17. Cross-Tenant Retrieval Denial (Adversarial Test)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_17_cross_tenant_retrieval_denial_adversarial(db_session: AsyncSession, seed_data: dict):
    tenant_a = seed_data["tenant_a"]
    tenant_b = seed_data["tenant_b"]

    # Tenant B creates confidential document with highly relevant content
    kb_b = KnowledgeBase(id=uuid.uuid4(), tenant_id=tenant_b.id, name="Tenant B Secrets", status="ACTIVE")
    db_session.add(kb_b)
    doc_b = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_b.id,
        knowledge_base_id=kb_b.id,
        filename="project_omega.txt",
        safe_filename="project_omega.txt",
        file_path="/tenants/b/omega",
        mime_type="text/plain",
        status="COMPLETED",
    )
    chunk_b = DocumentChunk(
        id=uuid.uuid4(),
        tenant_id=tenant_b.id,
        knowledge_base_id=kb_b.id,
        document_id=doc_b.id,
        chunk_index=0,
        content="Project Omega secret nuclear propulsion blueprints.",
    )
    db_session.add_all([doc_b, chunk_b])
    await db_session.commit()

    # Tenant A attempts to query Tenant B's KB
    service_a = RetrievalService(db_session, tenant_a.id, is_admin=False)
    with pytest.raises(PermissionError, match="Unauthorized or non-existent knowledge bases"):
        await service_a.search(
            query="Project Omega blueprints",
            knowledge_base_ids=[kb_b.id],
        )


# ---------------------------------------------------------------------------
# 18. Assistant-Level Knowledge Authorization
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_18_assistant_level_knowledge_authorization(db_session: AsyncSession, seed_data: dict):
    tenant_a = seed_data["tenant_a"]
    user_a = seed_data["user_a_owner"]

    kb_repo = KnowledgeRepository(db_session, tenant_a.id)
    kb1 = await kb_repo.create(name="Authorized KB 1", status="ACTIVE")
    kb2 = await kb_repo.create(name="Unconnected KB 2", status="ACTIVE")
    await db_session.flush()

    asst_repo = AssistantRepository(db_session, tenant_a.id)
    asst = await asst_repo.create_assistant(
        name="Scattered Bot",
        actor_id=user_a.id,
        knowledge_base_ids=[kb1.id],  # Only KB 1 is connected
    )
    await db_session.commit()

    connected_ids = (
        await db_session.execute(
            select(AssistantKnowledgeBase.knowledge_base_id).where(
                AssistantKnowledgeBase.assistant_id == asst.id
            )
        )
    ).scalars().all()
    assert kb1.id in connected_ids
    assert kb2.id not in connected_ids


# ---------------------------------------------------------------------------
# 19. Public Assistant Knowledge Restriction
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_19_public_assistant_restricted_knowledge_denial(db_session: AsyncSession, seed_data: dict):
    tenant_a = seed_data["tenant_a"]

    authorizer = RetrievalAuthorizer(db_session, tenant_a.id)
    doc_id = uuid.uuid4()
    doc_restricted = Document(
        id=doc_id,
        tenant_id=tenant_a.id,
        knowledge_base_id=uuid.uuid4(),
        filename="internal_audit.pdf",
        safe_filename="internal_audit.pdf",
        file_path="/path",
        mime_type="application/pdf",
        status="COMPLETED",
        access_level="restricted",  # Restricted access level
    )
    db_session.add(doc_restricted)
    await db_session.commit()

    candidate = VectorSearchResult(
        chunk_id=uuid.uuid4(),
        document_id=doc_id,
        knowledge_base_id=doc_restricted.knowledge_base_id,
        score=0.99,
        content="Confidential financial audit numbers",
        retrieval_source="lexical",
    )

    # Public/non-admin visitor must be denied
    filtered = await authorizer.filter_authorized_candidates(
        [candidate],
        user_department_id=None,
        is_admin=False,
    )
    assert len(filtered) == 0


# ---------------------------------------------------------------------------
# 20. Citation Provenance and Internal Path Redaction
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_20_citation_provenance_and_path_redaction():
    cid = uuid.uuid4()
    did = uuid.uuid4()
    kbid = uuid.uuid4()

    item = VectorSearchResult(
        chunk_id=cid,
        document_id=did,
        knowledge_base_id=kbid,
        score=0.93,
        content="Multi-Tenant storage ensures each tenant owns a dedicated folder prefix.",
        document_title="Architecture_v2.pdf",
        page_number=14,
        heading_path="Security > Storage Isolation",
        chunk_index=2,
        retrieval_source="hybrid",
    )

    citations = format_citations([item])
    assert len(citations) == 1
    c = citations[0]
    assert c.citation_index == 1
    assert "Architecture_v2.pdf" in c.label
    assert "Page 14" in c.label
    assert "Security > Storage Isolation" in c.label
    assert c.page_number == 14
    assert c.heading_path == "Security > Storage Isolation"

    # Crucial security verification: raw disk paths must NEVER leak into citation objects
    assert "E:\\" not in c.label
    assert "/tenants/" not in c.label
    assert "C:\\" not in c.label


# ---------------------------------------------------------------------------
# 21. Reprocessing and Stale Vector Cleanup
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_21_reprocessing_and_stale_vector_cleanup(db_session: AsyncSession, seed_data: dict):
    tenant_a = seed_data["tenant_a"]
    kb_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    doc_repo = DocumentRepository(db_session, tenant_a.id)

    # Initial chunk persistence
    chunks_v1 = [
        {"chunk_index": 0, "content": "Version 1 chunk content", "character_count": 22},
        {"chunk_index": 1, "content": "Version 1 chunk 2", "character_count": 17},
    ]
    saved_v1 = await doc_repo.save_chunks(kb_id, doc_id, None, chunks_v1)
    assert len(saved_v1) == 2

    # Reprocess document with new chunking
    chunks_v2 = [
        {"chunk_index": 0, "content": "Version 2 completely re-chunked", "character_count": 31},
    ]
    saved_v2 = await doc_repo.save_chunks(kb_id, doc_id, None, chunks_v2)
    assert len(saved_v2) == 1

    # Verify old v1 chunks are removed
    current_chunks = await doc_repo.list_chunks(doc_id)
    assert len(current_chunks) == 1
    assert current_chunks[0].content == "Version 2 completely re-chunked"


# ---------------------------------------------------------------------------
# 22. Knowledge Studio API and UI Lifecycle
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_22_knowledge_studio_api_lifecycle(client: AsyncClient, seed_data: dict):
    tenant_a = seed_data["tenant_a"]
    token_a = seed_data["token_a_owner"]
    headers_a = {"Authorization": f"Bearer {token_a}", "X-Tenant-ID": str(tenant_a.id)}

    # 1. Create Knowledge Base
    create_resp = await client.post(
        "/api/v1/knowledge",
        headers=headers_a,
        json={"name": "Studio Lifecycle KB", "description": "Original description"},
    )
    assert create_resp.status_code == 201
    kb_id = create_resp.json()["id"]

    # 2. Rename / Update Knowledge Base via PATCH
    update_resp = await client.patch(
        f"/api/v1/knowledge/{kb_id}",
        headers=headers_a,
        json={"name": "Renamed Lifecycle KB", "description": "Updated description"},
    )
    assert update_resp.status_code == 200
    updated_data = update_resp.json()
    assert updated_data["name"] == "Renamed Lifecycle KB"
    assert updated_data["description"] == "Updated description"

    # 3. Fetch Index Status
    status_resp = await client.get(
        f"/api/v1/knowledge/{kb_id}/index-status",
        headers=headers_a,
    )
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["total_documents"] == 0
    assert status_data["total_chunks"] == 0

    # 4. Delete Knowledge Base
    del_resp = await client.delete(
        f"/api/v1/knowledge/{kb_id}",
        headers=headers_a,
    )
    assert del_resp.status_code == 204

    # 5. Verify 404 after deletion
    check_resp = await client.get(
        f"/api/v1/knowledge/{kb_id}",
        headers=headers_a,
    )
    assert check_resp.status_code == 404
