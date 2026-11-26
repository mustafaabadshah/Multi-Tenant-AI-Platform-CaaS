"""Document and Ingestion repositories strictly enforcing tenant boundaries."""

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.knowledge import (
    Document,
    DocumentChunk,
    DocumentVersion,
    IngestionConfig,
    IngestionEvent,
    IngestionJob,
)
from app.repositories.base import TenantScopedRepository


class DocumentRepository(TenantScopedRepository[Document]):
    """Tenant-scoped repository for document entities, versions, and chunks."""

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID):
        super().__init__(Document, session, tenant_id)

    async def get_by_id(self, document_id: uuid.UUID | str) -> Document | None:
        doc_uuid = uuid.UUID(str(document_id)) if isinstance(document_id, str) else document_id
        stmt = (
            select(Document)
            .where(
                Document.id == doc_uuid,
                Document.tenant_id == self.tenant_id,
            )
            .options(
                selectinload(Document.versions),
                selectinload(Document.ingestion_jobs),
            )
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_by_hash(self, knowledge_base_id: uuid.UUID, file_hash: str) -> Document | None:
        """Find existing document in KB with identical hash for duplicate detection."""
        stmt = select(Document).where(
            Document.tenant_id == self.tenant_id,
            Document.knowledge_base_id == knowledge_base_id,
            Document.file_hash == file_hash,
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def list_by_knowledge_base(
        self,
        knowledge_base_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[Document]:
        stmt = (
            select(Document)
            .where(
                Document.tenant_id == self.tenant_id,
                Document.knowledge_base_id == knowledge_base_id,
            )
            .order_by(desc(Document.created_at))
            .limit(limit)
            .offset(offset)
        )
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def create_version(
        self,
        document_id: uuid.UUID,
        version_num: int,
        file_path: str,
        file_size: int,
        file_hash: str | None = None,
        extracted_text: str | None = None,
        structured_data: dict[str, Any] | None = None,
        extraction_stats: dict[str, Any] | None = None,
        parser_name: str | None = None,
        parser_version: str | None = None,
        ocr_applied: bool = False,
        ocr_provider: str | None = None,
        ocr_language: str | None = None,
    ) -> DocumentVersion:
        version = DocumentVersion(
            tenant_id=self.tenant_id,
            document_id=document_id,
            version_num=version_num,
            file_path=file_path,
            file_size=file_size,
            file_hash=file_hash,
            extracted_text=extracted_text,
            structured_data=structured_data or {},
            extraction_stats=extraction_stats or {},
            parser_name=parser_name,
            parser_version=parser_version,
            ocr_applied=ocr_applied,
            ocr_provider=ocr_provider,
            ocr_language=ocr_language,
        )
        self.session.add(version)
        await self.session.flush()
        return version

    async def get_latest_version(self, document_id: uuid.UUID) -> DocumentVersion | None:
        stmt = (
            select(DocumentVersion)
            .where(
                DocumentVersion.tenant_id == self.tenant_id,
                DocumentVersion.document_id == document_id,
            )
            .order_by(desc(DocumentVersion.version_num))
            .limit(1)
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def list_versions(self, document_id: uuid.UUID) -> Sequence[DocumentVersion]:
        stmt = (
            select(DocumentVersion)
            .where(
                DocumentVersion.tenant_id == self.tenant_id,
                DocumentVersion.document_id == document_id,
            )
            .order_by(desc(DocumentVersion.version_num))
        )
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def save_chunks(
        self,
        knowledge_base_id: uuid.UUID,
        document_id: uuid.UUID,
        document_version_id: uuid.UUID | None,
        chunks_data: list[dict[str, Any]],
    ) -> list[DocumentChunk]:
        """Atomically persist generated chunks strictly scoped to tenant."""
        # Clear existing chunks for this document version
        del_stmt = delete(DocumentChunk).where(
            DocumentChunk.tenant_id == self.tenant_id,
            DocumentChunk.document_id == document_id,
        )
        await self.session.execute(del_stmt)

        created_chunks: list[DocumentChunk] = []
        for c in chunks_data:
            chunk = DocumentChunk(
                tenant_id=self.tenant_id,
                knowledge_base_id=knowledge_base_id,
                document_id=document_id,
                document_version_id=document_version_id,
                chunk_index=c["chunk_index"],
                content=c["content"],
                character_count=c.get("character_count", len(c["content"])),
                token_count=c.get("token_count", 0),
                page_number=c.get("page_number"),
                heading_path=c.get("heading_path"),
                chunk_hash=c.get("chunk_hash"),
                chunking_strategy=c.get("chunking_strategy", "recursive"),
                metadata_json=c.get("metadata", {}),
            )
            self.session.add(chunk)
            created_chunks.append(chunk)

        # Update document totals
        doc_stmt = select(Document).where(
            Document.id == document_id,
            Document.tenant_id == self.tenant_id,
        )
        doc_res = await self.session.execute(doc_stmt)
        doc = doc_res.scalars().first()
        if doc:
            doc.total_chunks = len(created_chunks)

        await self.session.flush()
        return created_chunks

    async def list_chunks(
        self,
        document_id: uuid.UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[DocumentChunk]:
        stmt = (
            select(DocumentChunk)
            .where(
                DocumentChunk.tenant_id == self.tenant_id,
                DocumentChunk.document_id == document_id,
            )
            .order_by(DocumentChunk.chunk_index.asc())
            .limit(limit)
            .offset(offset)
        )
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def get_ingestion_config(self, knowledge_base_id: uuid.UUID) -> IngestionConfig | None:
        stmt = select(IngestionConfig).where(
            IngestionConfig.tenant_id == self.tenant_id,
            IngestionConfig.knowledge_base_id == knowledge_base_id,
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def upsert_ingestion_config(
        self,
        knowledge_base_id: uuid.UUID,
        chunking_strategy: str = "recursive",
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        ocr_enabled: bool = False,
        ocr_provider: str = "tesseract",
        ocr_language: str = "eng",
        max_file_size_mb: int = 50,
        settings_json: dict[str, Any] | None = None,
    ) -> IngestionConfig:
        config = await self.get_ingestion_config(knowledge_base_id)
        if not config:
            config = IngestionConfig(
                tenant_id=self.tenant_id,
                knowledge_base_id=knowledge_base_id,
                chunking_strategy=chunking_strategy,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                ocr_enabled=ocr_enabled,
                ocr_provider=ocr_provider,
                ocr_language=ocr_language,
                max_file_size_mb=max_file_size_mb,
                settings_json=settings_json or {},
            )
            self.session.add(config)
        else:
            config.chunking_strategy = chunking_strategy
            config.chunk_size = chunk_size
            config.chunk_overlap = chunk_overlap
            config.ocr_enabled = ocr_enabled
            config.ocr_provider = ocr_provider
            config.ocr_language = ocr_language
            config.max_file_size_mb = max_file_size_mb
            if settings_json is not None:
                config.settings_json = settings_json
        await self.session.flush()
        return config


class IngestionJobRepository(TenantScopedRepository[IngestionJob]):
    """Tenant-scoped repository for ingestion jobs and event audit history."""

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID):
        super().__init__(IngestionJob, session, tenant_id)

    async def get_by_id(self, job_id: uuid.UUID | str) -> IngestionJob | None:
        target_id = uuid.UUID(str(job_id)) if isinstance(job_id, str) else job_id
        stmt = (
            select(IngestionJob)
            .where(
                IngestionJob.id == target_id,
                IngestionJob.tenant_id == self.tenant_id,
            )
            .options(selectinload(IngestionJob.events))
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def list_jobs(
        self,
        knowledge_base_id: uuid.UUID | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[IngestionJob]:
        stmt = select(IngestionJob).where(IngestionJob.tenant_id == self.tenant_id)
        if knowledge_base_id:
            stmt = stmt.where(IngestionJob.knowledge_base_id == knowledge_base_id)
        if status:
            stmt = stmt.where(IngestionJob.status == status)
        stmt = stmt.order_by(desc(IngestionJob.created_at)).limit(limit)
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def record_event(
        self,
        job_id: uuid.UUID,
        document_id: uuid.UUID,
        stage: str,
        status: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> IngestionEvent:
        event = IngestionEvent(
            tenant_id=self.tenant_id,
            job_id=job_id,
            document_id=document_id,
            stage=stage,
            status=status,
            message=message,
            details=details or {},
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def get_document_events(self, document_id: uuid.UUID) -> Sequence[IngestionEvent]:
        stmt = (
            select(IngestionEvent)
            .where(
                IngestionEvent.tenant_id == self.tenant_id,
                IngestionEvent.document_id == document_id,
            )
            .order_by(IngestionEvent.created_at.asc())
        )
        res = await self.session.execute(stmt)
        return res.scalars().all()
