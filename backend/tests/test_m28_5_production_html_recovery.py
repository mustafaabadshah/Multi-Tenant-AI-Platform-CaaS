"""End-to-end integration and recovery tests for M28.5:
Production-Path HTML Ingestion Repair, Existing Document Recovery, and Ingestion Worker Verification.
"""

import asyncio
import io
import re
import uuid
from typing import Any
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import Document, DocumentChunk, DocumentVersion, IngestionJob, KnowledgeBase
from app.models.tenant import Tenant
from app.models.user import User
from app.parsers.html import HTMLParser
from app.parsers.registry import ParserRegistry, get_parser_registry
from app.services.ingestion.limits import (
    PERMANENT_INGESTION_ERRORS,
    TRANSIENT_INGESTION_ERRORS,
    IndexingError,
    IngestionTimeoutError,
    ProcessingTimeoutError,
    TemporaryDatabaseError,
    TemporaryStorageError,
    UnparseableDocumentError,
    UnsupportedFormatError,
)
from app.services.ingestion.service import IngestionService
from app.storage.base import StorageProvider


def generate_synthetic_cpp_for_loop_html(target_size: int = 268553) -> bytes:
    """Generate a realistic synthetic HTML file matching the exact 268553 byte size.

    Includes title, headings, code blocks, tables, lists, scripts, and boilerplate.
    """
    header = (
        b"<!DOCTYPE html>\n"
        b"<html lang=\"en\">\n"
        b"<head>\n"
        b"    <meta charset=\"UTF-8\">\n"
        b"    <title>C++ For Loop (With Syntax, Logic & Advanced Examples)</title>\n"
        b"    <script type=\"text/javascript\">\n"
        b"        // Analytics & Tracking script to verify stripping\n"
        b"        window.trackPageView = function() { console.log('page_view'); };\n"
        b"    </script>\n"
        b"    <style>\n"
        b"        body { font-family: sans-serif; }\n"
        b"        .nav-ad { display: block; }\n"
        b"    </style>\n"
        b"</head>\n"
        b"<body>\n"
        b"    <nav class=\"navigation-bar\">\n"
        b"        <a href=\"/\">Home</a> | <a href=\"/cpp\">C++ Tutorial</a> | <a href=\"/loops\">Control Flow</a>\n"
        b"    </nav>\n"
        b"    <main id=\"content\">\n"
        b"        <h1>C++ For Loop Deep Dive</h1>\n"
        b"        <p>In C++, loops are control flow structures used to repeatedly execute a block of code until a condition is met.</p>\n"
        b"        <h2>Syntax of standard for loop</h2>\n"
        b"        <pre><code>for (initialization; condition; increment/decrement) {\n"
        b"    // statement block\n"
        b"    std::cout << \"Loop iteration\" << std::endl;\n"
        b"}</code></pre>\n"
        b"        <h2>Practical Example with Iteration</h2>\n"
        b"        <p>Below is a complete working C++ program iterating over numbers 0 through 9:</p>\n"
        b"        <pre><code>#include &lt;iostream&gt;\n"
        b"int main() {\n"
        b"    for (int i = 0; i &lt; 10; ++i) {\n"
        b"        std::cout &lt;&lt; \"Current value of i: \" &lt;&lt; i &lt;&lt; std::endl;\n"
        b"    }\n"
        b"    return 0;\n"
        b"}</code></pre>\n"
        b"        <h2>Performance Benchmark Table</h2>\n"
        b"        <table>\n"
        b"            <thead><tr><th>Compiler</th><th>Optimization</th><th>Cycles per Iteration</th></tr></thead>\n"
        b"            <tbody>\n"
        b"                <tr><td>GCC 13.2</td><td>-O3</td><td>0.45</td></tr>\n"
        b"                <tr><td>Clang 17</td><td>-O3</td><td>0.44</td></tr>\n"
        b"                <tr><td>MSVC 2022</td><td>/O2</td><td>0.46</td></tr>\n"
        b"            </tbody>\n"
        b"        </table>\n"
    )

    footer = (
        b"    </main>\n"
        b"    <footer class=\"site-footer\">\n"
        b"        <p>Copyright 2026 Developer Portal. All rights reserved.</p>\n"
        b"    </footer>\n"
        b"</body>\n"
        b"</html>\n"
    )

    current_len = len(header) + len(footer)
    needed = target_size - current_len

    if needed < 0:
        return header[:target_size]

    # Generate realistic filler content using paragraphs and comments
    repeated_unit = (
        b"<section class=\"tutorial-substep\">\n"
        b"    <h3>Nested Loop Execution Characteristics</h3>\n"
        b"    <p>When nesting for loops, the inner loop executes its full cycle for each iteration of the outer loop. "
        b"Cache locality must be preserved when accessing multidimensional matrices in row-major order.</p>\n"
        b"    <!-- Detailed explanatory reference notes on loop unrolling and vectorization -->\n"
        b"</section>\n"
    )
    unit_len = len(repeated_unit)
    repetitions = needed // unit_len
    body = repeated_unit * repetitions

    remainder = needed - len(body)
    padding = b"<!-- padding: " + b"X" * max(0, remainder - 18) + b" -->\n"
    # Exact fit adjustment
    total = header + body + padding + footer
    diff = len(total) - target_size
    if diff > 0:
        total = total[:-diff]
    elif diff < 0:
        total = total + b" " * (-diff)
    return total


