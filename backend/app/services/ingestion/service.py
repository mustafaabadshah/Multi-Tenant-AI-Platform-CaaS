"""Document Ingestion Service orchestrating upload, storage, parsing, OCR, and chunking."""

import hashlib
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chunking import ChunkingConfig, get_chunking_registry
from app.core.config import settings
from app.database.session import async_session_factory
from app.models.knowledge import Document, IngestionJob
from app.ocr import OCRConfiguration, get_ocr_registry
from app.parsers import ExtractedDocument, get_parser_registry
from app.repositories.document_repository import DocumentRepository, IngestionJobRepository
from app.storage import get_storage_provider, sanitize_filename

logger = logging.getLogger("mmaip.ingestion")


class IngestionService:
    """Enterprise Document Ingestion Service with strict tenant isolation."""

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID | str):
        self.session = session
        self.tenant_id = uuid.UUID(str(tenant_id)) if isinstance(tenant_id, str) else tenant_id
        self.doc_repo = DocumentRepository(session, self.tenant_id)
        self.job_repo = IngestionJobRepository(session, self.tenant_id)
        self.storage = get_storage_provider()
        self.parser_registry = get_parser_registry()
        self.ocr_registry = get_ocr_registry()
        self.chunking_registry = get_chunking_registry()

    async def upload_document(
        self,
        knowledge_base_id: uuid.UUID | str,
        filename: str,
        content: bytes,
        mime_type: str | None = None,
    ) -> tuple[Document, IngestionJob, bool]:
        """Validate, store, create document version, and enqueue ingestion job.

        Returns (Document, IngestionJob, is_duplicate).
        """
        kb_id = uuid.UUID(str(knowledge_base_id)) if isinstance(knowledge_base_id, str) else knowledge_base_id
        # 1. Enforce file size limit
        file_size = len(content)
        if file_size > settings.MAX_FILE_SIZE_BYTES:
            raise ValueError(
                f"File size ({file_size} bytes) exceeds maximum permitted limit ({settings.MAX_FILE_SIZE_BYTES} bytes)."
            )

        # 2. Calculate SHA-256 checksum
        file_hash = hashlib.sha256(content).hexdigest()

        # 3. Duplicate detection within knowledge base
        existing_doc = await self.doc_repo.get_by_hash(kb_id, file_hash)
        if existing_doc:
            logger.info(
                f"Duplicate upload detected: tenant={self.tenant_id} doc={existing_doc.id} hash={file_hash}"
            )
            # Create a new ingestion job for reprocessing existing doc if needed
            job = await self.job_repo.create(
                knowledge_base_id=kb_id,
                document_id=existing_doc.id,
                status="QUEUED",
                stage="QUEUED",
                progress_pct=10,
                job_metadata={"is_duplicate": True, "file_hash": file_hash},
            )
            await self.session.commit()
            return existing_doc, job, True

        # 4. Safe filename and storage key
        safe_name = sanitize_filename(filename)
        doc_id = uuid.uuid4()
        storage_key = self.storage.build_storage_key(
            tenant_id=str(self.tenant_id),
            knowledge_base_id=str(kb_id),
            document_id=str(doc_id),
            version_number=1,
            filename=safe_name,
        )

        # 5. Save to storage abstraction
        await self.storage.save(str(self.tenant_id), storage_key, content)

        # 6. Detect verified MIME type
        detected_mime = self.parser_registry.detect_mime_type(content, filename)

        # 7. Create Document record
        document = Document(
            id=doc_id,
            tenant_id=self.tenant_id,
            knowledge_base_id=kb_id,
            filename=filename,
            safe_filename=safe_name,
            file_path=storage_key,
            file_size=file_size,
            mime_type=detected_mime,
            file_hash=file_hash,
            status="QUEUED",
            current_version_num=1,
            metadata_json={"original_mime": mime_type},
        )
        self.session.add(document)
        await self.session.flush()

        # 8. Create DocumentVersion record
        version = await self.doc_repo.create_version(
            document_id=document.id,
            version_num=1,
            file_path=storage_key,
            file_size=file_size,
            file_hash=file_hash,
        )

        # 9. Create IngestionJob record
        job = await self.job_repo.create(
            knowledge_base_id=kb_id,
            document_id=document.id,
            document_version_id=version.id,
            status="QUEUED",
            stage="QUEUED",
            progress_pct=10,
            job_metadata={"file_hash": file_hash, "version_num": 1},
        )

        # Record initial event
        await self.job_repo.record_event(
            job_id=job.id,
            document_id=document.id,
            stage="UPLOAD",
            status="COMPLETED",
            message=f"Document uploaded safely. Size: {file_size} bytes. Stored at: {storage_key}",
            details={"file_size": file_size, "mime_type": detected_mime},
        )

        await self.session.commit()
        return document, job, False

    async def execute_job(self, job_id: uuid.UUID | str) -> IngestionJob:
        """Run the full ingestion pipeline synchronously for a job.

        Pipeline: Validation -> Load -> Parse -> OCR (if required) -> Chunk -> Persist.
        """
        target_job_id = uuid.UUID(str(job_id)) if isinstance(job_id, str) else job_id
        start_time = time.perf_counter()
        job = await self.job_repo.get_by_id(target_job_id)
        if not job:
            raise ValueError(f"Ingestion job not found: {job_id}")

        if job.status in ("COMPLETED", "CANCELLED"):
            return job

        doc = await self.doc_repo.get_by_id(job.document_id)
        if not doc:
            job.status = "FAILED"
            job.error_message = "Associated document was deleted or not found."
            await self.session.commit()
            return job

        # Fetch KB ingestion configuration
        kb_config = await self.doc_repo.get_ingestion_config(doc.knowledge_base_id)
        chunking_strategy_name = kb_config.chunking_strategy if kb_config else "recursive"
        chunk_size = kb_config.chunk_size if kb_config else 1000
        chunk_overlap = kb_config.chunk_overlap if kb_config else 200
        ocr_enabled = kb_config.ocr_enabled if kb_config else settings.OCR_ENABLED_DEFAULT
        ocr_provider_name = kb_config.ocr_provider if kb_config else settings.OCR_DEFAULT_PROVIDER
        ocr_language = kb_config.ocr_language if kb_config else settings.OCR_DEFAULT_LANGUAGE

        job.status = "PROCESSING"
        job.stage = "PARSING"
        job.progress_pct = 20
        job.started_at = datetime.now(timezone.utc)
        doc.status = "PROCESSING"
        await self.session.commit()

        try:
            # 1. Load document bytes from storage
            content = await self.storage.get(str(self.tenant_id), doc.file_path)

            # 2. Select parser from registry
            parser = self.parser_registry.resolve_parser(doc.filename, content, doc.mime_type)
            await self.job_repo.record_event(
                job_id=job.id,
                document_id=doc.id,
                stage="PARSING",
                status="STARTED",
                message=f"Parser selected: {parser.parser_name}",
            )

            # 3. Extract structured document
            extracted_doc: ExtractedDocument = await parser.extract(content, doc.filename, doc.mime_type)

            job.stage = "PARSED"
            job.progress_pct = 50
            await self.job_repo.record_event(
                job_id=job.id,
                document_id=doc.id,
                stage="PARSING",
                status="COMPLETED",
                message=f"Extracted {len(extracted_doc.text)} characters across {len(extracted_doc.pages)} pages/sheets.",
                details=extracted_doc.extraction_stats,
            )

            # 4. Handle OCR if required
            ocr_applied = False
            has_scanned = any(p.is_scanned for p in extracted_doc.pages)
            if has_scanned and ocr_enabled:
                job.stage = "OCR_REQUIRED"
                job.progress_pct = 60
                await self.job_repo.record_event(
                    job_id=job.id,
                    document_id=doc.id,
                    stage="OCR",
                    status="STARTED",
                    message=f"Running OCR with provider '{ocr_provider_name}' on scanned pages.",
                )

                ocr_prov = self.ocr_registry.get_provider(ocr_provider_name)
                scanned_pages = [p.page_number for p in extracted_doc.pages if p.is_scanned]
                ocr_cfg = OCRConfiguration(
                    enabled=True,
                    provider=ocr_provider_name,
                    language=ocr_language,
                )
                ocr_res = await ocr_prov.process_pdf(content, scanned_pages, ocr_cfg)
                if ocr_res.success:
                    ocr_applied = True
                    # Append OCR recognized text to document text
                    if ocr_res.text:
                        extracted_doc.text += f"\n\n### OCR Extracted Text:\n{ocr_res.text}"
                    await self.job_repo.record_event(
                        job_id=job.id,
                        document_id=doc.id,
                        stage="OCR",
                        status="COMPLETED",
                        message=f"OCR completed successfully with {len(ocr_res.pages)} pages processed.",
                    )
                else:
                    await self.job_repo.record_event(
                        job_id=job.id,
                        document_id=doc.id,
                        stage="OCR",
                        status="WARNING",
                        message=f"OCR reported non-fatal warning: {ocr_res.error_message}",
                    )

            # 5. Chunking Stage
            job.stage = "CHUNKING"
            job.progress_pct = 75
            strategy = self.chunking_registry.get_strategy(chunking_strategy_name)
            chunking_cfg = ChunkingConfig(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                strategy=chunking_strategy_name,
            )

            context_meta = {
                "tenant_id": self.tenant_id,
                "knowledge_base_id": doc.knowledge_base_id,
                "document_id": doc.id,
                "document_version_id": job.document_version_id,
            }

            chunks = strategy.chunk(extracted_doc, context_meta, chunking_cfg)

            # 6. Persist Chunks & Update Version Record
            chunks_data = [
                {
                    "chunk_index": c.metadata.chunk_index,
                    "content": c.content,
                    "character_count": c.metadata.character_count,
                    "token_count": c.metadata.token_count,
                    "page_number": c.metadata.page_number,
                    "heading_path": c.metadata.heading_path,
                    "chunk_hash": c.metadata.chunk_hash,
                    "chunking_strategy": c.metadata.chunking_strategy,
                    "metadata": c.metadata.to_dict(),
                }
                for c in chunks
            ]
            saved_chunks = await self.doc_repo.save_chunks(
                knowledge_base_id=doc.knowledge_base_id,
                document_id=doc.id,
                document_version_id=job.document_version_id,
                chunks_data=chunks_data,
            )

            # Update DocumentVersion record with extracted data
            latest_version = await self.doc_repo.get_latest_version(doc.id)
            if latest_version:
                latest_version.extracted_text = extracted_doc.text[:settings.MAX_EXTRACTED_TEXT_SIZE_BYTES]
                latest_version.structured_data = extracted_doc.to_dict()
                latest_version.extraction_stats = extracted_doc.extraction_stats
                latest_version.parser_name = parser.parser_name
                latest_version.parser_version = parser.parser_version
                latest_version.ocr_applied = ocr_applied
                latest_version.ocr_provider = ocr_provider_name if ocr_applied else None
                latest_version.ocr_language = ocr_language if ocr_applied else None

            # 6b. Embedding & Vector Store Indexing Stage (Milestone 03)
            from app.embeddings.service import EmbeddingService
            from app.repositories.retrieval_repository import RetrievalRepository
            from app.vectorstores.base import VectorPoint
            from app.vectorstores.registry import get_vector_store

            ret_repo = RetrievalRepository(self.session, self.tenant_id)
            ret_cfg = await ret_repo.get_or_create_config(doc.knowledge_base_id)

            if ret_cfg.vector_store == "fts":
                job.stage = "INDEXED"
                job.progress_pct = 95
                await self.job_repo.record_event(
                    job_id=job.id,
                    document_id=doc.id,
                    stage="INDEXING",
                    status="COMPLETED",
                    message="FTS-only mode active. Lexical search indexed immediately without embeddings.",
                    details={"vector_store": "fts"},
                )
            else:
                job.stage = "EMBEDDING"
                job.progress_pct = 85
                await self.job_repo.record_event(
                    job_id=job.id,
                    document_id=doc.id,
                    stage="EMBEDDING",
                    status="STARTED",
                    message=f"Generating embeddings using '{ret_cfg.embedding_provider}' ({ret_cfg.embedding_model}).",
                    details={
                        "provider": ret_cfg.embedding_provider,
                        "model": ret_cfg.embedding_model,
                        "dimensions": ret_cfg.embedding_dimensions,
                    },
                )

                try:
                    emb_service = EmbeddingService(self.session, self.tenant_id)
                    generated_embeddings = await emb_service.embed_chunks(
                        knowledge_base_id=doc.knowledge_base_id,
                        chunks=saved_chunks,
                        ret_config=ret_cfg,
                    )

                    if ret_cfg.vector_store == "qdrant":
                        job.stage = "INDEXING"
                        job.progress_pct = 95
                        qdrant_store = get_vector_store("qdrant")
                        qpoints = [
                            VectorPoint(
                                id=str(emb.chunk_id),
                                vector=emb.vector or [],
                                dimensions=emb.dimensions,
                                payload={
                                    "document_id": str(doc.id),
                                    "document_version_id": str(job.document_version_id) if job.document_version_id else None,
                                    "chunk_id": str(emb.chunk_id),
                                    "embedding_version": ret_cfg.embedding_version,
                                    "provider": emb.provider,
                                    "model": emb.model,
                                    "content": next((c.content for c in saved_chunks if c.id == emb.chunk_id), ""),
                                    "document_title": doc.filename,
                                    "department_id": str(doc.department_id) if doc.department_id else None,
                                    "access_level": doc.access_level,
                                },
                            )
                            for emb in generated_embeddings
                        ]
                        await qdrant_store.upsert(qpoints, self.tenant_id, doc.knowledge_base_id)

                    await self.job_repo.record_event(
                        job_id=job.id,
                        document_id=doc.id,
                        stage="INDEXING",
                        status="COMPLETED",
                        message=f"Indexed {len(generated_embeddings)} vectors into {ret_cfg.vector_store}.",
                        details={"vector_store": ret_cfg.vector_store, "vectors_count": len(generated_embeddings)},
                    )
                except (TimeoutError, ConnectionError, PermissionError) as emb_err:
                    logger.warning(f"Embedding generation warning for job {job.id}: {emb_err}")
                    await self.job_repo.record_event(
                        job_id=job.id,
                        document_id=doc.id,
                        stage="EMBEDDING",
                        status="WARNING",
                        message=f"Embedding provider unavailable ({emb_err}). Chunks saved and available for lexical retrieval.",
                        details={"warning": str(emb_err)},
                    )

            # 7. Complete Job & Document Status
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            doc.status = "COMPLETED"
            doc.total_pages = len(extracted_doc.pages)
            doc.total_chunks = len(saved_chunks)

            job.status = "COMPLETED"
            job.stage = "COMPLETED"
            job.progress_pct = 100
            job.duration_ms = duration_ms
            job.completed_at = datetime.now(timezone.utc)

            await self.job_repo.record_event(
                job_id=job.id,
                document_id=doc.id,
                stage="COMPLETION",
                status="COMPLETED",
                message=f"Ingestion succeeded. Generated {len(saved_chunks)} chunks in {duration_ms} ms.",
                details={"chunks_count": len(saved_chunks), "duration_ms": duration_ms},
            )

            await self.session.commit()
            logger.info(f"Ingestion job completed: job={job.id} doc={doc.id} chunks={len(saved_chunks)}")
            return job

        except Exception as e:
            logger.exception(f"Ingestion failed for job {job.id}: {e}")
            job.retry_count += 1
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            job.duration_ms = duration_ms
            job.error_category = type(e).__name__
            job.error_message = str(e)

            if job.retry_count <= job.max_retries:
                job.status = "QUEUED"
                job.stage = "RETRY_QUEUED"
                await self.job_repo.record_event(
                    job_id=job.id,
                    document_id=doc.id,
                    stage="FAILURE",
                    status="RETRY_SCHEDULED",
                    message=f"Job failed (attempt {job.retry_count}/{job.max_retries}): {e}",
                    details={"error_category": type(e).__name__},
                )
            else:
                job.status = "FAILED"
                job.stage = "FAILED"
                doc.status = "FAILED"
                await self.job_repo.record_event(
                    job_id=job.id,
                    document_id=doc.id,
                    stage="FAILURE",
                    status="FAILED",
                    message=f"Job permanently failed after {job.retry_count} retries: {e}",
                    details={"error_category": type(e).__name__},
                )

            await self.session.commit()
            return job

    async def reindex_knowledge_base(self, knowledge_base_id: uuid.UUID | str) -> Any:
        """Trigger re-embedding and re-indexing for all active document chunks in a Knowledge Base."""
        from app.embeddings.service import EmbeddingService
        from app.models.knowledge import Document, DocumentChunk
        from app.repositories.retrieval_repository import RetrievalRepository
        from app.vectorstores.base import VectorPoint
        from app.vectorstores.registry import get_vector_store

        kb_id = uuid.UUID(str(knowledge_base_id)) if isinstance(knowledge_base_id, str) else knowledge_base_id
        ret_repo = RetrievalRepository(self.session, self.tenant_id)
        ret_cfg = await ret_repo.get_or_create_config(kb_id)

        # 1. Fetch all active chunks in this KB
        stmt = (
            select(DocumentChunk)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(
                DocumentChunk.tenant_id == self.tenant_id,
                DocumentChunk.knowledge_base_id == kb_id,
                Document.status != "DELETED",
            )
            .order_by(DocumentChunk.document_id, DocumentChunk.chunk_index)
        )
        chunks = list((await self.session.execute(stmt)).scalars().all())

        # 2. Create tracked EmbeddingJob
        emb_job = await ret_repo.create_embedding_job(
            knowledge_base_id=kb_id,
            embedding_version=ret_cfg.embedding_version,
            total_chunks=len(chunks),
        )
        emb_job.status = "PROCESSING"
        emb_job.stage = "EMBEDDING"
        await self.session.commit()

        if ret_cfg.vector_store == "fts" or not chunks:
            emb_job.status = "COMPLETED"
            emb_job.stage = "COMPLETED"
            emb_job.processed_chunks = len(chunks)
            emb_job.completed_at = datetime.now(timezone.utc)
            await self.session.commit()
            return emb_job

        try:
            emb_service = EmbeddingService(self.session, self.tenant_id)
            embeddings = await emb_service.embed_chunks(
                knowledge_base_id=kb_id,
                chunks=chunks,
                ret_config=ret_cfg,
            )

            if ret_cfg.vector_store == "qdrant":
                emb_job.stage = "INDEXING"
                await self.session.commit()

                qdrant_store = get_vector_store("qdrant")
                qpoints = [
                    VectorPoint(
                        id=str(emb.chunk_id),
                        vector=emb.vector or [],
                        dimensions=emb.dimensions,
                        payload={
                            "document_id": str(emb.document_id),
                            "chunk_id": str(emb.chunk_id),
                            "embedding_version": ret_cfg.embedding_version,
                            "provider": emb.provider,
                            "model": emb.model,
                            "content": next((c.content for c in chunks if c.id == emb.chunk_id), ""),
                        },
                    )
                    for emb in embeddings
                ]
                await qdrant_store.upsert(qpoints, self.tenant_id, kb_id)

            emb_job.status = "COMPLETED"
            emb_job.stage = "COMPLETED"
            emb_job.processed_chunks = len(embeddings)
            emb_job.completed_at = datetime.now(timezone.utc)
            await self.session.commit()
            return emb_job

        except Exception as exc:
            logger.exception(f"Reindexing failed for KB {kb_id}: {exc}")
            emb_job.status = "FAILED"
            emb_job.stage = "FAILED"
            emb_job.error_message = str(exc)
            emb_job.completed_at = datetime.now(timezone.utc)
            await self.session.commit()
            raise



async def run_ingestion_in_background(tenant_id: uuid.UUID, job_id: uuid.UUID) -> None:
    """Safely spawn ingestion execution in a background session."""
    async with async_session_factory() as session:
        service = IngestionService(session, tenant_id)
        await service.execute_job(job_id)
