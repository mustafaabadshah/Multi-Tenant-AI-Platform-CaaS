"""Document management, versioning, content, chunk inspection, and reprocessing endpoints."""

import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, get_current_user, require_permission
from app.core.constants import PermissionName
from app.database.session import get_db
from app.models.user import User
from app.repositories.audit_repository import AuditLogRepository
from app.repositories.document_repository import DocumentRepository, IngestionJobRepository
from app.schemas.knowledge import (
    DocumentChunkResponse,
    DocumentContentResponse,
    DocumentResponse,
    DocumentVersionResponse,
    IngestionEventResponse,
    IngestionJobResponse,
)
from app.services.ingestion.service import run_ingestion_in_background
from app.storage import get_storage_provider

router = APIRouter(prefix="/documents", tags=["Documents & Extraction"])


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

    # Delete raw file from storage
    storage = get_storage_provider()
    try:
        await storage.delete(str(ctx.tenant.id), doc.file_path)
    except Exception:
        pass

    # Delete document record (cascades to versions, chunks, jobs, and events)
    await repo.delete(document_id)

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

    job_repo = IngestionJobRepository(db, ctx.tenant.id)
    events = await job_repo.get_document_events(document_id)
    return [IngestionEventResponse.model_validate(e) for e in events]
