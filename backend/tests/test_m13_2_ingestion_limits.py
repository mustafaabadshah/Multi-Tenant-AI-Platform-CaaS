"""M13.2 REL-1/REL-2/REL-3 ingestion limit and event-loop protection tests.

No live LLM, embedding, OCR, or network provider is used. Parsers and page
counts are mocked; storage is an in-memory fake; the database is file-backed
SQLite so concurrent ingestion tasks use independent connections.
"""

import asyncio
import io
import threading
import uuid
import zipfile

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.database.base import Base
from app.models.knowledge import (
    ChunkEmbedding,
    Document,
    DocumentChunk,
    DocumentVersion,
    IngestionJob,
    KnowledgeBase,
    RetrievalConfig,
)
from app.models.tenant import Tenant
from app.parsers.base import ExtractedDocument, ExtractedPage
from app.parsers.registry import ParserRegistry, get_parser_registry
from app.services.ingestion import limits as ingestion_limits
from app.services.ingestion import service as service_module
from app.services.ingestion.limits import (
    IngestionLimitExceededError,
    UploadTooLargeError,
    read_upload_bounded,
    validate_zip_archive,
)
from app.services.ingestion.service import IngestionService, run_ingestion_in_background

MIB = 1024 * 1024


class _StaticStorage:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.get_calls = 0

    async def get(self, tenant_id: str, path: str) -> bytes:
        self.get_calls += 1
        await asyncio.sleep(0)
        return self.payload


class _ConcurrencyTracker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.active = 0
        self.max_active = 0

    def enter(self) -> None:
        with self._lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)

    def exit(self) -> None:
        with self._lock:
            self.active -= 1


class _SlowParser:
    parser_name = "slow-test-parser"
    parser_version = "test"

    def __init__(self, tracker: _ConcurrencyTracker, delay: float = 0.2) -> None:
        self.tracker = tracker
        self.delay = delay

    async def extract(self, content, filename, mime_type=None):
        self.tracker.enter()
        try:
            await asyncio.sleep(self.delay)
            body = "# Slow\n\nBounded concurrency ingestion content."
            return ExtractedDocument(
                source_filename=filename,
                mime_type=mime_type or "text/plain",
                parser_name=self.parser_name,
                parser_version=self.parser_version,
                text=body,
                pages=[ExtractedPage(page_number=1, text=body)],
            )
        finally:
            self.tracker.exit()


class _StaticParser:
    parser_name = "static-test-parser"
    parser_version = "test"

    def __init__(self, body: str) -> None:
        self.body = body

    async def extract(self, content, filename, mime_type=None):
        return ExtractedDocument(
            source_filename=filename,
            mime_type=mime_type or "text/plain",
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            text=self.body,
            pages=[ExtractedPage(page_number=1, text=self.body)],
        )


class _SleepingParser:
    parser_name = "sleeping-test-parser"
    parser_version = "test"

    def __init__(self, delay: float = 2.0) -> None:
        self.delay = delay

    async def extract(self, content, filename, mime_type=None):
        await asyncio.sleep(self.delay)
        return ExtractedDocument(
            source_filename=filename,
            mime_type=mime_type or "text/plain",
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            text="should never be persisted",
            pages=[ExtractedPage(page_number=1, text="should never be persisted")],
        )


@pytest.fixture
async def limits_session_factory(tmp_path):
    db_path = (tmp_path / "m13_2_limits.db").as_posix()
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
    filename: str = "doc.txt",
    mime_type: str = "text/plain",
    file_size: int = 64,
    vector_store: str = "fts",
):
    suffix = uuid.uuid4().hex[:12]
    async with session_factory() as session:
        tenant = Tenant(id=uuid.uuid4(), name=f"Tenant {suffix}", slug=f"tenant-{suffix}")
        session.add(tenant)
        await session.flush()

        kb = KnowledgeBase(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            name=f"KB {suffix}",
            status="ACTIVE",
        )
        session.add(kb)
        await session.flush()

        doc = Document(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            knowledge_base_id=kb.id,
            filename=filename,
            safe_filename=filename,
            file_path=f"docs/{suffix}",
            file_size=file_size,
            mime_type=mime_type,
            file_hash=suffix,
            status="QUEUED",
        )
        session.add(doc)
        await session.flush()

        version = DocumentVersion(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            document_id=doc.id,
            version_num=1,
            file_path=doc.file_path,
            file_size=file_size,
            file_hash=suffix,
        )
        session.add(version)
        await session.flush()

        job = IngestionJob(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            knowledge_base_id=kb.id,
            document_id=doc.id,
            document_version_id=version.id,
            status="QUEUED",
            stage="QUEUED",
            progress_pct=10,
            max_retries=3,
            job_metadata={},
        )
        session.add(job)
        session.add(
            RetrievalConfig(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                knowledge_base_id=kb.id,
                vector_store=vector_store,
            )
        )
        await session.commit()

        return tenant.id, kb.id, doc.id, version.id, job.id


