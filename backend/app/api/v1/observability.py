"""API endpoints for Platform Observability, Request Traces, and Operational Metrics."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, require_permission
from app.core.constants import PermissionName
from app.database.session import get_db
from app.models.trace import RequestTrace
from app.observability.policy import ObservabilityPolicyService
from app.observability.tracer import get_tracer
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
    tenant_ctx: TenantContext = Depends(require_permission(PermissionName.USAGE_READ)),
    db: AsyncSession = Depends(get_db),
):
    """List recent assistant request traces for the authenticated tenant with server-side filters."""
    mask_previews = not tenant_ctx.is_admin

    # 1. Query database traces
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

    stmt = stmt.limit(limit)
    rows = (await db.execute(stmt)).scalars().all()

    if rows:
        return [_serialize_db_trace(r, mask_previews=mask_previews) for r in rows]

    # 2. Fallback to in-memory tracer if DB has 0 records (e.g. fresh memory-only tests)
    tracer = get_tracer()
    traces = tracer.list_traces(
        tenant_id=tenant_ctx.tenant.id,
        assistant_id=assistant_id,
        status=status_filter,
        traffic_type=traffic_type,
        limit=limit,
    )
    return [t.to_dict(mask_previews=mask_previews) for t in traces]


@router.get("/traces/{trace_id}", response_model=TraceDetailSchema)
async def get_trace_detail(
    trace_id: str,
    tenant_ctx: TenantContext = Depends(require_permission(PermissionName.USAGE_READ)),
    db: AsyncSession = Depends(get_db),
):
    """Fetch complete lifecycle spans, diagnostics, and metrics for an individual trace."""
    mask_previews = not tenant_ctx.is_admin

    # 1. Query database first
    stmt = select(RequestTrace).where(
        RequestTrace.trace_id == trace_id,
        RequestTrace.tenant_id == tenant_ctx.tenant.id,
    )
    record = (await db.execute(stmt)).scalar_one_or_none()
    if record:
        return _serialize_db_trace(record, mask_previews=mask_previews)

    # 2. Fallback to in-memory tracer
    tracer = get_tracer()
    trace = tracer.get_trace(trace_id=trace_id, tenant_id=tenant_ctx.tenant.id)
    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trace not found or unauthorized",
        )
    return trace.to_dict(mask_previews=mask_previews)


@router.get("/metrics", response_model=ObservabilityMetricsSchema)
async def get_observability_metrics(
    period: str = Query(default="24h", pattern="^(24h|7d|30d|all)$"),
    tenant_ctx: TenantContext = Depends(require_permission(PermissionName.USAGE_READ)),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve operational latency percentiles, error rate, tokens, and cost estimates."""
    now = datetime.now(UTC)
    time_cutoff = None
    if period == "24h":
        time_cutoff = now - timedelta(hours=24)
    elif period == "7d":
        time_cutoff = now - timedelta(days=7)
    elif period == "30d":
        time_cutoff = now - timedelta(days=30)

    # 1. Check if DB has traces for this tenant
    stmt = select(RequestTrace).where(RequestTrace.tenant_id == tenant_ctx.tenant.id)
    if time_cutoff:
        stmt = stmt.where(RequestTrace.created_at >= time_cutoff)
    stmt = stmt.order_by(RequestTrace.created_at.desc()).limit(1000)

    rows = (await db.execute(stmt)).scalars().all()
    if not rows:
        # Fallback to in-memory tracer summary
        tracer = get_tracer()
        return tracer.get_metrics_summary(tenant_id=tenant_ctx.tenant.id)

    total_requests = len(rows)
    completed_latencies = [r.total_duration_ms for r in rows if r.total_duration_ms is not None]
    ttfts = [r.ttft_ms for r in rows if r.ttft_ms is not None]
    errors = sum(1 for r in rows if r.status in ("FAILED", "CANCELLED"))
    total_tokens = sum(r.total_tokens for r in rows)
    total_cost = sum(r.estimated_cost_usd for r in rows if r.estimated_cost_usd is not None)

    completed_latencies.sort()
    n = len(completed_latencies)
    p50_val = completed_latencies[int(n * 0.50)] if n else 0.0
    p95_val = completed_latencies[min(int(n * 0.95), n - 1)] if n else 0.0
    p99_val = completed_latencies[min(int(n * 0.99), n - 1)] if n else 0.0

    by_status: dict[str, int] = {}
    by_traffic: dict[str, int] = {}
    by_provider: dict[str, int] = {}
    by_error_cat: dict[str, int] = {}

    for r in rows:
        by_status[r.status] = by_status.get(r.status, 0) + 1
        by_traffic[r.traffic_type] = by_traffic.get(r.traffic_type, 0) + 1
        prov = r.provider or "unknown"
        by_provider[prov] = by_provider.get(prov, 0) + 1
        if r.error_category:
            by_error_cat[r.error_category] = by_error_cat.get(r.error_category, 0) + 1

    return {
        "total_requests": total_requests,
        "error_rate": round(errors / total_requests, 4),
        "avg_latency_ms": round(sum(completed_latencies) / n, 2) if n else 0.0,
        "p50_latency_ms": round(p50_val, 2),
        "p95_latency_ms": round(p95_val, 2),
        "p99_latency_ms": round(p99_val, 2),
        "avg_ttft_ms": round(sum(ttfts) / len(ttfts), 2) if ttfts else 0.0,
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
