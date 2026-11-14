"""Public Assistant Web Chat, Embed Widget Configuration, and Streaming Inference Endpoints."""

import json
import logging
import uuid
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assistant_runtime.runtime import AssistantRuntime
from app.core.config import settings
from app.core.rate_limit import client_identity, enforce_rate_limit
from app.database.session import get_db
from app.models.conversation import Conversation
from app.schemas.publishing import (
    PublicAssistantMetadataResponse,
    PublicChatRequest,
)
from app.services.publishing_service import (
    PublishingService,
    ensure_public_publishing_enabled,
    is_origin_allowed,
    public_publishing_enabled,
)
from app.services.quota_service import QuotaService

logger = logging.getLogger("mmaip.api.public_chat")

router = APIRouter(prefix="/public", tags=["Public Assistant & Embed Widget"])


def _embed_frontend_origin() -> str | None:
    """Resolve the frontend origin used by the embed loader.

    Returns None (inert loader, no inference) when public publishing is
    disabled, FRONTEND_URL is missing or malformed, or a non-development
    environment is not served over HTTPS. There is deliberately no fallback to
    the backend script origin or to localhost.
    """
    if not public_publishing_enabled():
        return None

    raw = (settings.FRONTEND_URL or "").strip().rstrip("/")
    if not raw:
        return None

    try:
        parsed = urlparse(raw)
        port = parsed.port
    except (TypeError, ValueError):
        return None

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    if parsed.username or parsed.password:
        return None
    if port is not None and not 1 <= port <= 65535:
        return None

    is_dev = (settings.ENVIRONMENT or "").strip().lower() == "development"
    if not is_dev:
        host = (parsed.hostname or "").strip(".").lower()
        if parsed.scheme != "https" or host in {"localhost", "127.0.0.1", "::1"}:
            return None

    return raw


_INERT_EMBED_SCRIPT = """/* Embed loader unavailable: public publishing is disabled or FRONTEND_URL is not a valid HTTPS origin for this environment. */
"""

_EMBED_SCRIPT_TEMPLATE = """(function() {
  var scriptTag = document.currentScript || document.querySelector('script[data-assistant]');
  if (!scriptTag) return;
  var publicId = scriptTag.getAttribute('data-assistant');
  if (!publicId) return;

  var embedBase = __EMBED_BASE__;

  var container = document.createElement('div');
  container.id = 'mmaip-widget-container';
  container.style.position = 'fixed';
  container.style.bottom = '20px';
  container.style.right = '20px';
  container.style.zIndex = '999999';

  var iframe = document.createElement('iframe');
  iframe.src = embedBase + '/embed/' + encodeURIComponent(publicId);
  iframe.style.width = '400px';
  iframe.style.height = '620px';
  iframe.style.border = 'none';
  iframe.style.borderRadius = '16px';
  iframe.style.boxShadow = '0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)';
  iframe.style.display = 'block';
  iframe.setAttribute('allow', 'clipboard-write');

  container.appendChild(iframe);
  document.body.appendChild(container);
})();"""


@router.get("/assistants/{public_id}", response_model=PublicAssistantMetadataResponse)
async def get_public_assistant_metadata(
    public_id: str,
    db: AsyncSession = Depends(get_db),
) -> PublicAssistantMetadataResponse:
    """Fetch public metadata for an active published assistant."""
    if not public_publishing_enabled():
        logger.warning("Blocked public metadata request: PUBLIC_PUBLISHING_ENABLED is disabled")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assistant publication not found or expired",
        )

    svc = PublishingService(db, uuid.UUID(int=0))
    res = await svc.get_by_public_id(public_id)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assistant publication not found or expired",
        )

    pub, asst = res
    if not pub.is_active or pub.visibility != "PUBLIC":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This assistant is currently not available publicly",
        )

    return PublicAssistantMetadataResponse(
        public_id=pub.public_id,
        name=asst.name,
        description=asst.description,
        custom_greeting=pub.custom_greeting or f"Hello! I am {asst.name}. How can I help you today?",
        brand_color=pub.brand_color or "#0284c7",
        visibility=pub.visibility,
        citation_style=getattr(asst, "citation_style", "strict"),
    )