async def _execute_with_payload(session_factory, tenant_id: str, job_id, payload: bytes):
    async with session_factory() as session:
        service = IngestionService(session, tenant_id)
        service.storage = _StaticStorage(payload)
        return await service.execute_job(job_id)


async def _create_kb(db_session: AsyncSession, seed_data: dict) -> KnowledgeBase:
    kb = KnowledgeBase(
        tenant_id=seed_data["tenant_a"].id,
        name=f"Limits KB {uuid.uuid4().hex[:8]}",
        status="ACTIVE",
    )
    db_session.add(kb)
    await db_session.commit()
    await db_session.refresh(kb)
    return kb


def _make_zip(members: list[tuple[str, bytes]]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, payload in members:
            archive.writestr(name, payload)
    return buffer.getvalue()


class _FakeUploadFile:
    def __init__(self, payload: bytes, allowed_chunk: int) -> None:
        self.payload = payload
        self.allowed_chunk = allowed_chunk
        self.offset = 0
        self.calls: list[int] = []

    async def read(self, size: int = -1) -> bytes:
        assert size != -1, "unbounded read is forbidden"
        assert 0 < size <= self.allowed_chunk, f"read size {size} exceeds bound"
        self.calls.append(size)
        chunk = self.payload[self.offset : self.offset + size]
        self.offset += len(chunk)
        return chunk


# ---------------------------------------------------------------------------
# REL-1: bounded upload
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_oversized_upload_rejected_413_before_service_or_parser(
    client,
    db_session: AsyncSession,
    seed_data: dict,
    monkeypatch,
):
    kb = await _create_kb(db_session, seed_data)
    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(seed_data["tenant_a"].id),
    }

    upload_calls: list[dict] = []
    parser_calls: list[tuple] = []

    async def spy_upload(self, **kwargs):
        upload_calls.append(kwargs)
        raise AssertionError("oversized upload must not reach IngestionService")

    original_resolve = ParserRegistry.resolve_parser

    def spy_resolve(self, *args, **kwargs):
        parser_calls.append(args)
        return original_resolve(self, *args, **kwargs)

    monkeypatch.setattr(IngestionService, "upload_document", spy_upload)
    monkeypatch.setattr(ParserRegistry, "resolve_parser", spy_resolve)
    monkeypatch.setattr(settings, "MAX_FILE_SIZE_BYTES", 1024)

    response = await client.post(
        f"/api/v1/knowledge/{kb.id}/documents",
        files=[("files", ("too_big.txt", b"x" * 2048, "text/plain"))],
        headers=headers,
    )

    assert response.status_code == 413
    assert upload_calls == []
    assert parser_calls == []


@pytest.mark.asyncio
async def test_files_per_request_limit_rejected(
    client,
    db_session: AsyncSession,
    seed_data: dict,
):
    kb = await _create_kb(db_session, seed_data)
    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(seed_data["tenant_a"].id),
    }

    files = [
        ("files", (f"file_{index}.txt", b"small", "text/plain"))
        for index in range(settings.MAX_FILES_PER_REQUEST + 1)
    ]
    response = await client.post(
        f"/api/v1/knowledge/{kb.id}/documents",
        files=files,
        headers=headers,
    )

    assert response.status_code == 400
    assert "maximum files" in response.text.lower()


