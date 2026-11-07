import asyncio
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, get_current_user, require_permission
from app.core.config import settings
from app.core.constants import PermissionName
from app.database.session import get_db
from app.models.user import User
from app.repositories.audit_repository import AuditLogRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.knowledge_repository import KnowledgeRepository
from app.schemas.knowledge import (
    DocumentResponse,
    DocumentUploadResponse,
    IngestionConfigResponse,
    IngestionConfigUpdateRequest,
    IngestionJobResponse,
    KnowledgeBaseCreateRequest,
    KnowledgeBaseResponse,
)
from app.schemas.retrieval import (
    EmbeddingJobRead,
    IndexStatusResponse,
    RetrievalConfigRead,
    RetrievalConfigUpdate,
)
from app.services.ingestion.service import IngestionService, run_ingestion_in_background

router = APIRouter(prefix="/knowledge", tags=["Knowledge Base Foundation"])


@router.get("", response_model=list[KnowledgeBaseResponse])
async def list_knowledge_bases(
    ctx: TenantContext = Depends(require_permission(PermissionName.KNOWLEDGE_READ.value)),
    db: AsyncSession = Depends(get_db),
) -> list[KnowledgeBaseResponse]:
    repo = KnowledgeRepository(db, ctx.tenant.id)
    items = await repo.list_with_counts()

    return [
        KnowledgeBaseResponse(
            id=kb.id,
            tenant_id=kb.tenant_id,
            name=kb.name,
            description=kb.description,
            status=kb.status,
            document_count=doc_count,
            created_at=kb.created_at,
            updated_at=kb.updated_at,
        )
        for kb, doc_count in items
    ]


@router.post("", response_model=KnowledgeBaseResponse, status_code=status.HTTP_201_CREATED)
async def create_knowledge_base(
    payload: KnowledgeBaseCreateRequest,
    ctx: TenantContext = Depends(require_permission(PermissionName.KNOWLEDGE_CREATE.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeBaseResponse:
    repo = KnowledgeRepository(db, ctx.tenant.id)
    kb = await repo.create(
        name=payload.name.strip(),
        description=payload.description,
        status="ACTIVE",
    )

    audit_repo = AuditLogRepository(db, ctx.tenant.id)
    await audit_repo.log_event(
        action="knowledge.create",
        resource_type="knowledge_base",
        resource_id=kb.id,
        actor_id=current_user.id,
        details={"name": kb.name},
    )

    return KnowledgeBaseResponse(
        id=kb.id,
        tenant_id=kb.tenant_id,
        name=kb.name,
        description=kb.description,
        status=kb.status,
        document_count=0,
        created_at=kb.created_at,
        updated_at=kb.updated_at,
    )


@router.get("/{kb_id}", response_model=KnowledgeBaseResponse)
async def get_knowledge_base(
    kb_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.KNOWLEDGE_READ.value)),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeBaseResponse:
    repo = KnowledgeRepository(db, ctx.tenant.id)
    kb = await repo.get_by_id(kb_id)
    if not kb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found in active workspace",
        )

    return KnowledgeBaseResponse(
        id=kb.id,
        tenant_id=kb.tenant_id,
        name=kb.name,
        description=kb.description,
        status=kb.status,
        document_count=0,
        created_at=kb.created_at,
        updated_at=kb.updated_at,
    )


@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_base(
    kb_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.KNOWLEDGE_DELETE.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    repo = KnowledgeRepository(db, ctx.tenant.id)
    deleted = await repo.delete(kb_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found in active workspace",
        )

    audit_repo = AuditLogRepository(db, ctx.tenant.id)
    await audit_repo.log_event(
        action="knowledge.delete",
        resource_type="knowledge_base",
        resource_id=kb_id,
        actor_id=current_user.id,
    )


# --- Milestone 02 Document & Ingestion Endpoints ---


@router.post(
    "/{kb_id}/documents",
    response_model=list[DocumentUploadResponse],
    status_code=status.HTTP_201_CREATED,
)
async def upload_documents(
    kb_id: uuid.UUID,
    files: list[UploadFile] = File(...),
    ctx: TenantContext = Depends(require_permission(PermissionName.DOCUMENT_UPLOAD.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DocumentUploadResponse]:
    # 1. Verify KB belongs to active tenant
    kb_repo = KnowledgeRepository(db, ctx.tenant.id)
    kb = await kb_repo.get_by_id(kb_id)
    if not kb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found in active workspace",
        )

    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided in upload request",
        )

    if len(files) > settings.MAX_FILES_PER_REQUEST:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Exceeded maximum files per request limit ({settings.MAX_FILES_PER_REQUEST})",
        )

    service = IngestionService(db, ctx.tenant.id)
    upload_results: list[DocumentUploadResponse] = []
    audit_repo = AuditLogRepository(db, ctx.tenant.id)

    for upload_file in files:
        filename = upload_file.filename or f"uploaded_{uuid.uuid4().hex[:8]}"
        content = await upload_file.read()

        try:
            doc, job, is_dup = await service.upload_document(
                knowledge_base_id=kb.id,
                filename=filename,
                content=content,
                mime_type=upload_file.content_type,
            )

            # Spawn background execution for new or reprocessed job
            asyncio.create_task(run_ingestion_in_background(ctx.tenant.id, job.id))

            await audit_repo.log_event(
                action="document.upload",
                resource_type="document",
                resource_id=doc.id,
                actor_id=current_user.id,
                details={"filename": filename, "is_duplicate": is_dup, "job_id": str(job.id)},
            )

            upload_results.append(
                DocumentUploadResponse(
                    document=DocumentResponse.model_validate(doc),
                    job=IngestionJobResponse.model_validate(job),
                    is_duplicate=is_dup,
                )
            )
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(err),
            )

    return upload_results