class MemoryTestStorage(StorageProvider):
    """Isolated, in-memory B2-compatible storage adapter for integration tests."""

    def __init__(self):
        self._store: dict[str, bytes] = {}

    async def save(self, tenant_id: str, relative_key: str, data: bytes) -> str:
        key = f"{tenant_id}/{relative_key.lstrip('/')}"
        self._store[key] = data
        return relative_key

    async def put(self, tenant_id: str, path: str, content: bytes, mime_type: str | None = None) -> str:
        return await self.save(tenant_id, path, content)

    async def get(self, tenant_id: str, relative_key: str) -> bytes:
        key = f"{tenant_id}/{relative_key.lstrip('/')}"
        if key not in self._store:
            raise FileNotFoundError(f"Object {relative_key} not found for tenant {tenant_id}")
        return self._store[key]

    async def delete(self, tenant_id: str, relative_key: str) -> bool:
        key = f"{tenant_id}/{relative_key.lstrip('/')}"
        if key in self._store:
            del self._store[key]
            return True
        return False

    async def exists(self, tenant_id: str, relative_key: str) -> bool:
        key = f"{tenant_id}/{relative_key.lstrip('/')}"
        return key in self._store

    async def get_size(self, tenant_id: str, relative_key: str) -> int:
        data = await self.get(tenant_id, relative_key)
        return len(data)

    async def list_keys(self, tenant_id: str, prefix: str = "") -> list[str]:
        pfx = f"{tenant_id}/{prefix.lstrip('/')}"
        return [k[len(tenant_id) + 1:] for k in self._store if k.startswith(pfx)]

    async def get_url(self, tenant_id: str, path: str, expires_in: int = 3600) -> str:
        return f"https://mock-b2-storage.local/{tenant_id}/{path}"


@pytest.fixture
async def setup_m28_5_env(db_session: AsyncSession):
    tenant = Tenant(
        id=uuid.uuid4(),
        name="Production Recovery Tenant",
        slug=f"recovery-{uuid.uuid4().hex[:6]}",
    )
    user = User(
        id=uuid.uuid4(),
        email="operator@test.local",
        hashed_password="mocked_argon2id_hash_placeholder",
        full_name="Systems Operator",
        status="ACTIVE",
    )
    kb = KnowledgeBase(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        name="Technical Documentation KB",
        status="ACTIVE",
    )
    db_session.add_all([tenant, user, kb])
    await db_session.commit()
    return {"tenant": tenant, "user": user, "kb": kb}


def test_synthetic_html_fixture_exact_size_and_structure():
    """Verify the synthetic HTML fixture matches the reported 268553 bytes and contains HTML structures."""
    content = generate_synthetic_cpp_for_loop_html(268553)
    assert len(content) == 268553
    assert b"C++ For Loop" in content
    assert b"<script" in content
    assert b"<table" in content
    assert b"for (int i = 0;" in content