@pytest.mark.asyncio
async def test_upload_reads_in_bounded_chunks():
    payload = b"abcdefghij" * 100
    fake = _FakeUploadFile(payload, allowed_chunk=128)

    content = await read_upload_bounded(fake, max_bytes=4096, chunk_size=128)

    assert content == payload
    assert fake.calls
    assert max(fake.calls) == 128

    oversized = _FakeUploadFile(b"x" * 1024, allowed_chunk=128)
    with pytest.raises(UploadTooLargeError, match="maximum permitted size"):
        await read_upload_bounded(oversized, max_bytes=256, chunk_size=128)
    assert all(size == 128 for size in oversized.calls)


# ---------------------------------------------------------------------------
# REL-3: bounded concurrency
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_semaphore_bounds_concurrent_ingestion_to_one(
    limits_session_factory,
    monkeypatch,
):
    first = await _seed_job(limits_session_factory)
    second = await _seed_job(limits_session_factory)
    tracker = _ConcurrencyTracker()
    slow_parser = _SlowParser(tracker, delay=0.2)

    monkeypatch.setattr(settings, "INGESTION_MAX_CONCURRENCY", 1)
    monkeypatch.setattr(service_module, "async_session_factory", limits_session_factory)
    monkeypatch.setattr(service_module, "get_storage_provider", lambda: _StaticStorage(b"slow"))
    monkeypatch.setattr(ParserRegistry, "resolve_parser", lambda self, *a, **k: slow_parser)

    await asyncio.gather(
        run_ingestion_in_background(first[0], first[4]),
        run_ingestion_in_background(second[0], second[4]),
    )

    assert tracker.max_active == 1

    async with limits_session_factory() as session:
        jobs = list((await session.execute(select(IngestionJob))).scalars().all())
        chunks = list((await session.execute(select(DocumentChunk))).scalars().all())
        assert len(jobs) == 2
        assert all(job.status == "COMPLETED" for job in jobs)
        assert len(chunks) >= 2


