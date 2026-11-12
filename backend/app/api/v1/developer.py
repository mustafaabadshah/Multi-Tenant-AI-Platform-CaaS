"""Developer API Key Management and Programmatic Assistant Inference Endpoints."""

import json
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, get_db, require_permission
from app.api.v1.assistants import _to_response
from app.assistant_runtime.runtime import AssistantRuntime
from app.core.config import settings
from app.core.constants import PermissionName
from app.core.rate_limit import enforce_rate_limit
from app.models.conversation import Conversation
from app.models.publishing import APIKey
from app.models.tenant import Tenant
from app.repositories.assistant_repository import AssistantRepository
from app.schemas.assistant import AssistantResponse
from app.schemas.publishing import (
    APIKeyCreate,
    APIKeyCreatedResponse,
    APIKeyResponse,
    DeveloperChatRequest,
)
from app.services.api_key_service import APIKeyService

router = APIRouter(prefix="/developer", tags=["Developer Platform & APIs"])


def _serialize_api_key(key: APIKey) -> APIKeyResponse:
    try:
        scopes = json.loads(key.scopes) if isinstance(key.scopes, str) else (key.scopes or [])
    except Exception:
        scopes = []

    return APIKeyResponse(
        id=key.id,
        tenant_id=key.tenant_id,
        user_id=key.user_id,
        assistant_id=key.assistant_id,
        name=key.name,
        key_prefix=key.key_prefix,
        scopes=scopes,
        expires_at=key.expires_at,
        last_used_at=key.last_used_at,
        is_active=key.is_active,
        created_at=key.created_at,
        updated_at=key.updated_at,
    )


# --- Workspace Admin API Key Endpoints (JWT Authenticated) ---


@router.get("/api-keys", response_model=list[APIKeyResponse])
async def list_api_keys(
    ctx: TenantContext = Depends(require_permission(PermissionName.API_KEY_READ.value)),
    db: AsyncSession = Depends(get_db),
) -> list[APIKeyResponse]:
    """List developer API keys configured for the active workspace."""
    svc = APIKeyService(db, ctx.tenant.id)
    keys = await svc.list_keys()
    return [_serialize_api_key(k) for k in keys]


@router.post("/api-keys", response_model=APIKeyCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    payload: APIKeyCreate,
    ctx: TenantContext = Depends(require_permission(PermissionName.API_KEY_MANAGE.value)),
    db: AsyncSession = Depends(get_db),
) -> APIKeyCreatedResponse:
    """Generate a new scoped developer API key. The secret token is returned ONLY ONCE."""
    svc = APIKeyService(db, ctx.tenant.id)
    key_record, raw_key = await svc.generate_api_key(payload, user_id=ctx.membership.user_id)
    serialized = _serialize_api_key(key_record)
    return APIKeyCreatedResponse(
        **serialized.model_dump(),
        raw_key=raw_key,
    )


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.API_KEY_MANAGE.value)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Revoke and deactivate a developer API key immediately."""
    svc = APIKeyService(db, ctx.tenant.id)
    success = await svc.revoke_key(key_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found in active workspace",
        )
    return {"success": True, "message": "API key revoked"}


# --- Programmatic Developer API Endpoints (Bearer API-Key Authenticated) ---


def require_developer_api_key(required_scope: Optional[str] = None):
    async def _dependency(
        authorization: Optional[str] = Header(None, alias="Authorization"),
        db: AsyncSession = Depends(get_db),
    ) -> tuple[APIKey, Tenant]:
        """Dependency validating developer Bearer API keys with optional scope requirement."""
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or malformed Authorization header. Expected 'Bearer mmaip_live_...'",
                headers={"WWW-Authenticate": "Bearer"},
            )

        raw_key = authorization.split("Bearer ", 1)[1].strip()
        svc = APIKeyService(db)
        return await svc.verify_api_key(raw_key, required_scope=required_scope)

    return _dependency


authenticate_developer_api_key = require_developer_api_key("assistant:chat")


@router.get("/assistants", response_model=list[AssistantResponse])
async def list_developer_assistants(
    auth_data: tuple[APIKey, Tenant] = Depends(require_developer_api_key("assistant:read")),
    db: AsyncSession = Depends(get_db),
) -> list[AssistantResponse]:
    """List assistants available to the authenticated API key's organization."""
    api_key, tenant = auth_data
    repo = AssistantRepository(db, tenant.id)
    assistants = await repo.list()
    if api_key.assistant_id:
        assistants = [a for a in assistants if a.id == api_key.assistant_id]
    responses = []
    for a in assistants:
        kb_ids = await repo.get_connected_kb_ids(a.id)
        responses.append(_to_response(a, kb_ids))
    return responses


@router.post("/assistants/{assistant_id}/chat")
async def developer_chat_stream(
    assistant_id: uuid.UUID,
    payload: DeveloperChatRequest,
    auth_data: tuple[APIKey, Tenant] = Depends(require_developer_api_key("assistant:chat")),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Stream chat responses programmatically using scoped Developer API key."""
    api_key, tenant = auth_data

    # Per-API-key limit; the key id is an opaque identifier, not the raw secret.
    await enforce_rate_limit(
        "developer.chat",
        str(api_key.id),
        settings.RATE_LIMIT_DEVELOPER_PER_MINUTE,
        60,
    )

    # Enforce assistant restriction if key is scoped to a specific assistant
    if api_key.assistant_id and api_key.assistant_id != assistant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"API key is restricted to assistant '{api_key.assistant_id}'.",
        )

    repo = AssistantRepository(db, tenant.id)
    asst = await repo.get_by_id(assistant_id)
    if not asst:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assistant {assistant_id} not found in authorized organization",
        )

    # Resolve or create conversation
    conv_id = payload.conversation_id
    if not conv_id:
        conv_id = uuid.uuid4()
        conv = Conversation(
            id=conv_id,
            tenant_id=tenant.id,
            assistant_id=asst.id,
            user_id=api_key.user_id,
            title=payload.message[:40],
        )
        db.add(conv)
        await db.commit()

    runtime = AssistantRuntime(
        session=db,
        tenant_id=tenant.id,
        user_id=api_key.user_id,
        is_admin=True,  # Developer API key operates with assistant execution privileges
    )

    stream_gen = runtime.stream_chat(
        conversation_id=conv_id,
        user_message=payload.message,
        is_public=False,
        traffic_type="developer_api",
    )

    return StreamingResponse(
        stream_gen,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
