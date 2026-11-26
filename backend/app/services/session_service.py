"""Durable authentication session service for refresh rotation, replay detection, and session revocation."""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.constants import UserStatus
from app.core.security import decode_token, generate_session_token, hash_session_token
from app.models.session import AuthSession
from app.models.user import User

logger = logging.getLogger("mmaip.services.session")


class SessionService:
    """Manages durable user authentication sessions."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_session(
        self,
        user_id: uuid.UUID,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> tuple[AuthSession, str]:
        """Create a new server-side session and return it along with the raw refresh token."""
        raw_token = generate_session_token()
        token_hash = hash_session_token(raw_token)
        now = datetime.now(UTC)
        expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        auth_session = AuthSession(
            user_id=user_id,
            refresh_token_hash=token_hash,
            previous_refresh_token_hash=None,
            session_family_id=uuid.uuid4(),
            user_agent=user_agent[:500] if user_agent else None,
            ip_address=ip_address[:100] if ip_address else None,
            is_revoked=False,
            last_used_at=now,
            expires_at=expires_at,
        )
        self.session.add(auth_session)
        await self.session.commit()
        await self.session.refresh(auth_session)
        return auth_session, raw_token

    async def rotate_session(
        self,
        raw_refresh_token: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> tuple[AuthSession, str]:
        """Atomically rotate a refresh token, detecting reuse/replay attacks."""
        if not raw_refresh_token or not raw_refresh_token.strip():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token required",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token_hash = hash_session_token(raw_refresh_token)
        now = datetime.now(UTC)

        # 1. Check if token matches a previously rotated token (REPLAY ATTACK!)
        replay_stmt = select(AuthSession).where(AuthSession.previous_refresh_token_hash == token_hash)
        replay_res = await self.session.execute(replay_stmt)
        compromised_session = replay_res.scalar_one_or_none()

        if compromised_session:
            logger.warning(
                "Security alert: Refresh token replay detected for session %s, family %s, user %s",
                compromised_session.id,
                compromised_session.session_family_id,
                compromised_session.user_id,
            )
            # Revoke entire session family immediately
            revoke_stmt = (
                update(AuthSession)
                .where(AuthSession.session_family_id == compromised_session.session_family_id)
                .values(
                    is_revoked=True,
                    revoked_at=now,
                    revoked_reason="REPLAY_DETECTED",
                )
            )
            await self.session.execute(revoke_stmt)
            await self.session.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Security violation: Refresh token reuse detected. All sessions in this chain have been revoked.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 2. Look up session by active refresh_token_hash
        stmt = select(AuthSession).where(AuthSession.refresh_token_hash == token_hash)
        res = await self.session.execute(stmt)
        auth_session = res.scalar_one_or_none()

        # Backward compatibility for legacy stateless JWT tokens
        if not auth_session:
            decoded = decode_token(raw_refresh_token)
            if decoded and decoded.get("type") == "refresh":
                user_id_str = decoded.get("sub")
                try:
                    user_id = uuid.UUID(user_id_str)
                    user_stmt = select(User).where(User.id == user_id)
                    user = (await self.session.execute(user_stmt)).scalar_one_or_none()
                    if user and user.status == UserStatus.ACTIVE.value:
                        logger.info("Migrated legacy stateless refresh token to durable session for user %s", user_id)
                        return await self.create_session(user_id, user_agent, ip_address)
                except Exception:
                    pass

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 3. Check revocation status
        if auth_session.is_revoked:
            logger.info("Rejected attempt to use revoked session %s", auth_session.id)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 4. Check expiration
        expires_at = auth_session.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at < now:
            auth_session.is_revoked = True
            auth_session.revoked_at = now
            auth_session.revoked_reason = "EXPIRED"
            await self.session.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 5. Check user status
        user_stmt = select(User).where(User.id == auth_session.user_id)
        user = (await self.session.execute(user_stmt)).scalar_one_or_none()
        if not user or user.status != UserStatus.ACTIVE.value:
            auth_session.is_revoked = True
            auth_session.revoked_at = now
            auth_session.revoked_reason = "USER_INACTIVE"
            await self.session.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive or suspended",
            )

        # 6. Perform one-time rotation
        new_raw_token = generate_session_token()
        new_token_hash = hash_session_token(new_raw_token)

        auth_session.previous_refresh_token_hash = auth_session.refresh_token_hash
        auth_session.refresh_token_hash = new_token_hash
        auth_session.last_used_at = now
        auth_session.expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        if user_agent:
            auth_session.user_agent = user_agent[:500]
        if ip_address:
            auth_session.ip_address = ip_address[:100]

        await self.session.commit()
        await self.session.refresh(auth_session)
        return auth_session, new_raw_token

    async def revoke_session(
        self,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        reason: str = "LOGOUT",
    ) -> bool:
        """Revoke a specific user session."""
        now = datetime.now(UTC)
        stmt = (
            update(AuthSession)
            .where(AuthSession.id == session_id, AuthSession.user_id == user_id)
            .values(
                is_revoked=True,
                revoked_at=now,
                revoked_reason=reason,
            )
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0

    async def revoke_all_user_sessions(
        self,
        user_id: uuid.UUID,
        reason: str = "LOGOUT_ALL",
    ) -> int:
        """Revoke all active sessions for a user (e.g., password change or account compromise)."""
        now = datetime.now(UTC)
        stmt = (
            update(AuthSession)
            .where(AuthSession.user_id == user_id, AuthSession.is_revoked.is_(False))
            .values(
                is_revoked=True,
                revoked_at=now,
                revoked_reason=reason,
            )
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount

    async def is_session_valid(self, session_id: uuid.UUID) -> bool:
        """Verify whether a session exists, is unrevoked, and is not expired."""
        now = datetime.now(UTC)
        stmt = select(AuthSession).where(AuthSession.id == session_id)
        res = await self.session.execute(stmt)
        auth_session = res.scalar_one_or_none()
        if not auth_session or auth_session.is_revoked:
            return False
        expires_at = auth_session.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        return expires_at > now