@router.get("/{kb_id}/documents", response_model=list[DocumentResponse])
async def list_kb_documents(
    kb_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
    ctx: TenantContext = Depends(require_permission(PermissionName.DOCUMENT_READ.value)),
    db: AsyncSession = Depends(get_db),
) -> list[DocumentResponse]:
    kb_repo = KnowledgeRepository(db, ctx.tenant.id)
    kb = await kb_repo.get_by_id(kb_id)
    if not kb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found in active workspace",
        )

    doc_repo = DocumentRepository(db, ctx.tenant.id)
    documents = await doc_repo.list_by_knowledge_base(kb_id, limit=limit, offset=offset)
    return [DocumentResponse.model_validate(d) for d in documents]


@router.get("/{kb_id}/ingestion-config", response_model=IngestionConfigResponse)
async def get_ingestion_config(
    kb_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.DOCUMENT_READ.value)),
    db: AsyncSession = Depends(get_db),
) -> IngestionConfigResponse:
    kb_repo = KnowledgeRepository(db, ctx.tenant.id)
    kb = await kb_repo.get_by_id(kb_id)
    if not kb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found in active workspace",
        )

    doc_repo = DocumentRepository(db, ctx.tenant.id)
    config = await doc_repo.get_ingestion_config(kb_id)
    if not config:
        # Return default configuration if not customized
        return IngestionConfigResponse(
            knowledge_base_id=kb_id,
            chunking_strategy="recursive",
            chunk_size=1000,
            chunk_overlap=200,
            ocr_enabled=settings.OCR_ENABLED_DEFAULT,
            ocr_provider=settings.OCR_DEFAULT_PROVIDER,
            ocr_language=settings.OCR_DEFAULT_LANGUAGE,
            max_file_size_mb=50,
            settings_json={},
        )
    return IngestionConfigResponse.model_validate(config)