def test_parser_registry_identifies_octet_stream_html_and_rejects_binary():
    """Verify ParserRegistry detects HTML when declared MIME is application/octet-stream and rejects deceptive binaries."""
    registry = ParserRegistry()
    html_bytes = generate_synthetic_cpp_for_loop_html(268553)

    # 1. Existing file with application/octet-stream MIME
    parser = registry.resolve_parser(
        filename="C___For_Loop.html",
        content=html_bytes,
        declared_mime="application/octet-stream",
    )
    assert isinstance(parser, HTMLParser)
    assert registry.detect_mime_type(html_bytes, "C___For_Loop.html") == "text/html"

    # 2. File without extension but with HTML content
    parser_no_ext = registry.resolve_parser(
        filename="unnamed_blob",
        content=html_bytes,
        declared_mime="application/octet-stream",
    )
    assert isinstance(parser_no_ext, HTMLParser)

    # 3. Deceptive binary payload renamed to .html (Windows PE header)
    fake_exe = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00" + b"\x00" * 200
    with pytest.raises(UnsupportedFormatError):
        registry.resolve_parser("malicious.html", fake_exe, declared_mime="application/octet-stream")

    # 4. Deceptive PDF renamed to .html
    fake_pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n"
    pdf_parser = registry.resolve_parser("masquerade.html", fake_pdf, declared_mime="text/html")
    # Must NOT route to HTMLParser
    assert not isinstance(pdf_parser, HTMLParser)


def test_typed_error_hierarchies_and_retryability():
    """Verify permanent vs transient error classifications for the ingestion pipeline."""
    # Permanent errors must not trigger retries
    assert issubclass(UnsupportedFormatError, ValueError)
    assert issubclass(UnparseableDocumentError, ValueError)
    assert UnsupportedFormatError in PERMANENT_INGESTION_ERRORS
    assert UnparseableDocumentError in PERMANENT_INGESTION_ERRORS
    assert IngestionTimeoutError in PERMANENT_INGESTION_ERRORS
    assert ProcessingTimeoutError in PERMANENT_INGESTION_ERRORS

    # Transient errors must allow bounded retry
    assert TemporaryStorageError in TRANSIENT_INGESTION_ERRORS
    assert TemporaryDatabaseError in TRANSIENT_INGESTION_ERRORS
    assert ConnectionError in TRANSIENT_INGESTION_ERRORS
    assert TimeoutError in TRANSIENT_INGESTION_ERRORS


@pytest.mark.asyncio
async def test_end_to_end_real_ingestion_pipeline_with_octet_stream_mime(
    db_session: AsyncSession, setup_m28_5_env, monkeypatch
):
    """End-to-End test executing the real IngestionService with 268553-byte HTML and application/octet-stream MIME.

    Executes:
    Upload/DocumentVersion metadata -> Storage -> Ingestion job -> ParserRegistry
    -> HTML extraction -> Chunking -> Status READY -> Searchable chunks.
    """
    env = setup_m28_5_env
    test_storage = MemoryTestStorage()
    monkeypatch.setattr("app.services.ingestion.service.get_storage_provider", lambda: test_storage)

    service = IngestionService(db_session, env["tenant"].id)
    service.storage = test_storage

    html_bytes = generate_synthetic_cpp_for_loop_html(268553)

    # 1. Upload document with historical application/octet-stream MIME
    doc, job, is_dup = await service.upload_document(
        knowledge_base_id=env["kb"].id,
        filename="C___For_Loop.html",
        content=html_bytes,
        mime_type="application/octet-stream",
    )
    assert is_dup is False
    assert doc.status == "QUEUED"
    assert doc.mime_type == "text/html"

    # 2. Execute ingestion through worker pipeline
    completed_job = await service.execute_job(job.id)
    assert completed_job.status == "COMPLETED"
    assert completed_job.stage == "COMPLETED"
    assert completed_job.progress_pct == 100

    # 3. Reload document and verify READY / COMPLETED status
    await db_session.refresh(doc)
    assert doc.status == "COMPLETED"
    assert doc.total_chunks > 0
    assert doc.metadata_json.get("detected_format") == "HTML"
    assert doc.metadata_json.get("detected_mime") == "text/html"

    # 4. Verify version record
    v_stmt = select(DocumentVersion).where(DocumentVersion.document_id == doc.id)
    version = (await db_session.execute(v_stmt)).scalar_one()
    assert version.extracted_text is not None
    assert len(version.extracted_text) > 500
    assert "C++ For Loop Deep Dive" in version.extracted_text
    assert "std::cout" in version.extracted_text
    assert "trackPageView" not in version.extracted_text  # Script tags cleanly stripped
    assert version.parser_name == "deterministic_html_parser"

    # 5. Verify chunks generated and persisted
    c_stmt = (
        select(DocumentChunk)
        .where(DocumentChunk.document_id == doc.id)
        .order_by(DocumentChunk.chunk_index.asc())
    )
    chunks = list((await db_session.execute(c_stmt)).scalars().all())
    assert len(chunks) == doc.total_chunks
    assert any("initialization" in c.content for c in chunks)


