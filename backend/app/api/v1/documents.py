"""Document management, versioning, content, chunk inspection, and reprocessing endpoints."""

import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, get_current_user, require_permission
from app.core.config import settings
from app.core.constants import PermissionName
from app.database.session import get_db
from app.models.knowledge import Document
from app.models.user import User
from app.repositories.audit_repository import AuditLogRepository
from app.repositories.document_repository import DocumentRepository, IngestionJobRepository
from app.repositories.knowledge_repository import KnowledgeRepository
from app.schemas.knowledge import (
    DocumentChunkResponse,
    DocumentContentResponse,
    DocumentResponse,
    DocumentUploadResponse,
    DocumentVersionResponse,
    IngestionEventResponse,
    IngestionJobResponse,
)
from app.schemas.provider import URLIngestRequest
from app.services.ingestion.service import IngestionService, run_ingestion_in_background
from app.services.ingestion.url_ingestion import SSRFValidationError, fetch_url_content_safe
from app.storage import get_storage_provider, sanitize_filename

logger = logging.getLogger("mmaip.documents")

router = APIRouter(prefix="/documents", tags=["Documents & Extraction"])


def _check_document_acl(doc: Document, ctx: TenantContext) -> None:
    if ctx.is_admin:
        return
    user_dept_id = ctx.membership.department_id if ctx.membership else None
    if doc.department_id and doc.department_id != user_dept_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found in active workspace",
        )
    if doc.access_level == "restricted" and not ctx.is_admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found in active workspace",
        )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.DOCUMENT_READ.value)),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    repo = DocumentRepository(db, ctx.tenant.id)
    doc = await repo.get_by_id(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found in active workspace",
        )
    _check_document_acl(doc, ctx)
    return DocumentResponse.model_validate(doc)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.DOCUMENT_DELETE.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    repo = DocumentRepository(db, ctx.tenant.id)
    doc = await repo.get_by_id(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found in active workspace",
        )
    _check_document_acl(doc, ctx)

    # Delete the object first. A storage failure must not be reported as a
    # successful deletion: keep the DB record so the document remains visible
    # and retryable. ``delete`` returning False means the object was already
    # absent, which is the desired end state.
    storage = get_storage_provider()
    try:
        await storage.delete(str(ctx.tenant.id), doc.file_path)
    except Exception as exc:
        logger.error(
            "Document storage deletion failed for tenant %s document %s (%s)",
            ctx.tenant.id,
            document_id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Document storage deletion failed; the document was not deleted.",
        )

    # Object is gone (or already absent); now remove DB records atomically.
    try:
        deleted = await repo.delete(document_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found in active workspace",
            )
        await db.commit()
    except HTTPException:
        await db.rollback()
        raise
    except Exception as exc:
        await db.rollback()
        logger.error(
            "Document database deletion failed after object removal for tenant %s document %s (%s)",
            ctx.tenant.id,
            document_id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document deletion could not be completed.",
        )

    audit_repo = AuditLogRepository(db, ctx.tenant.id)
    await audit_repo.log_event(
        action="document.delete",
        resource_type="document",
        resource_id=document_id,
        actor_id=current_user.id,
        details={"filename": doc.filename},
    )


@router.get("/{document_id}/versions", response_model=list[DocumentVersionResponse])
async def list_document_versions(
    document_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.DOCUMENT_READ.value)),
    db: AsyncSession = Depends(get_db),
) -> list[DocumentVersionResponse]:
    repo = DocumentRepository(db, ctx.tenant.id)
    doc = await repo.get_by_id(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found in active workspace",
        )
    _check_document_acl(doc, ctx)
    versions = await repo.list_versions(document_id)
    return [DocumentVersionResponse.model_validate(v) for v in versions]


