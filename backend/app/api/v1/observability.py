"""API endpoints for Platform Observability, Request Traces, and Operational Metrics."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, require_permission
from app.core.constants import PermissionName
from app.database.session import get_db
from app.models.trace import RequestTrace
from app.observability.policy import ObservabilityPolicyService
from app.schemas.observability import (
    ObservabilityMetricsSchema,
    ObservabilityPolicySchema,
    ObservabilityPolicyUpdate,
    PurgeResultSchema,
    TraceDetailSchema,
)

router = APIRouter(prefix="/observability", tags=["Platform Observability"])


def _serialize_db_trace(record: RequestTrace, mask_previews: bool = False) -> dict[str, Any]:
    """Helper to convert a RequestTrace ORM row into an API-compatible dict."""
    return {
        "trace_id": record.trace_id,
        "tenant_id": str(record.tenant_id),
        "assistant_id": str(record.assistant_id) if record.assistant_id else None,
        "assistant_name": record.assistant_name,
        "conversation_id": str(record.conversation_id) if record.conversation_id else None,
        "traffic_type": record.traffic_type,
        "status": record.status,
        "error_category": record.error_category,
        "error": record.error_message,
        "created_at": record.created_at.isoformat() if record.created_at else "",
        "completed_at": record.completed_at.isoformat() if record.completed_at else None,
        "total_duration_ms": record.total_duration_ms,
        "ttft_ms": record.ttft_ms,
        "provider": record.provider,
        "model": record.model,
        "credential_source": record.credential_source,
        "retrieval_mode": record.retrieval_mode,
        "retrieved_chunk_count": record.retrieved_chunk_count,
        "citation_count": record.citation_count,
        "input_tokens": record.input_tokens,
        "output_tokens": record.output_tokens,
        "total_tokens": record.total_tokens,
        "is_token_estimated": record.is_token_estimated,
        "estimated_cost_usd": record.estimated_cost_usd,
        "pricing_status": record.pricing_status,
        "retrieval_metadata": record.retrieval_metadata,
        "input_preview": None if mask_previews else record.input_preview,
        "output_preview": None if mask_previews else record.output_preview,
        "has_preview": record.has_preview and not mask_previews,
        "span_count": len(record.spans_data) if record.spans_data else 0,
        "spans": record.spans_data or [],
    }


@router.get("/traces")
async def list_recent_traces(
    assistant_id: Optional[uuid.UUID] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    traffic_type: Optional[str] = Query(default=None),
    provider: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    cursor: Optional[str] = Query(default=None),
    tenant_ctx: TenantContext = Depends(require_permission(PermissionName.USAGE_READ)),
    db: AsyncSession = Depends(get_db),
):
    """List recent assistant request traces for the authenticated tenant with server-side filters and pagination."""
    mask_previews = not tenant_ctx.is_admin

    # 1. Query database traces (PostgreSQL authoritative source of truth)
    stmt = (
        select(RequestTrace)
        .where(RequestTrace.tenant_id == tenant_ctx.tenant.id)
        .order_by(RequestTrace.created_at.desc())
    )

    if assistant_id:
        stmt = stmt.where(RequestTrace.assistant_id == assistant_id)
    if status_filter:
        stmt = stmt.where(RequestTrace.status == status_filter)
    if traffic_type:
        stmt = stmt.where(RequestTrace.traffic_type == traffic_type)
    if provider:
        stmt = stmt.where(RequestTrace.provider == provider)
    if cursor:
        try:
            cursor_dt = datetime.fromisoformat(cursor)
            stmt = stmt.where(RequestTrace.created_at < cursor_dt)
        except (ValueError, TypeError):
            pass
    if search:
        s_pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                RequestTrace.trace_id.ilike(s_pattern),
                RequestTrace.assistant_name.ilike(s_pattern),
                RequestTrace.model.ilike(s_pattern),
                RequestTrace.error_category.ilike(s_pattern),
            )
        )

    stmt = stmt.offset(offset).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()

    # PostgreSQL is authoritative; when empty, return empty list (no memory fallback)
    return [_serialize_db_trace(r, mask_previews=mask_previews) for r in rows]


@router.get("/traces/{trace_id}", response_model=TraceDetailSchema)
async def get_trace_detail(
    trace_id: str,
    tenant_ctx: TenantContext = Depends(require_permission(PermissionName.USAGE_READ)),
    db: AsyncSession = Depends(get_db),
):
    """Fetch complete lifecycle spans, diagnostics, and metrics for an individual trace."""
    mask_previews = not tenant_ctx.is_admin

    # PostgreSQL is authoritative
    stmt = select(RequestTrace).where(
        RequestTrace.trace_id == trace_id,
        RequestTrace.tenant_id == tenant_ctx.tenant.id,
    )
    record = (await db.execute(stmt)).scalar_one_or_none()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trace not found or unauthorized",
        )
    return _serialize_db_trace(record, mask_previews=mask_previews)


@router.get("/metrics", response_model=ObservabilityMetricsSchema)
async def get_observability_metrics(
    period: str = Query(default="24h", pattern="^(24h|7d|30d|all)$"),
    tenant_ctx: TenantContext = Depends(require_permission(PermissionName.USAGE_READ)),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve operational latency percentiles, error rate, tokens, and cost estimates across all matching traces."""
    now = datetime.now(UTC)
    time_cutoff = None
    if period == "24h":
        time_cutoff = now - timedelta(hours=24)
    elif period == "7d":
        time_cutoff = now - timedelta(days=7)
    elif period == "30d":
        time_cutoff = now - timedelta(days=30)

    base_filter = [RequestTrace.tenant_id == tenant_ctx.tenant.id]
    if time_cutoff:
        base_filter.append(RequestTrace.created_at >= time_cutoff)

    # 1. Total requests & general aggregations (all historical rows without 1,000 limit)
    agg_stmt = select(
        func.count(RequestTrace.id),
        func.coalesce(func.sum(RequestTrace.total_tokens), 0),
        func.coalesce(func.sum(RequestTrace.estimated_cost_usd), 0.0),
        func.coalesce(func.avg(RequestTrace.total_duration_ms), 0.0),
        func.coalesce(func.avg(RequestTrace.ttft_ms), 0.0),
    ).where(*base_filter)

    agg_row = (await db.execute(agg_stmt)).one()
    total_requests = int(agg_row[0])
    total_tokens = int(agg_row[1])
    total_cost = float(agg_row[2])
    avg_latency = float(agg_row[3])
    avg_ttft = float(agg_row[4])

    if total_requests == 0:
        return {
            "total_requests": 0,
            "error_rate": 0.0,
            "avg_latency_ms": 0.0,
            "p50_latency_ms": 0.0,
            "p95_latency_ms": 0.0,
            "p99_latency_ms": 0.0,
            "avg_ttft_ms": 0.0,
            "total_tokens": 0,
            "estimated_cost_usd": 0.0,
            "by_status": {},
            "by_traffic_type": {},
            "by_provider": {},
            "by_error_category": {},
        }

    # 2. Status counts (separate CANCELLED from FAILED)
    status_stmt = (
        select(RequestTrace.status, func.count(RequestTrace.id))
        .where(*base_filter)
        .group_by(RequestTrace.status)
    )
    by_status = {row[0]: int(row[1]) for row in (await db.execute(status_stmt)).all()}

    # Cancellation is separated from server errors
    failed_count = by_status.get("FAILED", 0)
    error_rate = round(failed_count / total_requests, 4) if total_requests > 0 else 0.0

    # 3. Traffic type counts
    traffic_stmt = (
        select(RequestTrace.traffic_type, func.count(RequestTrace.id))
        .where(*base_filter)
        .group_by(RequestTrace.traffic_type)
    )
    by_traffic = {row[0]: int(row[1]) for row in (await db.execute(traffic_stmt)).all()}

    # 4. Provider counts
    provider_stmt = (
        select(func.coalesce(RequestTrace.provider, "unknown"), func.count(RequestTrace.id))
        .where(*base_filter)
        .group_by(RequestTrace.provider)
    )
    by_provider = {row[0]: int(row[1]) for row in (await db.execute(provider_stmt)).all()}

    # 5. Error category counts
    error_cat_stmt = (
        select(RequestTrace.error_category, func.count(RequestTrace.id))
        .where(*base_filter, RequestTrace.error_category.isnot(None))
        .group_by(RequestTrace.error_category)
    )
    by_error_cat = {row[0]: int(row[1]) for row in (await db.execute(error_cat_stmt)).all()}

    # 6. Latency percentiles calculation
    latencies_stmt = (
        select(RequestTrace.total_duration_ms)
        .where(*base_filter, RequestTrace.total_duration_ms.isnot(None))
        .order_by(RequestTrace.total_duration_ms.asc())
    )
    completed_latencies = list((await db.execute(latencies_stmt)).scalars().all())
    n = len(completed_latencies)
    p50_val = completed_latencies[int(n * 0.50)] if n else 0.0
    p95_val = completed_latencies[min(int(n * 0.95), n - 1)] if n else 0.0
    p99_val = completed_latencies[min(int(n * 0.99), n - 1)] if n else 0.0

    return {
        "total_requests": total_requests,
        "error_rate": error_rate,
        "avg_latency_ms": round(avg_latency, 2),
        "p50_latency_ms": round(p50_val, 2),
        "p95_latency_ms": round(p95_val, 2),
        "p99_latency_ms": round(p99_val, 2),
        "avg_ttft_ms": round(avg_ttft, 2),
        "total_tokens": total_tokens,
        "estimated_cost_usd": round(total_cost, 4),
        "by_status": by_status,
        "by_traffic_type": by_traffic,
        "by_provider": by_provider,
        "by_error_category": by_error_cat,
    }