@router.post("/assistants/{public_id}/chat")
async def public_chat_stream(
    public_id: str,
    payload: PublicChatRequest,
    request: Request,
    origin: Optional[str] = Header(None, alias="Origin"),
    referer: Optional[str] = Header(None, alias="Referer"),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Stream chat responses for public web and embedded widget visitors."""
    # Global kill switch must reject before session creation, quota checks, or LLM calls.
    ensure_public_publishing_enabled("public chat request")

    # Rate limit before quota checks and anonymous session creation so rotating
    # session tokens cannot create unlimited sessions or provider calls.
    await enforce_rate_limit(
        "public_chat.message",
        client_identity(request),
        settings.RATE_LIMIT_PUBLIC_MESSAGE_PER_MINUTE,
        60,
    )

    svc = PublishingService(db, uuid.UUID(int=0))
    res = await svc.get_by_public_id(public_id)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assistant publication not found or revoked",
        )

    pub, asst = res
    if not pub.is_active or pub.visibility != "PUBLIC":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This assistant is not authorized for public external access",
        )

    # 1. Domain whitelist validation for embed contexts
    req_domain = origin or referer
    if not is_origin_allowed(req_domain, pub.allowed_domains):
        logger.warning(f"Public chat rejected: origin '{req_domain}' not permitted for pub_id={public_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requests from origin '{req_domain}' are not permitted for this embed widget",
        )

    # 2. Pre-invocation tenant quota check
    quota_svc = QuotaService(db, pub.tenant_id)
    await quota_svc.check_quota(estimated_tokens=len(payload.message.split()) * 3)

    # 3. Session isolation & conversation resolution
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    svc_scoped = PublishingService(db, pub.tenant_id)
    session_rec = await svc_scoped.get_or_create_public_session(
        publication_id=pub.id,
        session_token=payload.session_token,
        client_ip=client_ip,
        user_agent=user_agent,
    )

    # Find or initialize conversation deterministically bound to this public session
    conv = None
    if session_rec.conversation_id:
        conv_stmt = select(Conversation).where(
            Conversation.id == session_rec.conversation_id,
            Conversation.tenant_id == pub.tenant_id,
            Conversation.assistant_id == asst.id,
        )
        conv = (await db.execute(conv_stmt)).scalar_one_or_none()

    if not conv:
        conv = Conversation(
            id=uuid.uuid4(),
            tenant_id=pub.tenant_id,
            assistant_id=asst.id,
            user_id=None,
            title=f"Public: {payload.message[:30]}",
        )
        db.add(conv)
        await db.flush()
        session_rec.conversation_id = conv.id
        await db.commit()

    # 4. Stream response using unified AssistantRuntime with public scoping
    runtime = AssistantRuntime(
        session=db,
        tenant_id=pub.tenant_id,
        user_id=None,
        is_admin=False,
    )

    stream_gen = runtime.stream_chat(
        conversation_id=conv.id,
        user_message=payload.message,
        is_public=True,
        traffic_type="public",
    )

    return StreamingResponse(
        stream_gen,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Session-Token": session_rec.session_token,
        },
    )


@router.get("/embed/{public_id}/config")
@router.get("/assistants/{public_id}/embed-config")
async def get_embed_config(
    public_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Fetch configuration required by the embed widget."""
    if not public_publishing_enabled():
        logger.warning("Blocked embed config request: PUBLIC_PUBLISHING_ENABLED is disabled")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Embed configuration not found",
        )

    metadata = await get_public_assistant_metadata(public_id, db=db)
    frontend_base = settings.FRONTEND_URL.rstrip("/")
    backend_base = settings.BACKEND_URL.rstrip("/")
    return {
        "public_id": metadata.public_id,
        "name": metadata.name,
        "custom_greeting": metadata.custom_greeting,
        "brand_color": metadata.brand_color,
        "embed_url": f"{frontend_base}/embed/{metadata.public_id}",
        "script_url": f"{backend_base}/api/v1/public/embed.js",
    }


@router.get("/embed.js")
async def get_embed_script() -> Response:
    """Serve the embed loader, inert unless publishing and a safe origin are configured."""
    frontend_origin = _embed_frontend_origin()
    if frontend_origin is None:
        js_code = _INERT_EMBED_SCRIPT
    else:
        js_code = _EMBED_SCRIPT_TEMPLATE.replace("__EMBED_BASE__", json.dumps(frontend_origin))
    return Response(content=js_code, media_type="application/javascript")
