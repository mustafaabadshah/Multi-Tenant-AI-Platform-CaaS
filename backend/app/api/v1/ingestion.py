"""Ingestion job tracking, retry, and cancellation endpoints."""

import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, get_current_user, require_permission
from app.core.constants import PermissionName
from app.database.session import get_db
from app.models.user import User
from app.repositories.audit_repository import AuditLogRepository
from app.repositories.document_repository import IngestionJobRepository
from app.schemas.knowledge import IngestionJobResponse
from app.services.ingestion.service import IngestionService, run_ingestion_in_background

router = APIRouter(prefix="/ingestion", tags=["Ingestion Jobs"])


@router.get("/jobs", response_model=list[IngestionJobResponse])
async def list_ingestion_jobs(
    knowledge_base_id: uuid.UUID | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    ctx: TenantContext = Depends(require_permission(PermissionName.INGESTION_READ.value)),
    db: AsyncSession = Depends(get_db),
) -> list[IngestionJobResponse]:
    repo = IngestionJobRepository(db, ctx.tenant.id)
    jobs = await repo.list_jobs(
        knowledge_base_id=knowledge_base_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return [IngestionJobResponse.model_validate(j) for j in jobs]


@router.get("/jobs/{job_id}", response_model=IngestionJobResponse)
async def get_ingestion_job(
    job_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.INGESTION_READ.value)),
    db: AsyncSession = Depends(get_db),
) -> IngestionJobResponse:
    repo = IngestionJobRepository(db, ctx.tenant.id)
    job = await repo.get_by_id(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ingestion job not found in active workspace",
        )
    return IngestionJobResponse.model_validate(job)


@router.post("/jobs/{job_id}/retry", response_model=IngestionJobResponse)
async def retry_ingestion_job(
    job_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.INGESTION_RETRY.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IngestionJobResponse:
    repo = IngestionJobRepository(db, ctx.tenant.id)
    job = await repo.get_by_id(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ingestion job not found in active workspace",
        )

    if job.status not in ("FAILED", "CANCELLED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot retry a job in '{job.status}' status. Only FAILED or CANCELLED jobs may be retried.",
        )

    job.status = "QUEUED"
    job.stage = "QUEUED"
    job.progress_pct = 10
    job.retry_count = 0
    job.error_message = None
    job.error_category = None
    await db.commit()

    # Launch background ingestion
    asyncio.create_task(run_ingestion_in_background(ctx.tenant.id, job.id))

    audit_repo = AuditLogRepository(db, ctx.tenant.id)
    await audit_repo.log_event(
        action="ingestion.retry",
        resource_type="ingestion_job",
        resource_id=job.id,
        actor_id=current_user.id,
    )

    return IngestionJobResponse.model_validate(job)


@router.post("/jobs/{job_id}/cancel", response_model=IngestionJobResponse)
async def cancel_ingestion_job(
    job_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.INGESTION_CANCEL.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IngestionJobResponse:
    repo = IngestionJobRepository(db, ctx.tenant.id)
    job = await repo.get_by_id(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ingestion job not found in active workspace",
        )

    if job.status in ("COMPLETED", "FAILED", "CANCELLED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel job in '{job.status}' status.",
        )

    job.status = "CANCELLED"
    job.stage = "CANCELLED"
    await repo.record_event(
        job_id=job.id,
        document_id=job.document_id,
        stage="CANCEL",
        status="CANCELLED",
        message=f"Job cancelled by user {current_user.email}",
    )
    await db.commit()

    audit_repo = AuditLogRepository(db, ctx.tenant.id)
    await audit_repo.log_event(
        action="ingestion.cancel",
        resource_type="ingestion_job",
        resource_id=job.id,
        actor_id=current_user.id,
    )

    return IngestionJobResponse.model_validate(job)
