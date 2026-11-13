"""Document Ingestion Service orchestrating upload, storage, parsing, OCR, and chunking."""

import asyncio
import hashlib
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.chunking import ChunkingConfig, get_chunking_registry
from app.core.config import settings
from app.database.session import async_session_factory
from app.models.knowledge import Document, IngestionJob
from app.ocr import OCRConfiguration, get_ocr_registry
from app.parsers import ExtractedDocument, get_parser_registry
from app.repositories.document_repository import DocumentRepository, IngestionJobRepository
from app.services.ingestion import limits as ingestion_limits
from app.services.ingestion.job_queue import (
    TERMINAL_JOB_STATUSES,
    claim_job,
    get_ingestion_semaphore,
    purge_failed_version_artifacts,
    sanitize_error_message,
)
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

    @staticmethod
    def _processing_remaining_seconds(start_time: float) -> float:
        """Remaining time in the configured per-job processing budget."""
        limit = max(1, int(settings.MAX_PROCESSING_DURATION_SECONDS or 1))
        return limit - (time.perf_counter() - start_time)

    async def _run_bounded(
        self,
        func: Any,
        *args: Any,
        timeout: float,
        stage: str,
        **kwargs: Any,
    ) -> Any:
        """Run blocking parser/OCR/chunking work in a worker thread with a bound.

        Python threads cannot be force-killed. When the deadline expires the
        await returns a timeout error and the job is failed, but a worker
        already inside ``func`` continues until it returns on its own. The
        semantics are therefore cooperative at await points, not a hard kill.
        """
        if timeout <= 0:
            raise ingestion_limits.IngestionTimeoutError(
                f"Document processing exceeded the maximum allowed duration during {stage}."
            )

        try:
            return await asyncio.wait_for(
                asyncio.to_thread(
                    ingestion_limits.resolve_awaitable_sync,
                    func,
                    *args,
                    **kwargs,
                ),
                timeout=timeout,
            )
        except TimeoutError as exc:
            raise ingestion_limits.IngestionTimeoutError(
                f"Document processing exceeded the maximum allowed duration during {stage}."
            ) from exc

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

        # 5. Save the object, then persist metadata. If any database write fails
        # after the object exists, delete the just-stored object so a failed
        # upload cannot leave an orphan behind.
        storage_saved = False
        try:
            await self.storage.save(str(self.tenant_id), storage_key, content)
            storage_saved = True

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
        except Exception as exc:
            try:
                await self.session.rollback()
            except Exception:
                pass
            if storage_saved:
                try:
                    await self.storage.delete(str(self.tenant_id), storage_key)
                except Exception as delete_exc:
                    logger.error(
                        "Compensating storage delete failed for tenant %s (%s)",
                        self.tenant_id,
                        type(delete_exc).__name__,
                    )
            if isinstance(exc, ValueError):
                raise
            logger.error(
                "Document upload persistence failed for tenant %s (%s)",
                self.tenant_id,
                type(exc).__name__,
            )
            if storage_saved:
                raise RuntimeError(
                    "Document upload persistence failed; the stored object was cleaned up."
                ) from exc
            raise RuntimeError("Document upload failed; no document was created.") from exc

    async def _current_job_status(self, job_id: uuid.UUID) -> str | None:
        """Read the latest committed job status without flushing pipeline work."""
        with self.session.no_autoflush:
            result = await self.session.execute(
                select(IngestionJob.status).where(IngestionJob.id == job_id)
            )
        return result.scalar_one_or_none()

    async def _finalize_cancelled_job(
        self, job_id: uuid.UUID, document_id: uuid.UUID | None
    ) -> None:
        """Keep cancellation terminal and release any document lock."""
        if document_id:
            await self.session.execute(
                update(Document)
                .where(
                    Document.id == document_id,
                    Document.tenant_id == self.tenant_id,
                    Document.status.in_(("QUEUED", "PROCESSING")),
                )
                .values(status="CANCELLED")
                .execution_options(synchronize_session=False)
            )
        await self.session.commit()

    async def _settle_terminal_conflict(
        self, job_id: uuid.UUID, document_id: uuid.UUID | None
    ) -> IngestionJob:
        """Reload a job whose row changed under us and align its document."""
        refreshed = await self.job_repo.get_by_id(job_id)
        if not refreshed:
            raise ValueError(f"Ingestion job not found after terminal conflict: {job_id}")

        if document_id and refreshed.status == "CANCELLED":
            await self._finalize_cancelled_job(job_id, document_id)
            refreshed = await self.job_repo.get_by_id(job_id) or refreshed
        elif document_id and refreshed.status == "FAILED":
            await self.session.execute(
                update(Document)
                .where(
                    Document.id == document_id,
                    Document.tenant_id == self.tenant_id,
                    Document.status.notin_(("DELETED", "CANCELLED")),
                )
                .values(status="FAILED")
                .execution_options(synchronize_session=False)
            )
            await self.session.commit()
        else:
            await self.session.commit()

        return refreshed

    async def _handle_pipeline_failure(
        self, job_id: uuid.UUID, exc: Exception, start_time: float
    ) -> IngestionJob:
        """Roll back a failed pipeline and persist a retryable or terminal state.

        Resource-limit and timeout violations are permanent: retrying the same
        document cannot succeed, so the job/document become terminal FAILED and
        any partial chunks or embeddings for the failed version are purged.
        """
        is_permanent = isinstance(exc, ingestion_limits.PERMANENT_INGESTION_ERRORS)
        if is_permanent:
            logger.warning("Ingestion limit failure for job %s (%s)", job_id, type(exc).__name__)
        else:
            logger.exception("Ingestion failed for job %s (%s)", job_id, type(exc).__name__)
        try:
            await self.session.rollback()
        except Exception:
            logger.warning("Rollback after ingestion failure raised for job %s", job_id)

        job = await self.job_repo.get_by_id(job_id)
        if not job:
            raise ValueError(f"Ingestion job not found after failure: {job_id}")

        if job.status in TERMINAL_JOB_STATUSES:
            if job.status == "CANCELLED":
                await self._finalize_cancelled_job(job.id, job.document_id)
                refreshed = await self.job_repo.get_by_id(job.id)
                return refreshed or job
            return job

        job.retry_count += 1
        job.duration_ms = int((time.perf_counter() - start_time) * 1000)
        job.error_category = type(exc).__name__
        job.error_message = sanitize_error_message(exc)

        doc = await self.doc_repo.get_by_id(job.document_id) if job.document_id else None

        if not is_permanent and job.retry_count <= job.max_retries:
            job.status = "QUEUED"
            job.stage = "RETRY_QUEUED"
            job.started_at = None
            job.completed_at = None
            if doc and doc.status in ("QUEUED", "PROCESSING"):
                doc.status = "QUEUED"
            await self.job_repo.record_event(
                job_id=job.id,
                document_id=job.document_id,
                stage="FAILURE",
                status="RETRY_SCHEDULED",
                message=(
                    f"Job failed (attempt {job.retry_count}/{job.max_retries}). "
                    "Requeued for retry."
                ),
                details={"error_category": type(exc).__name__},
            )
        else:
            job.status = "FAILED"
            job.stage = "FAILED"
            job.completed_at = datetime.now(timezone.utc)
            if doc and doc.status not in ("DELETED", "CANCELLED"):
                doc.status = "FAILED"
            removed_chunks = await purge_failed_version_artifacts(
                self.session,
                self.tenant_id,
                job.document_id,
                job.document_version_id,
            )
            if is_permanent:
                failure_message = (
                    f"Job permanently failed due to a resource limit after "
                    f"{job.retry_count} attempt(s). Removed {removed_chunks} partial "
                    "chunk(s) for the failed version."
                )
            else:
                failure_message = (
                    f"Job permanently failed after {job.retry_count} attempts. "
                    f"Removed {removed_chunks} partial chunk(s) for the failed version."
                )
            await self.job_repo.record_event(
                job_id=job.id,
                document_id=job.document_id,
                stage="FAILURE",
                status="FAILED",
                message=failure_message,
                details={
                    "error_category": type(exc).__name__,
                    "chunks_removed": removed_chunks,
                    "permanent": is_permanent,
                },
            )

        await self.session.commit()
        return job

    async def execute_job(
        self, job_id: uuid.UUID | str, *, claimed: bool = False
    ) -> IngestionJob:
        """Run the ingestion pipeline only for a job this caller owns.

        Direct callers (upload/retry/reprocess task) leave ``claimed=False``;
        a QUEUED job is claimed here. Dispatcher and worker callers pass
        ``claimed=True`` after their atomic claim. A PROCESSING job without
        that hand-off belongs to another runner and is left untouched.
        """
        target_job_id = uuid.UUID(str(job_id)) if isinstance(job_id, str) else job_id
        start_time = time.perf_counter()
        job = await self.job_repo.get_by_id(target_job_id)
        if not job:
            raise ValueError(f"Ingestion job not found: {job_id}")

        job_uuid = job.id
        document_uuid = job.document_id

        if job.status == "CANCELLED":
            await self._finalize_cancelled_job(job_uuid, document_uuid)
            return job
        if job.status in ("COMPLETED", "FAILED"):
            return job

        if job.status == "QUEUED":
            if not await claim_job(self.session, job_uuid):
                refreshed = await self.job_repo.get_by_id(job_uuid)
                return refreshed or job
            await self.session.refresh(job)
        elif job.status == "PROCESSING":
            if not claimed:
                # The job is owned by another dispatcher/worker path.
                return job
        else:
            # PENDING and unknown states are never processed without a claim.
            return job

        doc = await self.doc_repo.get_by_id(document_uuid)
        if not doc:
            job.status = "FAILED"
            job.stage = "FAILED"
            job.error_category = "DOCUMENT_NOT_FOUND"
            job.error_message = "Associated document was deleted or not found."
            job.completed_at = datetime.now(timezone.utc)
            await self.session.commit()
            return job

        if doc.status == "DELETED":
            job.status = "FAILED"
            job.stage = "FAILED"
            job.error_category = "DOCUMENT_DELETED"
            job.error_message = "Associated document was deleted."
            job.completed_at = datetime.now(timezone.utc)
            await self.session.commit()
            return job

        if doc.status == "CANCELLED":
            # A cancelled document must not be resurrected by a dispatch race.
            job.status = "CANCELLED"
            job.stage = "CANCELLED"
            job.completed_at = datetime.now(timezone.utc)
            await self.session.commit()
            return job

        transition = await self.session.execute(
            update(IngestionJob)
            .where(IngestionJob.id == job_uuid, IngestionJob.status == "PROCESSING")
            .values(
                stage="PARSING",
                progress_pct=20,
                started_at=job.started_at or datetime.now(timezone.utc),
            )
            .execution_options(synchronize_session=False)
        )
        if transition.rowcount != 1:
            await self.session.rollback()
            return await self._settle_terminal_conflict(job_uuid, document_uuid)

        doc.status = "PROCESSING"
        await self.session.commit()
        await self.session.refresh(job)

        if job.status == "CANCELLED":
            await self._finalize_cancelled_job(job_uuid, document_uuid)
            return job

        try:
            # Fetch KB ingestion configuration
            kb_config = await self.doc_repo.get_ingestion_config(doc.knowledge_base_id)
            chunking_strategy_name = kb_config.chunking_strategy if kb_config else "recursive"
            chunk_size = kb_config.chunk_size if kb_config else 1000
            chunk_overlap = kb_config.chunk_overlap if kb_config else 200
            ocr_enabled = kb_config.ocr_enabled if kb_config else settings.OCR_ENABLED_DEFAULT
            ocr_provider_name = (
                kb_config.ocr_provider if kb_config else settings.OCR_DEFAULT_PROVIDER
            )
            ocr_language = (
                kb_config.ocr_language if kb_config else settings.OCR_DEFAULT_LANGUAGE
            )

            if await self._current_job_status(job_uuid) == "CANCELLED":
                await self._finalize_cancelled_job(job_uuid, document_uuid)
                refreshed = await self.job_repo.get_by_id(job_uuid)
                return refreshed or job

            # 1. Load document bytes from storage
            content = await self.storage.get(str(self.tenant_id), doc.file_path)

            # 2. Pre-parse resource checks: ZIP expansion/member safety for
            # OOXML containers and page count for PDFs. Both run before the
            # parser is selected, so rejected files are never extracted.
            max_archive_bytes = max(0, int(settings.MAX_ARCHIVE_EXPANSION_BYTES or 0))
            max_pages = max(1, int(settings.MAX_DOCUMENT_PAGES or 1))
            max_text_bytes = max(0, int(settings.MAX_EXTRACTED_TEXT_SIZE_BYTES or 0))
            await self._run_bounded(
                ingestion_limits.enforce_pre_extraction_limits,
                doc.filename,
                content,
                doc.mime_type,
                max_archive_expansion_bytes=max_archive_bytes,
                max_document_pages=max_pages,
                timeout=self._processing_remaining_seconds(start_time),
                stage="preflight inspection",
            )

            # 3. Select parser from registry
            parser = self.parser_registry.resolve_parser(doc.filename, content, doc.mime_type)
            await self.job_repo.record_event(
                job_id=job.id,
                document_id=doc.id,
                stage="PARSING",
                status="STARTED",
                message=f"Parser selected: {parser.parser_name}",
            )

            # 4. Extract structured document in a worker thread. The await is
            # bounded; a parser already running in the thread cannot be killed.
            extracted_doc: ExtractedDocument = await self._run_bounded(
                parser.extract,
                content,
                doc.filename,
                doc.mime_type,
                timeout=self._processing_remaining_seconds(start_time),
                stage="parser extraction",
            )

            ingestion_limits.enforce_extracted_page_limit(len(extracted_doc.pages), max_pages)
            text_stats = ingestion_limits.truncate_extracted_text(extracted_doc, max_text_bytes)
            if text_stats["truncated"]:
                await self.job_repo.record_event(
                    job_id=job.id,
                    document_id=doc.id,
                    stage="LIMITS",
                    status="WARNING",
                    message=(
                        "Extracted text was truncated at a UTF-8 character boundary "
                        f"to {max_text_bytes} bytes."
                    ),
                    details=text_stats,
                )

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
                ocr_res = await self._run_bounded(
                    ocr_prov.process_pdf,
                    content,
                    scanned_pages,
                    ocr_cfg,
                    timeout=self._processing_remaining_seconds(start_time),
                    stage="OCR",
                )
                if ocr_res.success:
                    ocr_applied = True
                    # Append OCR recognized text to document text, then re-apply
                    # the byte limit so persistence and embeddings stay bounded.
                    if ocr_res.text:
                        extracted_doc.text += f"\n\n### OCR Extracted Text:\n{ocr_res.text}"
                        ocr_text_stats = ingestion_limits.truncate_extracted_text(
                            extracted_doc, max_text_bytes
                        )
                        if ocr_text_stats["truncated"]:
                            await self.job_repo.record_event(
                                job_id=job.id,
                                document_id=doc.id,
                                stage="LIMITS",
                                status="WARNING",
                                message=(
                                    "OCR text was truncated at a UTF-8 character boundary "
                                    f"to {max_text_bytes} bytes."
                                ),
                                details=ocr_text_stats,
                            )
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

            chunks = await self._run_bounded(
                strategy.chunk,
                extracted_doc,
                context_meta,
                chunking_cfg,
                timeout=self._processing_remaining_seconds(start_time),
                stage="chunking",
            )

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
                latest_version.extracted_text = ingestion_limits.truncate_utf8_text(
                    extracted_doc.text, max_text_bytes
                )[0]
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
            # Cancellation wins over completion if it was committed during the
            # pipeline; do not overwrite a terminal cancellation.
            if await self._current_job_status(job_uuid) == "CANCELLED":
                await self.session.rollback()
                await self._finalize_cancelled_job(job_uuid, document_uuid)
                refreshed = await self.job_repo.get_by_id(job_uuid)
                return refreshed or job

            duration_ms = int((time.perf_counter() - start_time) * 1000)
            now = datetime.now(timezone.utc)

            # Persist pending stage/progress writes first so the conditional
            # terminal UPDATE is the last write to the job row.
            await self.session.flush()
            terminal = await self.session.execute(
                update(IngestionJob)
                .where(
                    IngestionJob.id == job_uuid,
                    IngestionJob.status == "PROCESSING",
                )
                .values(
                    status="COMPLETED",
                    stage="COMPLETED",
                    progress_pct=100,
                    duration_ms=duration_ms,
                    completed_at=now,
                    error_category=None,
                    error_message=None,
                )
                .execution_options(synchronize_session=False)
            )
            if terminal.rowcount != 1:
                await self.session.rollback()
                return await self._settle_terminal_conflict(job_uuid, document_uuid)

            doc.status = "COMPLETED"
            doc.total_pages = len(extracted_doc.pages)
            doc.total_chunks = len(saved_chunks)

            await self.job_repo.record_event(
                job_id=job_uuid,
                document_id=doc.id,
                stage="COMPLETION",
                status="COMPLETED",
                message=f"Ingestion succeeded. Generated {len(saved_chunks)} chunks in {duration_ms} ms.",
                details={"chunks_count": len(saved_chunks), "duration_ms": duration_ms},
            )

            await self.session.commit()
            await self.session.refresh(job)
            logger.info(f"Ingestion job completed: job={job_uuid} doc={doc.id} chunks={len(saved_chunks)}")
            return job

        except Exception as e:
            return await self._handle_pipeline_failure(job_uuid, e, start_time)

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
    """Safely spawn ingestion execution in a background session.

    Every upload/retry/reprocess path enters through this function, so the
    shared semaphore bounds upload-triggered tasks together with dispatcher and
    worker execution. Waiting for a slot happens before a session is opened.
    """
    async with get_ingestion_semaphore():
        async with async_session_factory() as session:
            service = IngestionService(session, tenant_id)
            await service.execute_job(job_id)
