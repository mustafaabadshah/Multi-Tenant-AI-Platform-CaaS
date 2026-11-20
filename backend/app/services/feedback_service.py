"""Service layer for in-app assistant message feedback and quality telemetry."""

import uuid
from datetime import UTC, datetime
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.administration import AuditLog
from app.models.assistant import Assistant
from app.models.conversation import Conversation, Message, MessageFeedback
from app.models.user import User
from app.schemas.feedback import (
    FeedbackCategory,
    FeedbackRating,
    FeedbackStatus,
    FeedbackTelemetryResponse,
    MessageFeedbackCreate,
    MessageFeedbackUpdate,
)


class FeedbackService:
    """Manages creation, lifecycle, and telemetry of message feedback with strict tenant isolation."""

    def __init__(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        is_admin: bool = False,
    ):
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.is_admin = is_admin

    async def submit_feedback(
        self,
        conversation_id: uuid.UUID,
        message_id: uuid.UUID,
        payload: MessageFeedbackCreate,
    ) -> MessageFeedback:
        """Create or update user feedback for an assistant message with idempotency."""
        # 1. Verify conversation belongs to active tenant and is not deleted
        conv_stmt = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.tenant_id == self.tenant_id,
            Conversation.status != "DELETED",
        )
        conv = (await self.session.execute(conv_stmt)).scalar_one_or_none()
        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found or unauthorized",
            )

        # 2. Verify message exists, belongs to this conversation and tenant, and is from assistant
        msg_stmt = select(Message).where(
            Message.id == message_id,
            Message.conversation_id == conversation_id,
            Message.tenant_id == self.tenant_id,
        )
        msg = (await self.session.execute(msg_stmt)).scalar_one_or_none()
        if not msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found in this conversation",
            )

        if msg.sender_type.lower() != "assistant":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Feedback can only be submitted on assistant messages",
            )

        now = datetime.now(UTC)

        # 3. Check for existing feedback by this user on this message
        existing_stmt = select(MessageFeedback).where(
            MessageFeedback.message_id == message_id,
            MessageFeedback.user_id == self.user_id,
            MessageFeedback.tenant_id == self.tenant_id,
        )
        existing = (await self.session.execute(existing_stmt)).scalar_one_or_none()

        if existing:
            # Update existing feedback
            existing.rating = payload.rating.value
            existing.category = payload.category.value if payload.category else None
            existing.comment = payload.comment
            existing.updated_at = now
            feedback = existing
            action = "MESSAGE_FEEDBACK_UPDATED"
        else:
            # Create new feedback record
            feedback = MessageFeedback(
                id=uuid.uuid4(),
                tenant_id=self.tenant_id,
                conversation_id=conversation_id,
                message_id=message_id,
                assistant_id=conv.assistant_id,
                user_id=self.user_id,
                rating=payload.rating.value,
                category=payload.category.value if payload.category else None,
                comment=payload.comment,
                status=FeedbackStatus.NEW.value,
                created_at=now,
                updated_at=now,
            )
            self.session.add(feedback)
            action = "MESSAGE_FEEDBACK_SUBMITTED"

        # Record audit log
        audit = AuditLog(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            actor_id=self.user_id,
            action=action,
            resource_type="message_feedback",
            resource_id=feedback.id,
            details={
                "conversation_id": str(conversation_id),
                "message_id": str(message_id),
                "assistant_id": str(conv.assistant_id),
                "rating": payload.rating.value,
                "category": payload.category.value if payload.category else None,
                "has_comment": bool(payload.comment),
            },
            created_at=now,
        )
        self.session.add(audit)
        await self.session.commit()
        await self.session.refresh(feedback)
        return feedback

    async def get_message_feedback(
        self,
        conversation_id: uuid.UUID,
        message_id: uuid.UUID,
    ) -> Optional[MessageFeedback]:
        """Fetch feedback submitted by the current user on a specific message."""
        stmt = select(MessageFeedback).where(
            MessageFeedback.conversation_id == conversation_id,
            MessageFeedback.message_id == message_id,
            MessageFeedback.user_id == self.user_id,
            MessageFeedback.tenant_id == self.tenant_id,
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_feedback(
        self,
        rating: Optional[str] = None,
        category: Optional[str] = None,
        assistant_id: Optional[uuid.UUID] = None,
        feedback_status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List feedback items for workspace admins with metadata joins and tenant scoping."""
        if not self.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin permissions required to review feedback logs",
            )

        stmt = (
            select(MessageFeedback, Assistant.name, User.email, Message.content)
            .join(Assistant, MessageFeedback.assistant_id == Assistant.id, isouter=True)
            .join(User, MessageFeedback.user_id == User.id, isouter=True)
            .join(Message, MessageFeedback.message_id == Message.id, isouter=True)
            .where(MessageFeedback.tenant_id == self.tenant_id)
            .order_by(MessageFeedback.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        if rating:
            stmt = stmt.where(MessageFeedback.rating == rating)
        if category:
            stmt = stmt.where(MessageFeedback.category == category)
        if assistant_id:
            stmt = stmt.where(MessageFeedback.assistant_id == assistant_id)
        if feedback_status:
            stmt = stmt.where(MessageFeedback.status == feedback_status)

        res = await self.session.execute(stmt)
        rows = res.all()

        results = []
        for fb, asst_name, user_email, msg_content in rows:
            snippet = None
            if msg_content:
                snippet = msg_content[:150] + ("..." if len(msg_content) > 150 else "")
            results.append({
                "id": fb.id,
                "tenant_id": fb.tenant_id,
                "conversation_id": fb.conversation_id,
                "message_id": fb.message_id,
                "assistant_id": fb.assistant_id,
                "assistant_name": asst_name or "Unknown Assistant",
                "user_id": fb.user_id,
                "user_email": user_email or "Unknown User",
                "rating": fb.rating,
                "category": fb.category,
                "comment": fb.comment,
                "status": fb.status,
                "admin_notes": fb.admin_notes,
                "message_content_snippet": snippet,
                "created_at": fb.created_at,
                "updated_at": fb.updated_at,
            })
        return results

    async def update_feedback_status(
        self,
        feedback_id: uuid.UUID,
        new_status: str,
        admin_notes: Optional[str] = None,
    ) -> MessageFeedback:
        """Update review lifecycle state of a feedback record."""
        if not self.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin permissions required to update feedback status",
            )

        stmt = select(MessageFeedback).where(
            MessageFeedback.id == feedback_id,
            MessageFeedback.tenant_id == self.tenant_id,
        )
        fb = (await self.session.execute(stmt)).scalar_one_or_none()
        if not fb:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Feedback record not found",
            )

        now = datetime.now(UTC)
        fb.status = new_status
        if admin_notes is not None:
            fb.admin_notes = admin_notes
        fb.updated_at = now

        audit = AuditLog(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            actor_id=self.user_id,
            action="MESSAGE_FEEDBACK_STATUS_UPDATED",
            resource_type="message_feedback",
            resource_id=fb.id,
            details={
                "new_status": new_status,
                "has_admin_notes": bool(admin_notes),
            },
            created_at=now,
        )
        self.session.add(audit)
        await self.session.commit()
        await self.session.refresh(fb)
        return fb

    async def get_feedback_telemetry(self) -> FeedbackTelemetryResponse:
        """Calculate mathematically accurate feedback telemetry with sparse sample detection."""
        # Positive and negative counts
        rating_stmt = (
            select(
                MessageFeedback.rating,
                func.count(MessageFeedback.id),
            )
            .where(MessageFeedback.tenant_id == self.tenant_id)
            .group_by(MessageFeedback.rating)
        )
        r_res = await self.session.execute(rating_stmt)
        rating_counts = dict(r_res.all())

        pos_count = rating_counts.get(FeedbackRating.THUMBS_UP.value, 0)
        neg_count = rating_counts.get(FeedbackRating.THUMBS_DOWN.value, 0)
        total_count = pos_count + neg_count

        pct_positive = None
        if total_count > 0:
            pct_positive = round((pos_count / total_count) * 100.0, 1)

        # Category breakdown
        cat_stmt = (
            select(
                MessageFeedback.category,
                func.count(MessageFeedback.id),
            )
            .where(
                MessageFeedback.tenant_id == self.tenant_id,
                MessageFeedback.category.is_not(None),
            )
            .group_by(MessageFeedback.category)
        )
        c_res = await self.session.execute(cat_stmt)
        cat_counts = {cat: count for cat, count in c_res.all() if cat}

        # Status breakdown
        status_stmt = (
            select(
                MessageFeedback.status,
                func.count(MessageFeedback.id),
            )
            .where(MessageFeedback.tenant_id == self.tenant_id)
            .group_by(MessageFeedback.status)
        )
        s_res = await self.session.execute(status_stmt)
        status_counts = dict(s_res.all())

        return FeedbackTelemetryResponse(
            total_feedback_count=total_count,
            positive_count=pos_count,
            negative_count=neg_count,
            positive_percentage=pct_positive,
            category_breakdown=cat_counts,
            is_sparse_sample=total_count < 5,
            status_breakdown=status_counts,
        )
