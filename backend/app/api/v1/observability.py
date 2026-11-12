"""API endpoints for Platform Observability, Request Traces, and Operational Metrics."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import TenantContext, require_permission
from app.core.constants import PermissionName
from app.observability.tracer import get_tracer

router = APIRouter(prefix="/observability", tags=["Platform Observability"])


@router.get("/traces")
async def list_recent_traces(
    assistant_id: Optional[uuid.UUID] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    traffic_type: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    tenant_ctx: TenantContext = Depends(require_permission(PermissionName.USAGE_READ)),
):
    """List recent assistant request traces for the authenticated tenant."""
    tracer = get_tracer()
    traces = tracer.list_traces(
        tenant_id=tenant_ctx.tenant.id,
        assistant_id=assistant_id,
        status=status_filter,
        traffic_type=traffic_type,
        limit=limit,
    )
    return [t.to_dict() for t in traces]


@router.get("/traces/{trace_id}")
async def get_trace_detail(
    trace_id: str,
    tenant_ctx: TenantContext = Depends(require_permission(PermissionName.USAGE_READ)),
):
    """Fetch complete lifecycle spans and metrics for an individual trace."""
    tracer = get_tracer()
    trace = tracer.get_trace(trace_id=trace_id, tenant_id=tenant_ctx.tenant.id)
    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trace not found or unauthorized",
        )
    return trace.to_dict()


@router.get("/metrics")
async def get_observability_metrics(
    tenant_ctx: TenantContext = Depends(require_permission(PermissionName.USAGE_READ)),
):
    """Retrieve operational latency, error rate, and throughput metrics across recent requests."""
    tracer = get_tracer()
    return tracer.get_metrics_summary(tenant_id=tenant_ctx.tenant.id)
