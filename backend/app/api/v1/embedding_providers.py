"""Endpoints for discovering and validating embedding providers."""


from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import TenantContext, require_permission
from app.core.constants import PermissionName
from app.embeddings.base import EmbeddingProviderConfig
from app.embeddings.registry import get_embedding_registry
from app.schemas.retrieval import (
    EmbeddingProviderRead,
    ValidateProviderRequest,
    ValidateProviderResponse,
)

router = APIRouter(prefix="/embedding-providers", tags=["Embedding Providers"])


@router.get(
    "",
    response_model=list[EmbeddingProviderRead],
    dependencies=[Depends(require_permission(PermissionName.RETRIEVAL_SEARCH))],
)
async def list_embedding_providers():
    """List available embedding providers and default models."""
    registry = get_embedding_registry()
    providers = registry.list_providers()
    return [
        EmbeddingProviderRead(
            name=p["name"],
            default_model=p["default_model"],
            supported_models=p["supported_models"],
            default_dimensions=p["default_dimensions"],
        )
        for p in providers
    ]


@router.post(
    "/validate",
    response_model=ValidateProviderResponse,
)
async def validate_embedding_provider(
    payload: ValidateProviderRequest,
    ctx: TenantContext = Depends(require_permission(PermissionName.RETRIEVAL_CONFIGURE.value)),
):
    """Validate connectivity and authentication for a provider configuration."""
    registry = get_embedding_registry()
    try:
        provider = registry.get_provider(payload.provider_name)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider '{payload.provider_name}' not found.",
        )

    config = EmbeddingProviderConfig(
        provider_name=payload.provider_name,
        model_name=payload.model_name or provider.default_model,
        dimensions=payload.dimensions or provider.get_dimensions(payload.model_name),
        api_key=payload.api_key,
        base_url=payload.base_url,
        timeout_seconds=5,
        max_retries=1,
    )

    is_valid = await provider.validate_configuration(config)
    if is_valid:
        return ValidateProviderResponse(
            valid=True,
            message="Connection and authentication verified successfully.",
            dimensions=config.dimensions,
        )
    return ValidateProviderResponse(
        valid=False,
        message="Failed to connect to provider. Verify your API key and base URL.",
    )
