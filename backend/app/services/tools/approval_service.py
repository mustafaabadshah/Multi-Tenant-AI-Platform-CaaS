"""Human-in-the-Loop Tool Approval Service."""

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mcp import ToolApproval


class ToolApprovalService:
    """Manages human-in-the-loop pending approval tokens for high-risk / mutating operations."""

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID):
        self.session = session
        self.tenant_id = tenant_id

    async def request_approval(
        self,
        conversation_id: uuid.UUID,
        assistant_id: uuid.UUID,
        user_id: uuid.UUID,
        tool_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        expires_in_minutes: int = 15,
    ) -> ToolApproval:
        """Create a single-use pending approval token stored in PostgreSQL."""
        token = f"appr_{secrets.token_urlsafe(32)}"
        expires_at = datetime.now(UTC) + timedelta(minutes=expires_in_minutes)

        approval = ToolApproval(
            tenant_id=self.tenant_id,
            conversation_id=conversation_id,
            assistant_id=assistant_id,
            user_id=user_id,
            tool_id=tool_id,
            tool_name=tool_name,
            arguments=arguments,
            status="PENDING",
            approval_token=token,
            expires_at=expires_at,
        )
        self.session.add(approval)
        await self.session.commit()
        await self.session.refresh(approval)
        return approval

    async def get_approval(self, approval_id: uuid.UUID) -> Optional[ToolApproval]:
        """Fetch an approval by ID scoped strictly to active tenant."""
        stmt = select(ToolApproval).where(
            ToolApproval.id == approval_id,
            ToolApproval.tenant_id == self.tenant_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def approve_and_consume(
        self,
        approval_id: uuid.UUID,
        user_id: uuid.UUID,
        token: Optional[str] = None,
    ) -> ToolApproval:
        """Atomically approve and consume a pending approval token. Rejects replays and expired requests."""
        approval = await self.get_approval(approval_id)
        if not approval:
            raise ValueError("Approval request not found in active workspace.")

        # Check tenant and user boundary
        if approval.user_id != user_id:
            raise PermissionError("Only the requesting user or tenant administrator can approve this tool execution.")

        # Check token if provided
        if token and approval.approval_token != token:
            raise PermissionError("Invalid approval token provided.")

        # Check status
        if approval.status == "APPROVED" or approval.status == "CONSUMED":
            raise ValueError("This tool action has already been approved and executed (replay prevented).")
        if approval.status == "DENIED":
            raise ValueError("This tool action was previously denied.")

        # Check expiration
        now = datetime.now(UTC)
        exp = approval.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=UTC)
        if exp < now:
            approval.status = "EXPIRED"
            await self.session.commit()
            raise ValueError("Approval request has expired.")


        # Atomically transition to APPROVED
        approval.status = "APPROVED"
        await self.session.commit()
        await self.session.refresh(approval)
        return approval

    async def mark_consumed(self, approval_id: uuid.UUID) -> None:
        """Mark an approved token as consumed so it cannot be re-executed."""
        approval = await self.get_approval(approval_id)
        if approval:
            approval.status = "CONSUMED"
            await self.session.commit()
            await self.session.refresh(approval)


    async def deny(self, approval_id: uuid.UUID, user_id: uuid.UUID) -> ToolApproval:
        """Explicitly deny a pending tool action."""
        approval = await self.get_approval(approval_id)
        if not approval:
            raise ValueError("Approval request not found in active workspace.")

        if approval.status != "PENDING":
            raise ValueError(f"Cannot deny approval with status '{approval.status}'.")

        approval.status = "DENIED"
        await self.session.commit()
        await self.session.refresh(approval)
        return approval

    async def list_pending_for_conversation(self, conversation_id: uuid.UUID) -> list[ToolApproval]:
        """List active pending approvals for a conversation."""
        now = datetime.now(UTC)
        stmt = (
            select(ToolApproval)
            .where(
                ToolApproval.tenant_id == self.tenant_id,
                ToolApproval.conversation_id == conversation_id,
                ToolApproval.status == "PENDING",
                ToolApproval.expires_at > now,
            )
            .order_by(ToolApproval.created_at.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())