@router.patch("/{kb_id}/ingestion-config", response_model=IngestionConfigResponse)
async def update_ingestion_config(
    kb_id: uuid.UUID,
    payload: IngestionConfigUpdateRequest,
    ctx: TenantContext = Depends(require_permission(PermissionName.INGESTION_CONFIGURE.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IngestionConfigResponse:
    kb_repo = KnowledgeRepository(db, ctx.tenant.id)
    kb = await kb_repo.get_by_id(kb_id)
    if not kb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found in active workspace",
        )

    doc_repo = DocumentRepository(db, ctx.tenant.id)
    existing = await doc_repo.get_ingestion_config(kb_id)

    updated = await doc_repo.upsert_ingestion_config(
        knowledge_base_id=kb_id,
        chunking_strategy=payload.chunking_strategy or (existing.chunking_strategy if existing else "recursive"),
        chunk_size=payload.chunk_size if payload.chunk_size is not None else (existing.chunk_size if existing else 1000),
        chunk_overlap=payload.chunk_overlap if payload.chunk_overlap is not None else (existing.chunk_overlap if existing else 200),
        ocr_enabled=payload.ocr_enabled if payload.ocr_enabled is not None else (existing.ocr_enabled if existing else settings.OCR_ENABLED_DEFAULT),
        ocr_provider=payload.ocr_provider or (existing.ocr_provider if existing else settings.OCR_DEFAULT_PROVIDER),
        ocr_language=payload.ocr_language or (existing.ocr_language if existing else settings.OCR_DEFAULT_LANGUAGE),
        max_file_size_mb=payload.max_file_size_mb if payload.max_file_size_mb is not None else (existing.max_file_size_mb if existing else 50),
    )
    await db.commit()

    audit_repo = AuditLogRepository(db, ctx.tenant.id)
    await audit_repo.log_event(
        action="ingestion.configure",
        resource_type="knowledge_base",
        resource_id=kb_id,
        actor_id=current_user.id,
        details=payload.model_dump(exclude_unset=True),
    )

    return IngestionConfigResponse.model_validate(updated)


@router.get("/{kb_id}/retrieval-config", response_model=RetrievalConfigRead)
async def get_retrieval_config(
    kb_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.RETRIEVAL_SEARCH.value)),
    db: AsyncSession = Depends(get_db),
) -> RetrievalConfigRead:
    """Fetch retrieval & vector database configuration for a knowledge base."""
    kb_repo = KnowledgeRepository(db, ctx.tenant.id)
    kb = await kb_repo.get_by_id(kb_id)
    if not kb:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found")

    from app.core.crypto import decrypt_secret, mask_secret
    from app.repositories.retrieval_repository import RetrievalRepository
    from app.schemas.retrieval import RetrievalConfigRead

    ret_repo = RetrievalRepository(db, ctx.tenant.id)
    cfg = await ret_repo.get_or_create_config(kb_id)
    plain = decrypt_secret(cfg.encrypted_api_key) if cfg.encrypted_api_key else None

    return RetrievalConfigRead(
        id=cfg.id,
        knowledge_base_id=cfg.knowledge_base_id,
        retrieval_mode=cfg.retrieval_mode,
        vector_store=cfg.vector_store,
        embedding_provider=cfg.embedding_provider,
        embedding_model=cfg.embedding_model,
        embedding_dimensions=cfg.embedding_dimensions,
        similarity_metric=cfg.similarity_metric,
        top_k=cfg.top_k,
        rrf_k=cfg.rrf_k,
        rerank_enabled=cfg.rerank_enabled,
        rerank_provider=cfg.rerank_provider,
        embedding_version=cfg.embedding_version,
        has_api_key=bool(cfg.encrypted_api_key),
        masked_api_key=mask_secret(plain) if plain else None,
        settings_json=cfg.settings_json or {},
    )


