"""Assistant Publishing Service managing distribution lifecycle, domain validation, and public session state."""

import json
import logging
import secrets
import urllib.parse
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assistant import Assistant, AssistantVersion
from app.models.publishing import AssistantPublication, PublicChatSession
from app.schemas.publishing import AssistantPublicationCreate, AssistantPublicationUpdate

logger = logging.getLogger("mmaip.services.publishing")


def generate_opaque_public_id() -> str:
    """Generate a clean, high-entropy 128-bit unguessable public identifier.

    Uses 16 cryptographically secure random bytes (32 hexadecimal characters).
    """
    return f"pub_{secrets.token_hex(16)}"


def _parse_allowed_domains(allowed_domains_raw: Any) -> Optional[list[str]]:
    """Decode stored allowlist configuration; None signals a malformed value."""
    if allowed_domains_raw is None:
        return []
    if isinstance(allowed_domains_raw, str):
        raw = allowed_domains_raw.strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError, ValueError):
            return None
        if isinstance(parsed, str):
            parsed = [parsed]
        if not isinstance(parsed, list):
            return None
        return [str(item) for item in parsed]
    if isinstance(allowed_domains_raw, (list, tuple, set)):
        return [str(item) for item in allowed_domains_raw]
    return None


def _parse_domain_entry(entry: str) -> Optional[tuple[str, Optional[int]]]:
    """Parse a configured domain entry into its hostname and optional port."""
    value = entry.strip().lower()
    if not value:
        return None
    candidate = value if "://" in value else f"//{value}"
    try:
        parsed = urllib.parse.urlparse(candidate)
        host = (parsed.hostname or "").strip(".").lower()
        port = parsed.port
    except (TypeError, ValueError):
        return None
    if not host:
        return None
    return host, port


def _hostname_matches(host: str, pattern: str) -> bool:
    if pattern.startswith("*."):
        suffix = pattern[1:]
        return len(host) > len(suffix) and host.endswith(suffix)
    return host == pattern


def is_origin_allowed(origin_or_referer: Optional[str], allowed_domains_raw: Optional[str]) -> bool:
    """Validate a request origin/referer against the configured embed allowlist.

    An empty configuration (or an explicit "*" entry) is unrestricted. With a
    restricted list, a missing or malformed origin is denied. Entries match an
    exact hostname; subdomains are accepted only for "*.example.com" patterns,
    which never match the bare domain. Ports are ignored unless the entry
    specifies one; http and https are both accepted.
    """
    domains = _parse_allowed_domains(allowed_domains_raw)
    if domains is None:
        return False
    if not domains:
        return True

    normalized = [entry.strip() for entry in domains if entry and entry.strip()]
    if "*" in normalized:
        return True

    if not origin_or_referer:
        return False

    try:
        parsed = urllib.parse.urlparse(origin_or_referer.strip())
    except (TypeError, ValueError):
        return False

    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        return False

    host = (parsed.hostname or "").strip(".").lower()
    if not host:
        return False

    try:
        port = parsed.port
    except ValueError:
        return False
    if port is None:
        port = 443 if scheme == "https" else 80

    for entry in normalized:
        parsed_entry = _parse_domain_entry(entry)
        if not parsed_entry:
            continue
        entry_host, entry_port = parsed_entry
        if not _hostname_matches(host, entry_host):
            continue
        if entry_port is not None and entry_port != port:
            continue
        return True

    return False


