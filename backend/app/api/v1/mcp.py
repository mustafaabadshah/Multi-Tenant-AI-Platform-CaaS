"""API router for Model Context Protocol (MCP) Connections and Tool Discovery."""

import uuid
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, get_current_user, get_db, require_permission
from app.core.config import settings
from app.core.constants import PermissionName
from app.core.crypto import decrypt_secret, encrypt_secret
from app.models.mcp import MCPConnection
from app.models.user import User
from app.schemas.mcp import (
    MCPConnectionCreateRequest,
    MCPConnectionResponse,
    MCPDiscoverResponse,
    MCPToolApproveRequest,
)
from app.services.mcp.client import MCPClientError, MCPClientService
from app.services.tools.ssrf import SSRFSecurityError, validate_outbound_url

router = APIRouter(prefix="/mcp", tags=["MCP Connections"])



@router.get("/connections", response_model=list[MCPConnectionResponse])
async def list_mcp_connections(
    db: AsyncSession = Depends(get_db),
    tenant_ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_READ.value)),
):
    """List all configured MCP server connections for the active workspace."""
    stmt = (
        select(MCPConnection)
        .where(MCPConnection.tenant_id == tenant_ctx.tenant.id)
        .order_by(MCPConnection.created_at.desc())
    )
    results = (await db.execute(stmt)).scalars().all()
    return [MCPConnectionResponse.model_validate(c) for c in results]


@router.post("/connections", response_model=MCPConnectionResponse, status_code=status.HTTP_201_CREATED)
async def create_mcp_connection(
    payload: MCPConnectionCreateRequest,
    db: AsyncSession = Depends(get_db),
    tenant_ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_UPDATE.value)),
    current_user: User = Depends(get_current_user),
):
    """Register a new remote MCP server connection with upfront SSRF validation."""
    # 0. Enforce Feature Flag & Host Whitelist Boundary
    if not settings.MCP_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MCP integrations are currently disabled by platform security policy.",
        )
    if settings.MCP_ALLOWED_HOSTS and settings.MCP_ALLOWED_HOSTS.strip() != "*":
        allowed = [h.strip().lower() for h in settings.MCP_ALLOWED_HOSTS.split(",") if h.strip()]
        host = (urlparse(payload.server_url.strip()).hostname or "").lower()
        if not any(host == a or host.endswith("." + a) for a in allowed):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Host '{host}' is not in the allowed MCP host list.",
            )

    # 1. Enforce SSRF Defense Boundary
    try:
        validated_url = validate_outbound_url(payload.server_url)
    except SSRFSecurityError as ssrf_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Security violation: {str(ssrf_err)}",
        )

    # 2. Encrypt Credential if provided
    encrypted_token = None
    if payload.credential:
        encrypted_token = encrypt_secret(payload.credential)


    connection = MCPConnection(
        tenant_id=tenant_ctx.tenant.id,
        user_id=current_user.id if payload.is_personal else None,
        display_name=payload.display_name.strip(),
        server_url=validated_url,
        auth_mode=payload.auth_mode,
        encrypted_credential=encrypted_token,
        connection_status="CONNECTED",
        server_capabilities={"tools": True},
        approved_tools=[],
        is_enabled=True,
    )
    db.add(connection)
    await db.commit()
    await db.refresh(connection)
    return MCPConnectionResponse.model_validate(connection)


@router.get("/connections/{connection_id}", response_model=MCPConnectionResponse)
async def get_mcp_connection(
    connection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant_ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_READ.value)),
):
    """Retrieve details for a specific MCP connection."""
    stmt = select(MCPConnection).where(
        MCPConnection.id == connection_id,
        MCPConnection.tenant_id == tenant_ctx.tenant.id,
    )
    conn = (await db.execute(stmt)).scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MCP connection not found.")
    return MCPConnectionResponse.model_validate(conn)


@router.post("/connections/{connection_id}/discover", response_model=MCPDiscoverResponse)
async def discover_mcp_tools(
    connection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant_ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_UPDATE.value)),
):
    """Query remote MCP server for published tools and schema fingerprints."""
    stmt = select(MCPConnection).where(
        MCPConnection.id == connection_id,
        MCPConnection.tenant_id == tenant_ctx.tenant.id,
    )
    conn = (await db.execute(stmt)).scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MCP connection not found.")

    decrypted_token = None
    if conn.encrypted_credential:
        decrypted_token = decrypt_secret(conn.encrypted_credential)

    try:
        tools = await MCPClientService.discover_tools(
            server_url=conn.server_url,
            auth_token=decrypted_token,
        )
        return MCPDiscoverResponse(server_url=conn.server_url, tools=tools)
    except (MCPClientError, SSRFSecurityError) as err:
        conn.connection_status = "ERROR"
        await db.commit()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"MCP Discovery failed: {str(err)}")


@router.post("/connections/{connection_id}/approve-tools", response_model=MCPConnectionResponse)
async def approve_mcp_tools(
    connection_id: uuid.UUID,
    payload: MCPToolApproveRequest,
    db: AsyncSession = Depends(get_db),
    tenant_ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_UPDATE.value)),
):
    """Approve discovered tools to be made available for assistant execution."""
    stmt = select(MCPConnection).where(
        MCPConnection.id == connection_id,
        MCPConnection.tenant_id == tenant_ctx.tenant.id,
    )
    conn = (await db.execute(stmt)).scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MCP connection not found.")

    decrypted_token = None
    if conn.encrypted_credential:
        decrypted_token = decrypt_secret(conn.encrypted_credential)


    # Discover current tools to get exact fingerprints
    try:
        discovered = await MCPClientService.discover_tools(
            server_url=conn.server_url,
            auth_token=decrypted_token,
        )
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Could not verify tools: {err}")

    approved_list = []
    discovered_map = {t["name"]: t for t in discovered}

    for name in payload.tool_names:
        if name in discovered_map:
            approved_list.append(discovered_map[name])

    conn.approved_tools = approved_list
    await db.commit()
    await db.refresh(conn)
    return MCPConnectionResponse.model_validate(conn)


@router.delete("/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mcp_connection(
    connection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant_ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_DELETE.value)),
):
    """Remove an MCP server connection from the workspace."""
    stmt = select(MCPConnection).where(
        MCPConnection.id == connection_id,
        MCPConnection.tenant_id == tenant_ctx.tenant.id,
    )
    conn = (await db.execute(stmt)).scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MCP connection not found.")

    await db.delete(conn)
    await db.commit()
