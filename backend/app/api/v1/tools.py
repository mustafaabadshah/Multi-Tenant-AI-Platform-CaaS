"""API endpoints for the Tool Registry and Safe Tool Execution."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, get_current_user, get_db, require_permission
from app.core.constants import PermissionName
from app.models.tool import Tool
from app.models.user import User
from app.schemas.tool import (
    ToolCreateRequest,
    ToolExecuteRequest,
    ToolExecuteResponse,
    ToolResponse,
)
from app.services.tools.registry import ToolRegistryService
from app.services.tools.ssrf import SSRFSecurityError

router = APIRouter(prefix="/tools", tags=["Tool Registry"])


@router.get("", response_model=list[ToolResponse])
async def list_available_tools(
    tool_type: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    tenant_ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_READ.value)),
):
    """List all tools available in the active workspace (Built-in + Custom HTTP + MCP)."""
    svc = ToolRegistryService(db, tenant_ctx.tenant.id, user_id=tenant_ctx.user_id)
    tools = await svc.list_tools(tool_type=tool_type)
    return [ToolResponse(**t) for t in tools]


@router.post("", response_model=ToolResponse, status_code=status.HTTP_201_CREATED)
async def create_custom_tool(
    payload: ToolCreateRequest,
    db: AsyncSession = Depends(get_db),
    tenant_ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_UPDATE.value)),
    current_user: User = Depends(get_current_user),
):
    """Register a new Custom HTTP tool with URL safety validation."""
    svc = ToolRegistryService(db, tenant_ctx.tenant.id, user_id=current_user.id)
    try:
        tool = await svc.create_custom_tool(
            name=payload.name,
            display_name=payload.display_name,
            endpoint_url=payload.endpoint_url,
            description=payload.description,
            method=payload.method,
            input_schema=payload.input_schema,
            output_schema=payload.output_schema,
            headers=payload.headers,
            risk_level=payload.risk_level,
            requires_approval=payload.requires_approval,
            timeout_seconds=payload.timeout_seconds,
        )
    except SSRFSecurityError as ssrf_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Security violation: {str(ssrf_err)}",
        )
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(val_err))

    return ToolResponse(
        id=str(tool.id),
        name=tool.name,
        display_name=tool.display_name,
        description=tool.description,
        namespace=tool.namespace,
        tool_type=tool.tool_type,
        risk_level=tool.risk_level,
        requires_approval=tool.requires_approval,
        is_enabled=tool.is_enabled,
        version=tool.version,
        input_schema=tool.input_schema,
        output_schema=tool.output_schema,
        http_config=tool.http_config,
        created_at=tool.created_at.isoformat() if tool.created_at else None,
    )


@router.get("/{tool_id}", response_model=ToolResponse)
async def get_tool_detail(
    tool_id: str,
    db: AsyncSession = Depends(get_db),
    tenant_ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_READ.value)),
):
    """Retrieve configuration and schema for a specific tool."""
    svc = ToolRegistryService(db, tenant_ctx.tenant.id, user_id=tenant_ctx.user_id)
    tool = await svc.get_tool(tool_id)
    if not tool:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found")
    return ToolResponse(**tool)


from app.repositories.audit_repository import AuditLogRepository


@router.post("/{tool_id}/execute", response_model=ToolExecuteResponse)
async def execute_tool_endpoint(
    tool_id: str,
    payload: ToolExecuteRequest,
    db: AsyncSession = Depends(get_db),
    tenant_ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_EXECUTE.value)),
    current_user: User = Depends(get_current_user),
):
    """Test and execute a tool directly with bounded parameters and security audit logging."""
    svc = ToolRegistryService(db, tenant_ctx.tenant.id, user_id=tenant_ctx.user_id)
    tool = await svc.get_tool(tool_id)
    if not tool:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found")

    # Safety Gate (Phase C1): Mutating, high-risk, or approval-gated tools require administrative permissions to test directly
    if tool.get("requires_approval") or tool.get("risk_level") in ("WRITE", "HIGH_RISK"):
        if "*" not in tenant_ctx.permissions and PermissionName.ASSISTANT_UPDATE.value not in tenant_ctx.permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Direct testing of mutating or approval-gated tools requires workspace administrative permissions.",
            )

    try:
        result = await svc.execute_tool(tool_id, payload.arguments)

        # Audit log the execution
        audit_repo = AuditLogRepository(db, tenant_ctx.tenant.id)
        tool_uuid = None
        try:
            tool_uuid = uuid.UUID(tool["id"])
        except (ValueError, TypeError):
            pass

        await audit_repo.log_event(
            action="tool.execute_test",
            resource_type="tool",
            resource_id=tool_uuid,
            actor_id=current_user.id,
            details={
                "tool_name": tool["name"],
                "risk_level": tool.get("risk_level"),
                "requires_approval": tool.get("requires_approval"),
            },
        )
        await db.commit()

        return ToolExecuteResponse(
            status_code=200,
            is_success=True,
            data=result,
        )
    except SSRFSecurityError as ssrf_err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Outbound execution blocked by security boundary: {str(ssrf_err)}",
        )
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Tool execution failed: {str(exc)}")


@router.delete("/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_custom_tool(
    tool_id: str,
    db: AsyncSession = Depends(get_db),
    tenant_ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_DELETE.value)),
):

    """Delete a custom tool from the workspace."""
    try:
        t_uuid = uuid.UUID(tool_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete built-in tools.")

    stmt = select(Tool).where(Tool.id == t_uuid, Tool.tenant_id == tenant_ctx.tenant.id)
    tool = (await db.execute(stmt)).scalar_one_or_none()
    if not tool:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found")

    await db.delete(tool)
    await db.commit()