# ---------------------------------------------------------------------------
# REL-2: archive expansion and traversal
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_archive_bomb_rejected_before_parser(
    limits_session_factory,
    monkeypatch,
):
    tenant_id, _kb_id, _doc_id, _version_id, job_id = await _seed_job(
        limits_session_factory,
        filename="bomb.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    payload = _make_zip([("word/document.xml", b"0" * (2 * MIB))])
    parser_calls: list[int] = []

    monkeypatch.setattr(settings, "MAX_ARCHIVE_EXPANSION_BYTES", MIB)
    monkeypatch.setattr(
        ParserRegistry,
        "resolve_parser",
        lambda self, *a, **k: parser_calls.append(1) or _StaticParser("never"),
    )

    job = await _execute_with_payload(limits_session_factory, tenant_id, job_id, payload)

    assert job.status == "FAILED"
    assert job.error_category == "IngestionLimitExceededError"
    assert parser_calls == []


def test_ooxml_page_counts_are_preflighted():
    deck = _make_zip(
        [
            ("ppt/slides/slide1.xml", b"one"),
            ("ppt/slides/slide2.xml", b"two"),
            ("ppt/slides/slide3.xml", b"three"),
        ]
    )
    with pytest.raises(IngestionLimitExceededError, match="pages/slides/sheets"):
        ingestion_limits.enforce_pre_extraction_limits(
            "deck.pptx",
            deck,
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            max_archive_expansion_bytes=MIB,
            max_document_pages=2,
        )

    sheets = _make_zip([("xl/worksheets/sheet1.xml", b"sheet")])
    details = ingestion_limits.enforce_pre_extraction_limits(
        "book.xlsx",
        sheets,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        max_archive_expansion_bytes=MIB,
        max_document_pages=2,
    )
    assert details["document_pages"] == 1

def test_zip_traversal_and_absolute_members_rejected():
    traversal = _make_zip([("../evil.txt", b"payload")])
    with pytest.raises(IngestionLimitExceededError, match="traversal"):
        validate_zip_archive(traversal, max_expansion_bytes=MIB)

    absolute = _make_zip([("/etc/passwd", b"payload")])
    with pytest.raises(IngestionLimitExceededError, match="absolute"):
        validate_zip_archive(absolute, max_expansion_bytes=MIB)


# ---------------------------------------------------------------------------
# REL-2: PDF page limit before OCR/parser
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_pdf_page_limit_rejected_before_parser_and_ocr(
    limits_session_factory,
    monkeypatch,
):
    tenant_id, _kb_id, _doc_id, _version_id, job_id = await _seed_job(
        limits_session_factory,
        filename="large.pdf",
        mime_type="application/pdf",
    )
    parser_calls: list[int] = []

    monkeypatch.setattr(settings, "MAX_DOCUMENT_PAGES", 2)
    monkeypatch.setattr(ingestion_limits, "count_pdf_pages", lambda content: 5)
    monkeypatch.setattr(
        ParserRegistry,
        "resolve_parser",
        lambda self, *a, **k: parser_calls.append(1) or _StaticParser("never"),
    )

    job = await _execute_with_payload(
        limits_session_factory,
        tenant_id,
        job_id,
        b"%PDF-1.7 fake content for page-limit preflight",
    )

    assert job.status == "FAILED"
    assert job.error_category == "IngestionLimitExceededError"
    assert "pages" in (job.error_message or "").lower()
    assert parser_calls == []


# ---------------------------------------------------------------------------
# REL-2: extracted-text byte limit
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_extracted_text_limit_enforced_in_utf8_bytes(
    limits_session_factory,
    monkeypatch,
):
    tenant_id, _kb_id, doc_id, version_id, job_id = await _seed_job(
        limits_session_factory,
        filename="multibyte.txt",
    )
    multibyte = "é" * 1200
    limit_bytes = 1000

    monkeypatch.setattr(settings, "MAX_EXTRACTED_TEXT_SIZE_BYTES", limit_bytes)
    monkeypatch.setattr(
        ParserRegistry,
        "resolve_parser",
        lambda self, *a, **k: _StaticParser(multibyte),
    )

    job = await _execute_with_payload(limits_session_factory, tenant_id, job_id, b"ignored")

    assert job.status == "COMPLETED"

    async with limits_session_factory() as session:
        version = await session.get(DocumentVersion, version_id)
        chunks = list(
            (
                await session.execute(
                    select(DocumentChunk).where(DocumentChunk.document_id == doc_id)
                )
            )
            .scalars()
            .all()
        )
        document = await session.get(Document, doc_id)

    stored = version.extracted_text or ""
    assert len(stored.encode("utf-8")) <= limit_bytes
    assert stored == "é" * (limit_bytes // 2)
    assert "\ufffd" not in stored
    assert chunks
    assert all(len(chunk.content.encode("utf-8")) <= limit_bytes for chunk in chunks)
    assert document.status == "COMPLETED"


# ---------------------------------------------------------------------------
# REL-2: processing duration
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_timeout_marks_job_and_document_failed_without_artifacts(
    limits_session_factory,
    monkeypatch,
):
    tenant_id, _kb_id, doc_id, version_id, job_id = await _seed_job(
        limits_session_factory,
        filename="slow.txt",
    )

    monkeypatch.setattr(settings, "MAX_PROCESSING_DURATION_SECONDS", 1)
    monkeypatch.setattr(
        ParserRegistry,
        "resolve_parser",
        lambda self, *a, **k: _SleepingParser(delay=2.0),
    )

    job = await _execute_with_payload(limits_session_factory, tenant_id, job_id, b"slow content")

    assert job.status == "FAILED"
    assert job.stage == "FAILED"
    assert job.error_category == "IngestionTimeoutError"
    assert job.completed_at is not None

    async with limits_session_factory() as session:
        document = await session.get(Document, doc_id)
        version = await session.get(DocumentVersion, version_id)
        chunks = list(
            (
                await session.execute(
                    select(DocumentChunk).where(
                        DocumentChunk.document_id == doc_id,
                        DocumentChunk.document_version_id == version_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        embeddings = list(
            (
                await session.execute(
                    select(ChunkEmbedding).where(ChunkEmbedding.document_id == doc_id)
                )
            )
            .scalars()
            .all()
        )

    assert document.status == "FAILED"
    assert version.extracted_text is None
    assert chunks == []
    assert embeddings == []


# ---------------------------------------------------------------------------
# Format preservation
# ---------------------------------------------------------------------------
def test_parser_registry_keeps_all_supported_formats():
    registry = get_parser_registry()
    extensions = registry.get_supported_extensions()
    required = {".pdf", ".docx", ".xlsx", ".pptx", ".csv", ".json", ".sql", ".md", ".txt"}
    assert required <= extensions

    for extension in sorted(required):
        parser = registry.resolve_parser(f"sample{extension}", b"neutral content")
        assert parser is not None
