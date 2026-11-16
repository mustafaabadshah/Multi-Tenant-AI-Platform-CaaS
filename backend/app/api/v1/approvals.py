"""API router for Human-in-the-Loop Tool Approvals."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, get_current_user, get_db, require_permission
from app.core.constants import PermissionName
from app.models.mcp import ToolApproval
from app.models.user import User
from app.schemas.approval import ToolApprovalDecisionRequest, ToolApprovalResponse
from app.services.tools.approval_service import ToolApprovalService

router = APIRouter(prefix="/approvals", tags=["Tool Approvals"])


@router.get("/pending", response_model=list[ToolApprovalResponse])
async def list_pending_approvals(
    conversation_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    tenant_ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_READ.value)),
):
    """List pending tool approval requests for a specific conversation in the active workspace."""
    svc = ToolApprovalService(db, tenant_ctx.tenant.id)
    approvals = await svc.list_pending_for_conversation(conversation_id)
    return [ToolApprovalResponse.model_validate(a) for a in approvals]


@router.get("/{approval_id}", response_model=ToolApprovalResponse)
async def get_approval_detail(
    approval_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant_ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_READ.value)),
):
    """Inspect a specific tool approval request."""
    svc = ToolApprovalService(db, tenant_ctx.tenant.id)
    approval = await svc.get_approval(approval_id)
    if not approval:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval request not found.")
    return ToolApprovalResponse.model_validate(approval)


@router.post("/{approval_id}/approve", response_model=ToolApprovalResponse)
async def approve_tool_execution(
    approval_id: uuid.UUID,
    payload: ToolApprovalDecisionRequest,
    db: AsyncSession = Depends(get_db),
    tenant_ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_EXECUTE.value)),
    current_user: User = Depends(get_current_user),
):
    """Approve a pending tool action. Validates single-use token and prevents replay attacks."""
    svc = ToolApprovalService(db, tenant_ctx.tenant.id)
    try:
        approval = await svc.approve_and_consume(
            approval_id=approval_id,
            user_id=current_user.id,
            token=payload.token,
        )
        return ToolApprovalResponse.model_validate(approval)
    except PermissionError as perm_err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(perm_err))
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))


@router.post("/{approval_id}/deny", response_model=ToolApprovalResponse)
async def deny_tool_execution(
    approval_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant_ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_EXECUTE.value)),
    current_user: User = Depends(get_current_user),
):
    """Explicitly deny a pending tool action."""
    svc = ToolApprovalService(db, tenant_ctx.tenant.id)
    try:
        approval = await svc.deny(approval_id=approval_id, user_id=current_user.id)
        return ToolApprovalResponse.model_validate(approval)
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))
