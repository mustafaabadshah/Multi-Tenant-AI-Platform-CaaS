"""Invitation issuance and acceptance support for invitation-based onboarding."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invitation import Invitation

INVITATION_EXPIRY_DAYS = 7


def generate_invitation_token() -> str:
    """Return a high-entropy raw invitation token (never persisted)."""
    return secrets.token_urlsafe(32)


def hash_invitation_token(raw_token: str) -> str:
    """Return the SHA-256 hex digest stored for an invitation token."""
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()


class InvitationService:
    """Creates pending workspace invitations and resolves them by raw token."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_invitation(
        self,
        tenant_id: uuid.UUID,
        email: str,
        role_id: uuid.UUID,
        department_id: uuid.UUID | None = None,
        invited_by_id: uuid.UUID | None = None,
    ) -> tuple[Invitation, str]:
        """Create a pending invitation and return it together with the raw token."""
        raw_token = generate_invitation_token()
        invitation = Invitation(
            tenant_id=tenant_id,
            email=email.lower().strip(),
            role_id=role_id,
            department_id=department_id,
            invited_by_id=invited_by_id,
            token=hash_invitation_token(raw_token),
            expires_at=datetime.now(UTC) + timedelta(days=INVITATION_EXPIRY_DAYS),
            accepted_at=None,
            is_cancelled=False,
        )
        self.session.add(invitation)
        await self.session.flush()
        return invitation, raw_token

    async def get_by_raw_token(self, raw_token: str) -> Invitation | None:
        """Resolve an active, uncancelled invitation by hashing the supplied raw token."""
        if not raw_token or not raw_token.strip():
            return None
        stmt = select(Invitation).where(
            Invitation.token == hash_invitation_token(raw_token),
            Invitation.is_cancelled.is_(False),
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def list_pending_invitations(self, tenant_id: uuid.UUID) -> list[Invitation]:
        """List active pending (unaccepted, unexpired, uncancelled) invitations for a tenant."""
        now = datetime.now(UTC)
        stmt = (
            select(Invitation)
            .where(
                Invitation.tenant_id == tenant_id,
                Invitation.accepted_at.is_(None),
                Invitation.is_cancelled.is_(False),
                Invitation.expires_at > now,
            )
            .order_by(Invitation.created_at.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def cancel_invitation(self, invitation_id: uuid.UUID, tenant_id: uuid.UUID) -> Invitation | None:
        """Mark an invitation cancelled within a tenant."""
        stmt = select(Invitation).where(
            Invitation.id == invitation_id,
            Invitation.tenant_id == tenant_id,
            Invitation.is_cancelled.is_(False),
            Invitation.accepted_at.is_(None),
        )
        invitation = (await self.session.execute(stmt)).scalar_one_or_none()
        if not invitation:
            return None
        invitation.is_cancelled = True
        await self.session.flush()
        return invitation

