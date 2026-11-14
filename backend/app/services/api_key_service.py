"""Developer API Key Service managing cryptographic key generation, SHA-256 hashing, and scope enforcement."""

import hashlib
import json
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.publishing import APIKey
from app.models.tenant import Tenant
from app.schemas.publishing import APIKeyCreate

logger = logging.getLogger("mmaip.services.api_key")

DEFAULT_SCOPES = ["assistant:read", "assistant:chat"]
VALID_SCOPES = {"assistant:read", "assistant:chat", "assistant:eval", "knowledge:read"}
KEY_PREFIX = "mmaip_live_"


def developer_api_enabled() -> bool:
    """Return whether the developer API is enabled (read dynamically)."""
    return bool(settings.DEVELOPER_API_ENABLED)


def ensure_developer_api_enabled() -> None:
    """Reject developer API operations when the global kill switch is disabled."""
    if developer_api_enabled():
        return
    logger.warning("Blocked developer API request: DEVELOPER_API_ENABLED is disabled")
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Developer API is disabled",
    )


def hash_api_key(raw_key: str) -> str:
    """Compute deterministic SHA-256 hex digest of secret API key."""
    return hashlib.sha256(raw_key.strip().encode("utf-8")).hexdigest()


class APIKeyService:
    """Service managing developer API keys and Bearer authentication."""

    def __init__(self, session: AsyncSession, tenant_id: Optional[uuid.UUID] = None):
        self.session = session
        self.tenant_id = tenant_id

    async def generate_api_key(
        self,
        payload: APIKeyCreate,
        user_id: Optional[uuid.UUID] = None,
    ) -> tuple[APIKey, str]:
        """Generate a cryptographically secure API key and persist its SHA-256 hash.

        Returns (APIKey model record, raw_key string).
        The raw_key is only returned ONCE to the caller.
        """
        ensure_developer_api_enabled()
        if not self.tenant_id:
            raise ValueError("Tenant ID is required to generate an API key")

        # Validate requested scopes
        for s in payload.scopes:
            if s not in VALID_SCOPES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid scope '{s}'. Supported: {list(VALID_SCOPES)}",
                )

        secret_token = secrets.token_urlsafe(32)
        raw_key = f"{KEY_PREFIX}{secret_token}"
        key_hash = hash_api_key(raw_key)

        now = datetime.now(UTC)
        expires_at = now + timedelta(days=payload.expires_days) if payload.expires_days else None

        key_record = APIKey(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            user_id=user_id,
            assistant_id=payload.assistant_id,
            name=payload.name.strip(),
            key_prefix=KEY_PREFIX,
            key_hash=key_hash,
            scopes=json.dumps(payload.scopes or DEFAULT_SCOPES),
            expires_at=expires_at,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        self.session.add(key_record)
        await self.session.commit()
        await self.session.refresh(key_record)

        logger.info(f"Generated API key '{key_record.name}' ({key_record.id}) for tenant {self.tenant_id}")
        return key_record, raw_key

    async def verify_api_key(
        self,
        raw_key: str,
        required_scope: Optional[str] = None,
        target_assistant_id: Optional[uuid.UUID] = None,
    ) -> tuple[APIKey, Tenant]:
        """Authenticate an incoming Bearer API key, checking expiration, scopes, and optional assistant restriction.

        Returns (APIKey, Tenant).
        """
        ensure_developer_api_enabled()
        cleaned_key = raw_key.strip()
        if not cleaned_key.startswith(KEY_PREFIX):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key format. Expected 'mmaip_live_...' prefix.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        key_hash = hash_api_key(cleaned_key)
        now = datetime.now(UTC)

        stmt = (
            select(APIKey, Tenant)
            .join(Tenant, APIKey.tenant_id == Tenant.id)
            .where(
                APIKey.key_hash == key_hash,
                APIKey.is_active.is_(True),
            )
        )
        res = (await self.session.execute(stmt)).first()
        if not res:
            logger.warning("API key verification failed: hash not found or key revoked")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked API key.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        api_key, tenant = res[0], res[1]

        if api_key.expires_at:
            exp = api_key.expires_at if api_key.expires_at.tzinfo else api_key.expires_at.replace(tzinfo=timezone.utc)
            if exp < now:
                logger.warning(f"API key {api_key.id} expired at {api_key.expires_at}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="API key has expired.",
                    headers={"WWW-Authenticate": "Bearer"},
                )

        try:
            scopes = json.loads(api_key.scopes) if isinstance(api_key.scopes, str) else api_key.scopes
        except Exception:
            scopes = DEFAULT_SCOPES

        if required_scope and required_scope not in scopes:
            logger.warning(f"API key {api_key.id} lacks required scope '{required_scope}'")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"API key lacks required permission scope '{required_scope}'. Key scopes: {scopes}",
            )

        # Enforce assistant-level restriction if configured
        if api_key.assistant_id and target_assistant_id and api_key.assistant_id != target_assistant_id:
            logger.warning(f"API key {api_key.id} restricted to assistant {api_key.assistant_id}, cannot access {target_assistant_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"API key is restricted to assistant '{api_key.assistant_id}'.",
            )

        # Update last_used_at timestamp
        api_key.last_used_at = now
        await self.session.commit()

        return api_key, tenant

    async def list_keys(self) -> list[APIKey]:
        """List active and revoked API keys for the current tenant."""
        if not self.tenant_id:
            return []
        stmt = (
            select(APIKey)
            .where(APIKey.tenant_id == self.tenant_id)
            .order_by(APIKey.created_at.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def revoke_key(self, key_id: uuid.UUID) -> bool:
        """Immediately revoke an API key."""
        stmt = (
            select(APIKey)
            .where(
                APIKey.id == key_id,
                APIKey.tenant_id == self.tenant_id,
            )
        )
        key = (await self.session.execute(stmt)).scalar_one_or_none()
        if not key:
            return False

        key.is_active = False
        key.updated_at = datetime.now(UTC)
        await self.session.commit()
        logger.info(f"Revoked API key {key_id} for tenant {self.tenant_id}")
        return True

    async def delete_key(self, key_id: uuid.UUID) -> bool:
        """Permanently delete an API key record."""
        stmt = delete(APIKey).where(
            APIKey.id == key_id,
            APIKey.tenant_id == self.tenant_id,
        )
        res = await self.session.execute(stmt)
        await self.session.commit()
        return res.rowcount > 0