@router.post("/{document_id}/reprocess", response_model=IngestionJobResponse)
async def reprocess_document(
    document_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.DOCUMENT_REPROCESS.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IngestionJobResponse:
    repo = DocumentRepository(db, ctx.tenant.id)
    doc = await repo.get_by_id(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found in active workspace",
        )
    _check_document_acl(doc, ctx)

    job_repo = IngestionJobRepository(db, ctx.tenant.id)
    job = await job_repo.create(
        knowledge_base_id=doc.knowledge_base_id,
        document_id=doc.id,
        status="QUEUED",
        stage="QUEUED",
        progress_pct=10,
        job_metadata={"reprocessed_by": str(current_user.id)},
    )
    doc.status = "QUEUED"
    await db.commit()

    # Launch background ingestion
    asyncio.create_task(run_ingestion_in_background(ctx.tenant.id, job.id))

    audit_repo = AuditLogRepository(db, ctx.tenant.id)
    await audit_repo.log_event(
        action="document.reprocess",
        resource_type="document",
        resource_id=document_id,
        actor_id=current_user.id,
        details={"job_id": str(job.id)},
    )

    return IngestionJobResponse.model_validate(job)


@router.get("/{document_id}/content", response_model=DocumentContentResponse)
async def get_document_content(
    document_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.DOCUMENT_READ_CONTENT.value)),
    db: AsyncSession = Depends(get_db),
) -> DocumentContentResponse:
    repo = DocumentRepository(db, ctx.tenant.id)
    doc = await repo.get_by_id(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found in active workspace",
        )
    _check_document_acl(doc, ctx)

    latest_version = await repo.get_latest_version(document_id)
    return DocumentContentResponse(
        document_id=doc.id,
        version_num=latest_version.version_num if latest_version else 1,
        filename=doc.filename,
        mime_type=doc.mime_type,
        total_pages=doc.total_pages,
        extracted_text=latest_version.extracted_text if latest_version else None,
        structured_data=latest_version.structured_data if latest_version else {},
        extraction_stats=latest_version.extraction_stats if latest_version else {},
    )


@router.get("/{document_id}/chunks", response_model=list[DocumentChunkResponse])
async def list_document_chunks(
    document_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    ctx: TenantContext = Depends(require_permission(PermissionName.DOCUMENT_READ_CHUNKS.value)),
    db: AsyncSession = Depends(get_db),
) -> list[DocumentChunkResponse]:
    repo = DocumentRepository(db, ctx.tenant.id)
    doc = await repo.get_by_id(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found in active workspace",
        )
    _check_document_acl(doc, ctx)

    chunks = await repo.list_chunks(document_id, limit=limit, offset=offset)
    return [DocumentChunkResponse.model_validate(c) for c in chunks]


@router.get("/{document_id}/processing-history", response_model=list[IngestionEventResponse])
async def get_document_processing_history(
    document_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.DOCUMENT_READ.value)),
    db: AsyncSession = Depends(get_db),
) -> list[IngestionEventResponse]:
    repo = DocumentRepository(db, ctx.tenant.id)
    doc = await repo.get_by_id(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found in active workspace",
        )
    _check_document_acl(doc, ctx)

    job_repo = IngestionJobRepository(db, ctx.tenant.id)
    events = await job_repo.get_document_events(document_id)
    return [IngestionEventResponse.model_validate(e) for e in events]


@router.post("/ingest-url", response_model=DocumentUploadResponse)
async def ingest_url(
    payload: URLIngestRequest,
    ctx: TenantContext = Depends(require_permission(PermissionName.DOCUMENT_UPLOAD.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentUploadResponse:
    kb_repo = KnowledgeRepository(db, ctx.tenant.id)
    kb = await kb_repo.get_by_id(payload.knowledge_base_id)
    if not kb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found in active workspace",
        )

    try:
        title, content_bytes, mime_type = await fetch_url_content_safe(payload.url)
    except SSRFValidationError as ssrf_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Security error: {str(ssrf_err)}",
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch content from URL: {str(err)}",
        )

    if len(content_bytes) > settings.MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=(
                f"Fetched content size ({len(content_bytes)} bytes) exceeds the "
                f"maximum permitted limit ({settings.MAX_FILE_SIZE_BYTES} bytes)."
            ),
        )

    ext = ".html" if "html" in mime_type else ".txt"
    cleaned_title = sanitize_filename(title[:40].strip()) or f"web_page_{uuid.uuid4().hex[:6]}"
    filename = f"{cleaned_title}{ext}"

    service = IngestionService(db, ctx.tenant.id)
    try:
        doc, job, is_dup = await service.upload_document(
            knowledge_base_id=kb.id,
            filename=filename,
            content=content_bytes,
            mime_type=mime_type,
        )
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        )

    # Spawn background ingestion task
    asyncio.create_task(run_ingestion_in_background(ctx.tenant.id, job.id))

    audit_repo = AuditLogRepository(db, ctx.tenant.id)
    await audit_repo.log_event(
        action="document.ingest_url",
        resource_type="document",
        resource_id=doc.id,
        actor_id=current_user.id,
        details={"url": payload.url, "filename": filename, "is_duplicate": is_dup, "job_id": str(job.id)},
    )

    return DocumentUploadResponse(
        document=DocumentResponse.model_validate(doc),
        job=IngestionJobResponse.model_validate(job),
        is_duplicate=is_dup,
    )
