"""API Router for Private Beta Cohort Operations and User Telemetry."""

import uuid
from datetime import UTC, datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, get_current_user, get_db, require_permission
from app.core.constants import PermissionName
from app.models.conversation import Message, MessageFeedback
from app.models.invitation import Invitation
from app.models.membership import TenantMembership
from app.models.role import Role
from app.models.user import User

router = APIRouter(prefix="/beta", tags=["Private Beta Cohort Operations"])


class BetaInvitationItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role_name: str
    token_preview: str
    is_cancelled: bool
    is_expired: bool
    is_accepted: bool
    created_at: datetime
    expires_at: datetime
    accepted_at: Optional[datetime] = None


class BetaMemberItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    email: str
    full_name: str
    role_name: str
    status: str
    joined_at: datetime
    message_count: int
    feedback_count: int


class BetaCohortSummary(BaseModel):
    total_invited: int
    pending_invitations: int
    accepted_invitations: int
    active_beta_members: int
    total_conversation_turns: int
    total_feedback_count: int
    positive_feedback_count: int
    negative_feedback_count: int
    satisfaction_rate: Optional[float] = None
    is_sparse_sample: bool


class BetaCohortResponse(BaseModel):
    summary: BetaCohortSummary
    invitations: list[BetaInvitationItem]
    members: list[BetaMemberItem]


@router.get("/cohort", response_model=BetaCohortResponse)
async def get_beta_cohort(
    ctx: TenantContext = Depends(require_permission(PermissionName.MEMBER_READ.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BetaCohortResponse:
    """Retrieve private beta cohort telemetry, invitation states, and member activity."""
    tenant_id = ctx.tenant.id
    now = datetime.now(UTC)

    # 1. Fetch Invitations for active tenant
    inv_stmt = (
        select(Invitation, Role.name)
        .join(Role, Invitation.role_id == Role.id)
        .where(Invitation.tenant_id == tenant_id)
        .order_by(Invitation.created_at.desc())
    )
    inv_rows = (await db.execute(inv_stmt)).all()

    invitation_items: list[BetaInvitationItem] = []
    total_invited = len(inv_rows)
    pending_count = 0
    accepted_count = 0

    for inv, role_name in inv_rows:
        is_acc = inv.accepted_at is not None
        exp = inv.expires_at if inv.expires_at.tzinfo is not None else inv.expires_at.replace(tzinfo=UTC)
        is_exp = exp < now and not is_acc
        if is_acc:
            accepted_count += 1
        elif not inv.is_cancelled and not is_exp:
            pending_count += 1

        token_preview = inv.token[:6] + "..." if len(inv.token) > 6 else inv.token
        invitation_items.append(
            BetaInvitationItem(
                id=inv.id,
                email=inv.email,
                role_name=role_name,
                token_preview=token_preview,
                is_cancelled=inv.is_cancelled,
                is_expired=is_exp,
                is_accepted=is_acc,
                created_at=inv.created_at,
                expires_at=inv.expires_at,
                accepted_at=inv.accepted_at,
            )
        )

    # 2. Fetch Active Beta Members
    mem_stmt = (
        select(TenantMembership, User, Role.name)
        .join(User, TenantMembership.user_id == User.id)
        .join(Role, TenantMembership.role_id == Role.id)
        .where(TenantMembership.tenant_id == tenant_id)
        .order_by(TenantMembership.created_at.desc())
    )
    mem_rows = (await db.execute(mem_stmt)).all()

    member_items: list[BetaMemberItem] = []
    for mem, usr, role_name in mem_rows:
        # Count user messages in this tenant
        msg_cnt_stmt = select(func.count(Message.id)).where(
            Message.tenant_id == tenant_id,
            Message.sender_type == "user",
        )
        # Count feedback given by this user
        fb_cnt_stmt = select(func.count(MessageFeedback.id)).where(
            MessageFeedback.tenant_id == tenant_id,
            MessageFeedback.user_id == usr.id,
        )
        msg_cnt = int((await db.execute(msg_cnt_stmt)).scalar_one())
        fb_cnt = int((await db.execute(fb_cnt_stmt)).scalar_one())

        member_items.append(
            BetaMemberItem(
                user_id=usr.id,
                email=usr.email,
                full_name=usr.full_name,
                role_name=role_name,
                status=mem.status,
                joined_at=mem.created_at,
                message_count=msg_cnt,
                feedback_count=fb_cnt,
            )
        )

    # 3. Overall Feedback & Message Turns
    total_turns_stmt = select(func.count(Message.id)).where(
        Message.tenant_id == tenant_id,
        Message.sender_type == "user",
    )
    total_turns = int((await db.execute(total_turns_stmt)).scalar_one())

    pos_stmt = select(func.count(MessageFeedback.id)).where(
        MessageFeedback.tenant_id == tenant_id,
        MessageFeedback.rating == "THUMBS_UP",
    )
    pos_count = int((await db.execute(pos_stmt)).scalar_one())

    neg_stmt = select(func.count(MessageFeedback.id)).where(
        MessageFeedback.tenant_id == tenant_id,
        MessageFeedback.rating == "THUMBS_DOWN",
    )
    neg_count = int((await db.execute(neg_stmt)).scalar_one())

    total_fb = pos_count + neg_count
    sat_rate = round((pos_count / total_fb) * 100.0, 1) if total_fb > 0 else None

    summary = BetaCohortSummary(
        total_invited=total_invited,
        pending_invitations=pending_count,
        accepted_invitations=accepted_count,
        active_beta_members=len(member_items),
        total_conversation_turns=total_turns,
        total_feedback_count=total_fb,
        positive_feedback_count=pos_count,
        negative_feedback_count=neg_count,
        satisfaction_rate=sat_rate,
        is_sparse_sample=total_fb < 5,
    )

    return BetaCohortResponse(
        summary=summary,
        invitations=invitation_items,
        members=member_items,
    )