@router.get("/policy", response_model=ObservabilityPolicySchema)
async def get_observability_policy(
    tenant_ctx: TenantContext = Depends(require_permission(PermissionName.USAGE_READ)),
    db: AsyncSession = Depends(get_db),
):
    """Fetch active workspace observability capture policy."""
    svc = ObservabilityPolicyService(db, tenant_ctx.tenant.id)
    policy = await svc.get_policy()
    return policy


@router.put("/policy", response_model=ObservabilityPolicySchema)
async def update_observability_policy(
    body: ObservabilityPolicyUpdate,
    tenant_ctx: TenantContext = Depends(require_permission(PermissionName.USAGE_READ)),
    db: AsyncSession = Depends(get_db),
):
    """Update workspace observability capture policy (Owner or Admin required)."""
    if not tenant_ctx.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only workspace owners and administrators may configure observability policies.",
        )

    svc = ObservabilityPolicyService(db, tenant_ctx.tenant.id)
    updated = await svc.update_policy(
        capture_mode=body.capture_mode,
        max_preview_length=body.max_preview_length,
        retention_days=body.retention_days,
    )
    return updated


@router.post("/purge", response_model=PurgeResultSchema)
async def purge_expired_traces(
    tenant_ctx: TenantContext = Depends(require_permission(PermissionName.USAGE_READ)),
    db: AsyncSession = Depends(get_db),
):
    """Purge traces older than the workspace retention policy period (Owner or Admin required)."""
    if not tenant_ctx.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only workspace owners and administrators may purge telemetry data.",
        )

    svc = ObservabilityPolicyService(db, tenant_ctx.tenant.id)
    policy = await svc.get_policy()

    cutoff_date = datetime.now(UTC) - timedelta(days=policy.retention_days)
    del_stmt = (
        delete(RequestTrace)
        .where(
            RequestTrace.tenant_id == tenant_ctx.tenant.id,
            RequestTrace.created_at < cutoff_date,
        )
    )
    result = await db.execute(del_stmt)
    await db.commit()

    return {
        "purged_count": result.rowcount,
        "retention_days": policy.retention_days,
        "message": f"Successfully purged traces older than {policy.retention_days} days.",
    }
