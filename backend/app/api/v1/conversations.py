"""Conversations and SSE Streaming Chat API Router."""

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import TenantContext, get_current_user, require_permission
from app.assistant_runtime.runtime import AssistantRuntime
from app.core.constants import PermissionName
from app.database.session import get_db
from app.models.conversation import Conversation, Message
from app.models.knowledge import DocumentChunk
from app.models.user import User
from app.schemas.assistant import (
    ConversationCreateRequest,
    ConversationResponse,
    ConversationUpdateRequest,
    MessageCitationResponse,
    MessageResponse,
    SendMessageRequest,
)
from app.schemas.conversation_attachment import (
    AttachmentPromotionRequest,
    AttachmentPromotionResponse,
    ConversationAttachmentResponse,
)
from app.schemas.feedback import (
    FeedbackListItemResponse,
    FeedbackStatusUpdateRequest,
    FeedbackTelemetryResponse,
    MessageFeedbackCreate,
    MessageFeedbackResponse,
)
from app.services.conversation_attachment_service import ConversationAttachmentService
from app.services.feedback_service import FeedbackService

router = APIRouter(prefix="/conversations", tags=["Conversations & Chat"])


@router.get("", response_model=list[ConversationResponse])
async def list_conversations(
    assistant_id: uuid.UUID | None = None,
    ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_READ.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ConversationResponse]:
    stmt = (
        select(Conversation)
        .where(
            Conversation.tenant_id == ctx.tenant.id,
            Conversation.user_id == current_user.id,
            Conversation.status == "ACTIVE",
        )
        .order_by(Conversation.updated_at.desc())
    )
    if assistant_id:
        stmt = stmt.where(Conversation.assistant_id == assistant_id)

    res = await db.execute(stmt)
    conversations = res.scalars().all()
    return [ConversationResponse.model_validate(c) for c in conversations]


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: ConversationCreateRequest,
    ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_READ.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    conv = Conversation(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant.id,
        user_id=current_user.id,
        assistant_id=payload.assistant_id,
        title=payload.title or "New Conversation",
        status="ACTIVE",
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return ConversationResponse.model_validate(conv)


@router.get("/feedback/stream", response_model=list[FeedbackListItemResponse])
async def list_feedback_stream(
    rating: str | None = None,
    category: str | None = None,
    assistant_id: uuid.UUID | None = None,
    feedback_status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    ctx: TenantContext = Depends(require_permission(PermissionName.AUDIT_READ.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[FeedbackListItemResponse]:
    """Admin endpoint to stream/list all message feedback items in this workspace."""
    svc = FeedbackService(
        session=db,
        tenant_id=ctx.tenant.id,
        user_id=current_user.id,
        is_admin=ctx.is_admin or ctx.is_owner,
    )
    items = await svc.list_feedback(
        rating=rating,
        category=category,
        assistant_id=assistant_id,
        feedback_status=feedback_status,
        limit=limit,
        offset=offset,
    )
    return [FeedbackListItemResponse.model_validate(it) for it in items]


@router.get("/feedback/telemetry", response_model=FeedbackTelemetryResponse)
async def get_feedback_telemetry(
    ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_READ.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FeedbackTelemetryResponse:
    """Get aggregated quality feedback telemetry for the workspace."""
    svc = FeedbackService(
        session=db,
        tenant_id=ctx.tenant.id,
        user_id=current_user.id,
        is_admin=ctx.is_admin or ctx.is_owner,
    )
    return await svc.get_feedback_telemetry()


@router.patch("/feedback/{feedback_id}/status", response_model=MessageFeedbackResponse)
async def update_feedback_status(
    feedback_id: uuid.UUID,
    payload: FeedbackStatusUpdateRequest,
    ctx: TenantContext = Depends(require_permission(PermissionName.AUDIT_READ.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageFeedbackResponse:
    """Update review status of a feedback record (admin only)."""
    svc = FeedbackService(
        session=db,
        tenant_id=ctx.tenant.id,
        user_id=current_user.id,
        is_admin=ctx.is_admin or ctx.is_owner,
    )
    fb = await svc.update_feedback_status(
        feedback_id=feedback_id,
        new_status=payload.status.value,
        admin_notes=payload.admin_notes,
    )
    return MessageFeedbackResponse.model_validate(fb)


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_READ.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.tenant_id == ctx.tenant.id,
    )
    conv = (await db.execute(stmt)).scalar_one_or_none()
    if not conv or (not ctx.is_admin and conv.user_id != current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return ConversationResponse.model_validate(conv)


@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: uuid.UUID,
    payload: ConversationUpdateRequest,
    ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_READ.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.tenant_id == ctx.tenant.id,
    )
    conv = (await db.execute(stmt)).scalar_one_or_none()
    if not conv or (not ctx.is_admin and conv.user_id != current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    if payload.title is not None:
        conv.title = payload.title.strip() or "Untitled Conversation"
    if payload.status is not None:
        conv.status = payload.status

    await db.commit()
    await db.refresh(conv)
    return ConversationResponse.model_validate(conv)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_READ.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.tenant_id == ctx.tenant.id,
    )
    conv = (await db.execute(stmt)).scalar_one_or_none()
    if not conv or (not ctx.is_admin and conv.user_id != current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    conv.status = "DELETED"
    await db.commit()


@router.get("/{conversation_id}/messages", response_model=list[MessageResponse])
async def list_messages(
    conversation_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_READ.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MessageResponse]:
    # Authorize conversation
    conv_stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.tenant_id == ctx.tenant.id,
    )
    conv = (await db.execute(conv_stmt)).scalar_one_or_none()
    if not conv or (not ctx.is_admin and conv.user_id != current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    # Fetch messages with citations
    msg_stmt = (
        select(Message)
        .options(selectinload(Message.citations))
        .where(
            Message.conversation_id == conversation_id,
            Message.tenant_id == ctx.tenant.id,
        )
        .order_by(Message.created_at.asc())
    )
    res = await db.execute(msg_stmt)
    messages = res.scalars().all()

    # Collect chunk IDs for real provenance lookup (page_number, genuine bounding_box)
    all_chunk_ids = [c.chunk_id for m in messages for c in m.citations if c.chunk_id]
    chunk_map: dict[uuid.UUID, DocumentChunk] = {}
    if all_chunk_ids:
        chunk_res = await db.execute(
            select(DocumentChunk).where(
                DocumentChunk.id.in_(all_chunk_ids),
                DocumentChunk.tenant_id == ctx.tenant.id,
            )
        )
        chunk_map = {chk.id: chk for chk in chunk_res.scalars().all()}

    output = []
    for m in messages:
        c_list = []
        for c in m.citations:
            has_http_prefix = c.document_name.startswith("http://") or c.document_name.startswith("https://")
            is_web = (c.chunk_id is None) and has_http_prefix
            web_url = c.document_name if has_http_prefix else None
            domain_name = None
            if web_url:
                from urllib.parse import urlparse
                domain_name = urlparse(web_url).hostname

            chk = chunk_map.get(c.chunk_id) if c.chunk_id else None
            actual_page = chk.page_number if (chk and chk.page_number is not None and not is_web) else None
            bbox = None
            if chk and chk.metadata_json and isinstance(chk.metadata_json, dict) and not is_web:
                raw_bbox = chk.metadata_json.get("bounding_box")
                if isinstance(raw_bbox, dict) and all(k in raw_bbox for k in ("page", "x", "y", "width", "height")):
                    bbox = {
                        "page": int(raw_bbox["page"]),
                        "x": float(raw_bbox["x"]),
                        "y": float(raw_bbox["y"]),
                        "width": float(raw_bbox["width"]),
                        "height": float(raw_bbox["height"]),
                    }

            c_list.append(
                MessageCitationResponse(
                    id=c.id,
                    citation_num=c.citation_num,
                    chunk_id=c.chunk_id,
                    document_name=c.document_name,
                    citation_text=c.citation_text,
                    snippet=c.citation_text,
                    page_number=actual_page,
                    bounding_box=bbox,
                    source_type="web" if is_web else "document",
                    source_url=web_url,
                    domain=domain_name,
                )
            )
        output.append(
            MessageResponse(
                id=m.id,
                conversation_id=m.conversation_id,
                sender_type=m.sender_type,
                content=m.content,
                token_count=m.token_count,
                citations=c_list,
                created_at=m.created_at,
            )
        )
    return output


@router.post("/{conversation_id}/messages/stream")
async def stream_message(
    conversation_id: uuid.UUID,
    payload: SendMessageRequest,
    ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_READ.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Send user message and receive streaming assistant response via Server-Sent Events (SSE)."""
    # 1. Authorize conversation
    conv_stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.tenant_id == ctx.tenant.id,
    )
    conv = (await db.execute(conv_stmt)).scalar_one_or_none()
    if not conv or (not ctx.is_admin and conv.user_id != current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    # 2. Initialize runtime
    runtime = AssistantRuntime(
        session=db,
        tenant_id=ctx.tenant.id,
        user_id=current_user.id,
        is_admin=ctx.is_admin,
        user_department_id=ctx.membership.department_id if ctx.membership else None,
    )

    # 3. Stream SSE response
    return StreamingResponse(
        runtime.stream_chat(conversation_id, payload.content),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Conversation Attachments API
# ---------------------------------------------------------------------------


@router.post(
    "/{conversation_id}/attachments",
    response_model=ConversationAttachmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_attachment(
    conversation_id: uuid.UUID,
    file: UploadFile = File(...),
    ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_READ.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationAttachmentResponse:
    """Upload a document directly into the chat conversation for scoped retrieval."""
    conv_stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.tenant_id == ctx.tenant.id,
    )
    conv = (await db.execute(conv_stmt)).scalar_one_or_none()
    if not conv or conv.status == "DELETED" or (not ctx.is_admin and conv.user_id != current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")

    svc = ConversationAttachmentService(db, ctx.tenant.id)
    try:
        att = await svc.upload_attachment(
            conversation_id=conversation_id,
            uploader_user_id=current_user.id,
            filename=file.filename or "uploaded_document",
            content=content,
            declared_content_type=file.content_type,
        )
        return ConversationAttachmentResponse.model_validate(att)
    except ValueError as v_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(v_err))


@router.get(
    "/{conversation_id}/attachments",
    response_model=list[ConversationAttachmentResponse],
)
async def list_attachments(
    conversation_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_READ.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ConversationAttachmentResponse]:
    """List all attachments in an authorized conversation."""
    conv_stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.tenant_id == ctx.tenant.id,
    )
    conv = (await db.execute(conv_stmt)).scalar_one_or_none()
    if not conv or conv.status == "DELETED" or (not ctx.is_admin and conv.user_id != current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    svc = ConversationAttachmentService(db, ctx.tenant.id)
    attachments = await svc.list_attachments(conversation_id)
    return [ConversationAttachmentResponse.model_validate(a) for a in attachments]


@router.get(
    "/{conversation_id}/attachments/{attachment_id}",
    response_model=ConversationAttachmentResponse,
)
async def get_attachment(
    conversation_id: uuid.UUID,
    attachment_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_READ.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationAttachmentResponse:
    """Retrieve details of a specific conversation attachment."""
    conv_stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.tenant_id == ctx.tenant.id,
    )
    conv = (await db.execute(conv_stmt)).scalar_one_or_none()
    if not conv or conv.status == "DELETED" or (not ctx.is_admin and conv.user_id != current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    svc = ConversationAttachmentService(db, ctx.tenant.id)
    att = await svc.get_attachment(conversation_id, attachment_id)
    if not att:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    return ConversationAttachmentResponse.model_validate(att)


@router.get(
    "/{conversation_id}/attachments/{attachment_id}/download",
)
async def download_attachment(
    conversation_id: uuid.UUID,
    attachment_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_READ.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Download the raw binary file for an authorized conversation attachment."""
    conv_stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.tenant_id == ctx.tenant.id,
    )
    conv = (await db.execute(conv_stmt)).scalar_one_or_none()
    if not conv or conv.status == "DELETED" or (not ctx.is_admin and conv.user_id != current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    svc = ConversationAttachmentService(db, ctx.tenant.id)
    try:
        att, data = await svc.get_attachment_bytes(conversation_id, attachment_id)
        return Response(
            content=data,
            media_type=att.content_type,
            headers={"Content-Disposition": f'attachment; filename="{att.filename}"'},
        )
    except ValueError as v_err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(v_err))


@router.delete(
    "/{conversation_id}/attachments/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_attachment(
    conversation_id: uuid.UUID,
    attachment_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_READ.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an attachment and its chunks from the conversation."""
    conv_stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.tenant_id == ctx.tenant.id,
    )
    conv = (await db.execute(conv_stmt)).scalar_one_or_none()
    if not conv or conv.status == "DELETED" or (not ctx.is_admin and conv.user_id != current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    svc = ConversationAttachmentService(db, ctx.tenant.id)
    deleted = await svc.delete_attachment(conversation_id, attachment_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")


@router.post(
    "/{conversation_id}/attachments/{attachment_id}/promote",
    response_model=AttachmentPromotionResponse,
)
async def promote_attachment(
    conversation_id: uuid.UUID,
    attachment_id: uuid.UUID,
    payload: AttachmentPromotionRequest,
    ctx: TenantContext = Depends(require_permission(PermissionName.DOCUMENT_UPLOAD.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AttachmentPromotionResponse:
    """Promote a conversation attachment into a permanent Knowledge Base document."""
    conv_stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.tenant_id == ctx.tenant.id,
    )
    conv = (await db.execute(conv_stmt)).scalar_one_or_none()
    if not conv or conv.status == "DELETED" or (not ctx.is_admin and conv.user_id != current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    target_kb = payload.knowledge_base_id or payload.target_knowledge_base_id
    if not target_kb:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either knowledge_base_id or target_knowledge_base_id must be provided",
        )

    svc = ConversationAttachmentService(db, ctx.tenant.id)
    try:
        att, doc = await svc.promote_to_knowledge_base(
            conversation_id=conversation_id,
            attachment_id=attachment_id,
            target_kb_id=target_kb,
            actor_user_id=current_user.id,
            title=payload.title,
        )
        return AttachmentPromotionResponse(
            attachment_id=att.id,
            knowledge_base_id=target_kb,
            document_id=doc.id,
            status="PROMOTED",
            message=f"Attachment '{att.filename}' promoted successfully to Knowledge Base.",
            promoted_at=att.promoted_at,
        )
    except ValueError as v_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(v_err))


@router.post(
    "/{conversation_id}/messages/{message_id}/feedback",
    response_model=MessageFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_message_feedback(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    payload: MessageFeedbackCreate,
    ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_READ.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageFeedbackResponse:
    """Submit or update user rating and feedback on an assistant message."""
    svc = FeedbackService(
        session=db,
        tenant_id=ctx.tenant.id,
        user_id=current_user.id,
        is_admin=ctx.is_admin or ctx.is_owner,
    )
    fb = await svc.submit_feedback(
        conversation_id=conversation_id,
        message_id=message_id,
        payload=payload,
    )
    return MessageFeedbackResponse.model_validate(fb)


@router.get(
    "/{conversation_id}/messages/{message_id}/feedback",
    response_model=MessageFeedbackResponse | None,
)
async def get_message_feedback(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_READ.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageFeedbackResponse | None:
    """Retrieve the current user's feedback for a specific assistant message."""
    svc = FeedbackService(
        session=db,
        tenant_id=ctx.tenant.id,
        user_id=current_user.id,
        is_admin=ctx.is_admin or ctx.is_owner,
    )
    fb = await svc.get_message_feedback(
        conversation_id=conversation_id,
        message_id=message_id,
    )
    if not fb:
        return None
    return MessageFeedbackResponse.model_validate(fb)