@router.patch("/{kb_id}/retrieval-config", response_model=RetrievalConfigRead)
async def update_retrieval_config(
    kb_id: uuid.UUID,
    payload: RetrievalConfigUpdate,
    ctx: TenantContext = Depends(require_permission(PermissionName.RETRIEVAL_CONFIGURE.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RetrievalConfigRead:
    """Update retrieval and vector configuration for a knowledge base."""
    kb_repo = KnowledgeRepository(db, ctx.tenant.id)
    kb = await kb_repo.get_by_id(kb_id)
    if not kb:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found")

    from app.core.crypto import decrypt_secret, mask_secret
    from app.repositories.retrieval_repository import RetrievalRepository

    ret_repo = RetrievalRepository(db, ctx.tenant.id)
    update_data = payload.model_dump(exclude_unset=True)

    updated = await ret_repo.update_config(kb_id, **update_data)
    await db.commit()

    audit_repo = AuditLogRepository(db, ctx.tenant.id)
    await audit_repo.log_event(
        action="retrieval.configure",
        resource_type="knowledge_base",
        resource_id=kb_id,
        actor_id=current_user.id,
        details={k: v for k, v in update_data.items() if k != "api_key"},
    )

    plain = decrypt_secret(updated.encrypted_api_key) if updated.encrypted_api_key else None
    return RetrievalConfigRead(
        id=updated.id,
        knowledge_base_id=updated.knowledge_base_id,
        retrieval_mode=updated.retrieval_mode,
        vector_store=updated.vector_store,
        embedding_provider=updated.embedding_provider,
        embedding_model=updated.embedding_model,
        embedding_dimensions=updated.embedding_dimensions,
        similarity_metric=updated.similarity_metric,
        top_k=updated.top_k,
        rrf_k=updated.rrf_k,
        rerank_enabled=updated.rerank_enabled,
        rerank_provider=updated.rerank_provider,
        embedding_version=updated.embedding_version,
        has_api_key=bool(updated.encrypted_api_key),
        masked_api_key=mask_secret(plain) if plain else None,
        settings_json=updated.settings_json or {},
    )


@router.get("/{kb_id}/index-status", response_model=IndexStatusResponse)
async def get_kb_index_status(
    kb_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.INDEX_READ.value)),
    db: AsyncSession = Depends(get_db),
) -> IndexStatusResponse:
    """Return indexing statistics, chunk counts, and vector store health for a knowledge base."""
    kb_repo = KnowledgeRepository(db, ctx.tenant.id)
    kb = await kb_repo.get_by_id(kb_id)
    if not kb:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found")

    from app.repositories.retrieval_repository import RetrievalRepository

    ret_repo = RetrievalRepository(db, ctx.tenant.id)
    status_data = await ret_repo.get_index_status(kb_id)
    return IndexStatusResponse(**status_data)


@router.post("/{kb_id}/reindex")
async def trigger_kb_reindex(
    kb_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.INDEX_REINDEX.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger re-embedding and vector store reindexing for all chunks in this knowledge base."""
    kb_repo = KnowledgeRepository(db, ctx.tenant.id)
    kb = await kb_repo.get_by_id(kb_id)
    if not kb:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found")

    service = IngestionService(db, ctx.tenant.id)
    job = await service.reindex_knowledge_base(kb_id)

    audit_repo = AuditLogRepository(db, ctx.tenant.id)
    await audit_repo.log_event(
        action="index.reindex",
        resource_type="knowledge_base",
        resource_id=kb_id,
        actor_id=current_user.id,
        details={"job_id": str(job.id), "total_chunks": job.total_chunks},
    )

    return {
        "message": "Reindexing completed successfully.",
        "job_id": str(job.id),
        "status": job.status,
        "processed_chunks": job.processed_chunks,
        "total_chunks": job.total_chunks,
    }


@router.get("/{kb_id}/embedding-jobs", response_model=list[EmbeddingJobRead])
async def list_kb_embedding_jobs(
    kb_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.INDEX_READ.value)),
    db: AsyncSession = Depends(get_db),
) -> list[EmbeddingJobRead]:
    """List recent embedding and reindexing jobs for a knowledge base."""
    from app.repositories.retrieval_repository import RetrievalRepository

    ret_repo = RetrievalRepository(db, ctx.tenant.id)
    jobs = await ret_repo.list_embedding_jobs(kb_id)
    return [
        EmbeddingJobRead(
            id=j.id,
            knowledge_base_id=j.knowledge_base_id,
            document_id=j.document_id,
            embedding_version=j.embedding_version,
            status=j.status,
            stage=j.stage,
            total_chunks=j.total_chunks,
            processed_chunks=j.processed_chunks,
            failed_chunks=j.failed_chunks,
            error_message=j.error_message,
            created_at=j.created_at.isoformat(),
            completed_at=j.completed_at.isoformat() if j.completed_at else None,
        )
        for j in jobs
    ]


