"""Endpoints for vector store discovery and adapter health validation."""


from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, get_db, require_permission
from app.core.constants import PermissionName
from app.schemas.retrieval import (
    ValidateVectorStoreRequest,
    ValidateVectorStoreResponse,
    VectorStoreRead,
)
from app.vectorstores.registry import VectorStoreRegistry, get_vector_store

router = APIRouter(prefix="/vector-stores", tags=["Vector Stores"])


@router.get(
    "",
    response_model=list[VectorStoreRead],
    dependencies=[Depends(require_permission(PermissionName.RETRIEVAL_SEARCH))],
)
async def list_vector_stores():
    """List available vector store adapters and their capabilities."""
    stores = VectorStoreRegistry.list_available_stores()
    return [VectorStoreRead(**s) for s in stores]


@router.post(
    "/validate",
    response_model=ValidateVectorStoreResponse,
)
async def validate_vector_store(
    payload: ValidateVectorStoreRequest,
    ctx: TenantContext = Depends(require_permission(PermissionName.RETRIEVAL_CONFIGURE.value)),
    db: AsyncSession = Depends(get_db),
):
    """Perform health and connectivity validation for a vector store."""
    store = get_vector_store(
        payload.store_type,
        session=db,
        custom_endpoint=payload.endpoint,
        custom_api_key=payload.api_key,
    )
    health = await store.check_health()
    is_healthy = health.get("status") == "healthy"
    return ValidateVectorStoreResponse(
        valid=is_healthy,
        status=health.get("status", "unknown"),
        details=health,
    )