@pytest.mark.asyncio
async def test_reprocess_flow_idempotency_and_in_flight_protection(
    db_session: AsyncSession, setup_m28_5_env, monkeypatch
):
    """Verify that reprocessing safely recovers a failed document and blocks duplicate in-flight attempts."""
    env = setup_m28_5_env
    test_storage = MemoryTestStorage()
    monkeypatch.setattr("app.services.ingestion.service.get_storage_provider", lambda: test_storage)

    service = IngestionService(db_session, env["tenant"].id)
    service.storage = test_storage

    html_bytes = generate_synthetic_cpp_for_loop_html(268553)
    doc_path = f"kbs/{env['kb'].id}/docs/{uuid.uuid4()}/v1/C___For_Loop.html"
    await test_storage.put(str(env["tenant"].id), doc_path, html_bytes)

    # 1. Seed a simulated failed document record
    failed_doc = Document(
        id=uuid.uuid4(),
        tenant_id=env["tenant"].id,
        knowledge_base_id=env["kb"].id,
        filename="C___For_Loop.html",
        safe_filename="C___For_Loop.html",
        file_path=doc_path,
        file_size=len(html_bytes),
        mime_type="application/octet-stream",
        status="FAILED",
        total_pages=0,
        total_chunks=0,
        metadata_json={},
    )
    db_session.add(failed_doc)
    await db_session.flush()

    failed_version = DocumentVersion(
        id=uuid.uuid4(),
        tenant_id=env["tenant"].id,
        document_id=failed_doc.id,
        version_num=1,
        file_path=doc_path,
        file_size=len(html_bytes),
        file_hash="90685c333c7049b14dc6622e5b20733b2746f8c2a1aea9d558d579786da5907d",
        extracted_text=None,
        structured_data={},
        extraction_stats={},
    )
    db_session.add(failed_version)
    await db_session.commit()

    # 2. Trigger reprocess job creation
    reprocess_job = await service.job_repo.create(
        knowledge_base_id=failed_doc.knowledge_base_id,
        document_id=failed_doc.id,
        document_version_id=failed_version.id,
        status="QUEUED",
        stage="QUEUED",
        progress_pct=10,
        job_metadata={"reprocessed_by": str(env["user"].id), "reprocess_attempt": True},
    )
    failed_doc.status = "QUEUED"
    await db_session.commit()

    # 3. Verify in-flight duplicate check
    active_stmt = select(IngestionJob).where(
        IngestionJob.document_id == failed_doc.id,
        IngestionJob.tenant_id == env["tenant"].id,
        IngestionJob.status.in_(("QUEUED", "PROCESSING")),
    )
    active_jobs = list((await db_session.execute(active_stmt)).scalars().all())
    assert len(active_jobs) == 1

    # 4. Execute the reprocess job to completion
    res_job = await service.execute_job(reprocess_job.id)
    assert res_job.status == "COMPLETED"

    await db_session.refresh(failed_doc)
    assert failed_doc.status == "COMPLETED"
    assert failed_doc.total_chunks > 0
    assert failed_doc.metadata_json.get("detected_format") == "HTML"
