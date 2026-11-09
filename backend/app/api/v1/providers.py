"""Provider Directory, BYOK Key Vault, and Usage Quota API Endpoints."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, get_current_user, get_db, require_permission
from app.core.constants import PermissionName
from app.llm.registry import get_llm_registry
from app.models.user import User
from app.schemas.provider import (
    ProviderCredentialCreate,
    ProviderCredentialResponse,
    ProviderCredentialRotateRequest,
    ProviderDirectoryItem,
    ProviderUsageSummaryResponse,
)
from app.services.byok_vault import BYOKVaultService
from app.services.quota_service import QuotaService

router = APIRouter(prefix="/providers", tags=["Providers & BYOK Vault"])


@router.get("/directory", response_model=list[ProviderDirectoryItem])
async def list_provider_directory(
    ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_READ.value)),
) -> list[dict[str, Any]]:
    """List available providers and current capability-verified model catalogs."""
    registry = get_llm_registry()
    return registry.list_providers()


@router.get("/credentials", response_model=list[ProviderCredentialResponse])
async def list_credentials(
    ctx: TenantContext = Depends(require_permission(PermissionName.TENANT_READ.value)),
    db: AsyncSession = Depends(get_db),
) -> list[ProviderCredentialResponse]:
    """List configured BYOK credentials for the active workspace (secrets are encrypted and masked)."""
    vault = BYOKVaultService(db, ctx.tenant.id)
    creds = await vault.list_credentials()
    return [ProviderCredentialResponse.model_validate(c) for c in creds]


@router.post("/credentials", response_model=ProviderCredentialResponse, status_code=status.HTTP_201_CREATED)
async def create_credential(
    payload: ProviderCredentialCreate,
    ctx: TenantContext = Depends(require_permission(PermissionName.TENANT_UPDATE.value)),
    db: AsyncSession = Depends(get_db),
) -> ProviderCredentialResponse:
    """Securely encrypt and store a BYOK provider credential using Fernet."""
    vault = BYOKVaultService(db, ctx.tenant.id)
    cred = await vault.add_credential(
        provider_name=payload.provider_name,
        display_name=payload.display_name,
        api_key=payload.api_key,
        base_url=payload.base_url,
        is_default=payload.is_default,
    )
    return ProviderCredentialResponse.model_validate(cred)


@router.post("/credentials/{credential_id}/test")
async def test_credential(
    credential_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.TENANT_UPDATE.value)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Test connection and validate credential with provider endpoint in memory."""
    vault = BYOKVaultService(db, ctx.tenant.id)
    is_valid, err = await vault.test_credential(credential_id)
    return {"valid": is_valid, "error": err}


@router.post("/credentials/{credential_id}/rotate", response_model=ProviderCredentialResponse)
async def rotate_credential(
    credential_id: uuid.UUID,
    payload: ProviderCredentialRotateRequest,
    ctx: TenantContext = Depends(require_permission(PermissionName.TENANT_UPDATE.value)),
    db: AsyncSession = Depends(get_db),
) -> ProviderCredentialResponse:
    """Rotate an existing provider key without exposing plaintext."""
    vault = BYOKVaultService(db, ctx.tenant.id)
    cred = await vault.rotate_credential(credential_id, payload.new_api_key)
    if not cred:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found in active workspace",
        )
    return ProviderCredentialResponse.model_validate(cred)


@router.post("/credentials/{credential_id}/revoke", response_model=ProviderCredentialResponse)
async def revoke_credential(
    credential_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.TENANT_UPDATE.value)),
    db: AsyncSession = Depends(get_db),
) -> ProviderCredentialResponse:
    """Immediately revoke and deactivate a provider credential."""
    vault = BYOKVaultService(db, ctx.tenant.id)
    cred = await vault.revoke_credential(credential_id)
    if not cred:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found in active workspace",
        )
    return ProviderCredentialResponse.model_validate(cred)


@router.delete("/credentials/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credential(
    credential_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.TENANT_UPDATE.value)),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Permanently delete a provider credential."""
    vault = BYOKVaultService(db, ctx.tenant.id)
    success = await vault.delete_credential(credential_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found in active workspace",
        )


@router.get("/usage", response_model=ProviderUsageSummaryResponse)
@router.get("/usage/summary", response_model=ProviderUsageSummaryResponse)
async def get_usage_summary(
    ctx: TenantContext = Depends(require_permission(PermissionName.TENANT_READ.value)),
    db: AsyncSession = Depends(get_db),
) -> ProviderUsageSummaryResponse:
    """Get accurate usage accounting and quota status for the active tenant."""
    quota_svc = QuotaService(db, ctx.tenant.id)
    summary = await quota_svc.get_usage_summary()
    return ProviderUsageSummaryResponse(**summary)
