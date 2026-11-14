"""Conversations and SSE Streaming Chat API Router."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import TenantContext, get_current_user, require_permission
from app.assistant_runtime.runtime import AssistantRuntime
from app.core.constants import PermissionName
from app.database.session import get_db
from app.models.conversation import Conversation, Message
from app.models.user import User
from app.schemas.assistant import (
    ConversationCreateRequest,
    ConversationResponse,
    ConversationUpdateRequest,
    MessageCitationResponse,
    MessageResponse,
    SendMessageRequest,
)

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

    output = []
    for m in messages:
        c_list = [
            MessageCitationResponse(
                id=c.id,
                citation_num=c.citation_num,
                chunk_id=c.chunk_id,
                document_name=c.document_name,
                citation_text=c.citation_text,
                snippet=c.citation_text,
                page_number=1,
                bounding_box={
                    "page": 1,
                    "x": 72.0,
                    "y": 90.0 + (((c.citation_num - 1) % 7) * 85.0),
                    "width": 468.0,
                    "height": 65.0,
                },
            )
            for c in m.citations
        ]
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
