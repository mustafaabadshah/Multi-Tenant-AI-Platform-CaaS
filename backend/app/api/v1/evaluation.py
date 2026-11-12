"""API endpoints for AI Assistant Evaluation, Datasets, and Benchmarking."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, get_db, require_permission
from app.core.constants import PermissionName
from app.schemas.evaluation import (
    EvalDatasetCreate,
    EvalDatasetDetailResponse,
    EvalDatasetItemResponse,
    EvalDatasetResponse,
    EvalRunComparisonResponse,
    EvalRunCreate,
    EvalRunDetailResponse,
    EvalRunResponse,
    EvalRunResultResponse,
)
from app.services.evaluation_service import EvaluationService

router = APIRouter(prefix="/evaluations", tags=["AI Evaluation"])


@router.get("/datasets", response_model=list[EvalDatasetResponse])
async def list_evaluation_datasets(
    db: AsyncSession = Depends(get_db),
    tenant_ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_READ)),
):
    """List all evaluation benchmark datasets accessible to the current tenant."""
    eval_svc = EvaluationService(
        session=db,
        tenant_id=tenant_ctx.tenant.id,
        user_id=tenant_ctx.user_id,
        is_admin=tenant_ctx.is_owner,
    )
    datasets = await eval_svc.list_datasets()
    return [
        EvalDatasetResponse(
            id=d.id,
            tenant_id=d.tenant_id,
            name=d.name,
            description=d.description,
            version=d.version,
            is_system=d.is_system,
            item_count=len(d.items) if "items" in d.__dict__ and d.items else 0,
            created_by=d.created_by,
            created_at=d.created_at,
            updated_at=d.updated_at,
        )
        for d in datasets
    ]


@router.post("/datasets", response_model=EvalDatasetDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_evaluation_dataset(
    payload: EvalDatasetCreate,
    db: AsyncSession = Depends(get_db),
    tenant_ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_UPDATE)),
):
    """Create a new evaluation dataset."""
    eval_svc = EvaluationService(
        session=db,
        tenant_id=tenant_ctx.tenant.id,
        user_id=tenant_ctx.user_id,
        is_admin=tenant_ctx.is_owner,
    )
    dataset = await eval_svc.create_dataset(
        name=payload.name,
        description=payload.description,
        items=[item.model_dump() for item in payload.items],
    )
    items_list = dataset.items if "items" in dataset.__dict__ and dataset.items else []
    return EvalDatasetDetailResponse(
        id=dataset.id,
        tenant_id=dataset.tenant_id,
        name=dataset.name,
        description=dataset.description,
        version=dataset.version,
        is_system=dataset.is_system,
        item_count=len(items_list),
        created_by=dataset.created_by,
        created_at=dataset.created_at,
        updated_at=dataset.updated_at,
        items=[EvalDatasetItemResponse.model_validate(itm) for itm in items_list],
    )


@router.post("/datasets/seed-starter", response_model=list[EvalDatasetResponse])
async def seed_starter_benchmarks(
    db: AsyncSession = Depends(get_db),
    tenant_ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_UPDATE)),
):
    """Seed default deterministic starter benchmarks into the current tenant."""
    eval_svc = EvaluationService(
        session=db,
        tenant_id=tenant_ctx.tenant.id,
        user_id=tenant_ctx.user_id,
        is_admin=tenant_ctx.is_owner,
    )
    seeded = await eval_svc.seed_system_benchmarks()
    return [
        EvalDatasetResponse(
            id=d.id,
            tenant_id=d.tenant_id,
            name=d.name,
            description=d.description,
            version=d.version,
            is_system=d.is_system,
            item_count=len(d.items) if "items" in d.__dict__ and d.items else 0,
            created_by=d.created_by,
            created_at=d.created_at,
            updated_at=d.updated_at,
        )
        for d in seeded
    ]


@router.get("/datasets/{dataset_id}", response_model=EvalDatasetDetailResponse)
async def get_evaluation_dataset(
    dataset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant_ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_READ)),
):
    """Fetch details and individual items of an evaluation dataset."""
    eval_svc = EvaluationService(
        session=db,
        tenant_id=tenant_ctx.tenant.id,
        user_id=tenant_ctx.user_id,
        is_admin=tenant_ctx.is_owner,
    )
    dataset = await eval_svc.get_dataset(dataset_id)
    if not dataset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

    items_list = dataset.items if "items" in dataset.__dict__ and dataset.items else []
    return EvalDatasetDetailResponse(
        id=dataset.id,
        tenant_id=dataset.tenant_id,
        name=dataset.name,
        description=dataset.description,
        version=dataset.version,
        is_system=dataset.is_system,
        item_count=len(items_list),
        created_by=dataset.created_by,
        created_at=dataset.created_at,
        updated_at=dataset.updated_at,
        items=[EvalDatasetItemResponse.model_validate(itm) for itm in items_list],
    )


@router.post("/runs", response_model=EvalRunResponse, status_code=status.HTTP_201_CREATED)
async def trigger_evaluation_run(
    payload: EvalRunCreate,
    db: AsyncSession = Depends(get_db),
    tenant_ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_EXECUTE)),
):
    """Execute an evaluation benchmark run against an assistant."""
    eval_svc = EvaluationService(
        session=db,
        tenant_id=tenant_ctx.tenant.id,
        user_id=tenant_ctx.user_id,
        is_admin=tenant_ctx.is_owner,
    )
    try:
        run = await eval_svc.execute_eval_run(
            assistant_id=payload.assistant_id,
            dataset_id=payload.dataset_id,
            eval_type=payload.eval_type,
            judge_provider=payload.judge_provider,
            judge_model=payload.judge_model,
        )
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))

    return EvalRunResponse(
        id=run.id,
        tenant_id=run.tenant_id,
        assistant_id=run.assistant_id,
        dataset_id=run.dataset_id,
        status=run.status,
        eval_type=run.eval_type,
        judge_provider=run.judge_provider,
        judge_model=run.judge_model,
        metrics_summary=run.metrics_summary,
        created_by=run.created_by,
        created_at=run.created_at,
        completed_at=run.completed_at,
        result_count=len(run.results) if "results" in run.__dict__ and run.results else 0,
    )


@router.get("/runs", response_model=list[EvalRunResponse])
async def list_evaluation_runs(
    assistant_id: Optional[uuid.UUID] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    tenant_ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_READ)),
):
    """List evaluation runs for this tenant, optionally filtered by assistant."""
    eval_svc = EvaluationService(
        session=db,
        tenant_id=tenant_ctx.tenant.id,
        user_id=tenant_ctx.user_id,
        is_admin=tenant_ctx.is_owner,
    )
    runs = await eval_svc.list_runs(assistant_id=assistant_id)
    return [
        EvalRunResponse(
            id=r.id,
            tenant_id=r.tenant_id,
            assistant_id=r.assistant_id,
            dataset_id=r.dataset_id,
            status=r.status,
            eval_type=r.eval_type,
            judge_provider=r.judge_provider,
            judge_model=r.judge_model,
            metrics_summary=r.metrics_summary,
            created_by=r.created_by,
            created_at=r.created_at,
            completed_at=r.completed_at,
            result_count=0,
        )
        for r in runs
    ]


@router.get("/runs/{run_id}", response_model=EvalRunDetailResponse)
async def get_evaluation_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant_ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_READ)),
):
    """Fetch details and individual item results of an evaluation run."""
    eval_svc = EvaluationService(
        session=db,
        tenant_id=tenant_ctx.tenant.id,
        user_id=tenant_ctx.user_id,
        is_admin=tenant_ctx.is_owner,
    )
    run = await eval_svc.get_run(run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation run not found")

    serialized_results = []
    for res in run.results or []:
        serialized_results.append(
            EvalRunResultResponse(
                id=res.id,
                run_id=res.run_id,
                item_id=res.item_id,
                question=res.item.question if res.item else None,
                expected_answer=res.item.expected_answer if res.item else None,
                generated_answer=res.generated_answer,
                retrieved_chunks=res.retrieved_chunks or [],
                citations=res.citations or [],
                recall_score=res.recall_score,
                mrr_score=res.mrr_score,
                faithfulness_score=res.faithfulness_score,
                citation_score=res.citation_score,
                latency_ms=res.latency_ms,
                error_message=res.error_message,
                created_at=res.created_at,
            )
        )

    return EvalRunDetailResponse(
        id=run.id,
        tenant_id=run.tenant_id,
        assistant_id=run.assistant_id,
        dataset_id=run.dataset_id,
        status=run.status,
        eval_type=run.eval_type,
        judge_provider=run.judge_provider,
        judge_model=run.judge_model,
        metrics_summary=run.metrics_summary,
        created_by=run.created_by,
        created_at=run.created_at,
        completed_at=run.completed_at,
        result_count=len(serialized_results),
        results=serialized_results,
    )


@router.get("/runs/{run_id}/compare/{other_run_id}", response_model=EvalRunComparisonResponse)
async def compare_evaluation_runs(
    run_id: uuid.UUID,
    other_run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant_ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_READ)),
):
    """Compare two evaluation runs to evaluate regressions or improvements."""
    eval_svc = EvaluationService(
        session=db,
        tenant_id=tenant_ctx.tenant.id,
        user_id=tenant_ctx.user_id,
        is_admin=tenant_ctx.is_owner,
    )
    try:
        comparison = await eval_svc.compare_runs(run_id, other_run_id)
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(val_err))

    return EvalRunComparisonResponse(**comparison)