class PublishingService:
    """Service managing assistant public visibility, embed configurations, and public sessions."""

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID):
        self.session = session
        self.tenant_id = tenant_id

    async def get_publication(self, assistant_id: uuid.UUID) -> Optional[AssistantPublication]:
        """Fetch publication record for assistant."""
        stmt = select(AssistantPublication).where(
            AssistantPublication.tenant_id == self.tenant_id,
            AssistantPublication.assistant_id == assistant_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_or_create_publication(self, assistant_id: uuid.UUID) -> AssistantPublication:
        """Fetch existing publication record or initialize a private default record."""
        pub = await self.get_publication(assistant_id)
        if not pub:
            pub = AssistantPublication(
                id=uuid.uuid4(),
                tenant_id=self.tenant_id,
                assistant_id=assistant_id,
                public_id=generate_opaque_public_id(),
                visibility="PRIVATE",
                is_active=False,
                allowed_domains=json.dumps(["*"]),
                brand_color="#0284c7",
            )
            self.session.add(pub)
            await self.session.commit()
            await self.session.refresh(pub)
        return pub

    async def publish_assistant(
        self,
        assistant_id: uuid.UUID,
        payload: AssistantPublicationCreate,
        user_id: Optional[uuid.UUID] = None,
    ) -> AssistantPublication:
        """Publish an assistant, setting public identifier and active state."""
        pub = await self.get_or_create_publication(assistant_id)

        pub.visibility = payload.visibility.upper()
        pub.is_active = True
        pub.allowed_domains = json.dumps(payload.allowed_domains or ["*"])
        pub.custom_greeting = payload.custom_greeting
        pub.brand_color = payload.brand_color or "#0284c7"
        pub.created_by = user_id
        pub.published_at = datetime.now(UTC)
        pub.updated_at = datetime.now(UTC)

        if payload.published_version_id:
            pub.published_version_id = payload.published_version_id
        else:
            # Snapshot latest configuration version
            v_stmt = (
                select(AssistantVersion.id)
                .where(AssistantVersion.assistant_id == assistant_id)
                .order_by(AssistantVersion.version_num.desc())
                .limit(1)
            )
            latest_v_id = (await self.session.execute(v_stmt)).scalar_one_or_none()
            if latest_v_id:
                pub.published_version_id = latest_v_id

        await self.session.commit()
        await self.session.refresh(pub)
        logger.info(f"Assistant {assistant_id} published with public_id={pub.public_id}, visibility={pub.visibility}")
        return pub

    async def unpublish_assistant(self, assistant_id: uuid.UUID) -> AssistantPublication:
        """Deactivate assistant publication immediately."""
        pub = await self.get_or_create_publication(assistant_id)
        pub.is_active = False
        pub.updated_at = datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(pub)
        logger.info(f"Assistant {assistant_id} unpublished (public_id={pub.public_id})")
        return pub

    async def update_publication(
        self,
        assistant_id: uuid.UUID,
        payload: AssistantPublicationUpdate,
    ) -> AssistantPublication:
        """Update publication properties."""
        pub = await self.get_or_create_publication(assistant_id)

        if payload.visibility is not None:
            pub.visibility = payload.visibility.upper()
        if payload.is_active is not None:
            pub.is_active = payload.is_active
        if payload.allowed_domains is not None:
            pub.allowed_domains = json.dumps(payload.allowed_domains)
        if payload.custom_greeting is not None:
            pub.custom_greeting = payload.custom_greeting
        if payload.brand_color is not None:
            pub.brand_color = payload.brand_color

        pub.updated_at = datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(pub)
        return pub

    async def get_by_public_id(self, public_id: str) -> Optional[tuple[AssistantPublication, Assistant]]:
        """Resolve publication and underlying assistant by public opaque ID."""
        stmt = (
            select(AssistantPublication, Assistant)
            .join(Assistant, AssistantPublication.assistant_id == Assistant.id)
            .where(AssistantPublication.public_id == public_id.strip())
        )
        res = (await self.session.execute(stmt)).first()
        if not res:
            return None
        return res[0], res[1]

    async def get_or_create_public_session(
        self,
        publication_id: uuid.UUID,
        session_token: Optional[str] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        conversation_id: Optional[uuid.UUID] = None,
    ) -> PublicChatSession:
        """Resolve or initialize an unguessable session for public chat visitors."""
        now = datetime.now(UTC)
        if session_token:
            stmt = select(PublicChatSession).where(
                PublicChatSession.publication_id == publication_id,
                PublicChatSession.session_token == session_token.strip(),
            )
            existing = (await self.session.execute(stmt)).scalar_one_or_none()
            if existing:
                exp = existing.expires_at if existing.expires_at.tzinfo else existing.expires_at.replace(tzinfo=UTC)
                if exp <= now:
                    logger.warning(f"Public chat session {existing.id} expired at {existing.expires_at}")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Public chat session has expired. Please start a new session.",
                    )
                existing.updated_at = now
                if conversation_id and not existing.conversation_id:
                    existing.conversation_id = conversation_id
                await self.session.commit()
                return existing

        new_session = PublicChatSession(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            publication_id=publication_id,
            conversation_id=conversation_id,
            session_token=session_token.strip() if session_token else f"sess_{secrets.token_urlsafe(24)}",
            client_ip_hash=secrets.token_hex(16) if client_ip else None,
            user_agent=user_agent[:250] if user_agent else None,
            expires_at=now + timedelta(days=7),
        )
        self.session.add(new_session)
        await self.session.commit()
        await self.session.refresh(new_session)
        return new_session

    async def bind_session_conversation(
        self,
        session_id: uuid.UUID,
        conversation_id: uuid.UUID,
    ) -> None:
        """Bind a specific conversation thread to an anonymous public session."""
        stmt = select(PublicChatSession).where(PublicChatSession.id == session_id)
        session_rec = (await self.session.execute(stmt)).scalar_one_or_none()
        if session_rec:
            session_rec.conversation_id = conversation_id
            session_rec.updated_at = datetime.now(UTC)
            await self.session.commit()
