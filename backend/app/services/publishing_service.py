"""Assistant Publishing Service managing distribution lifecycle, domain validation, and public session state."""

import json
import logging
import secrets
import urllib.parse
import uuid
from datetime import UTC, datetime, timedelta
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assistant import Assistant, AssistantVersion
from app.models.publishing import AssistantPublication, PublicChatSession
from app.schemas.publishing import AssistantPublicationCreate, AssistantPublicationUpdate

logger = logging.getLogger("mmaip.services.publishing")


def generate_opaque_public_id() -> str:
    """Generate a clean, unguessable public identifier for published assistants."""
    return f"pub_{secrets.token_hex(8)}"


def is_origin_allowed(origin_or_referer: Optional[str], allowed_domains_raw: Optional[str]) -> bool:
    """Validate whether request origin or referer hostname matches configured allowed domains."""
    if not allowed_domains_raw:
        return True

    try:
        domains = json.loads(allowed_domains_raw) if isinstance(allowed_domains_raw, str) else allowed_domains_raw
    except Exception:
        domains = ["*"]

    if "*" in domains or not domains:
        return True

    if not origin_or_referer:
        # Non-browser or direct navigation
        return True

    try:
        parsed = urllib.parse.urlparse(origin_or_referer)
        req_host = (parsed.hostname or "").lower()
    except Exception:
        return False

    for pattern in domains:
        p = pattern.strip().lower()
        if p == "*":
            return True
        if p.startswith("http://") or p.startswith("https://"):
            try:
                p = (urllib.parse.urlparse(p).hostname or "").lower()
            except Exception:
                pass
        if req_host == p or req_host.endswith(f".{p}"):
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
    ) -> PublicChatSession:
        """Resolve or initialize an unguessable session for public chat visitors."""
        now = datetime.now(UTC)
        if session_token:
            stmt = select(PublicChatSession).where(
                PublicChatSession.publication_id == publication_id,
                PublicChatSession.session_token == session_token.strip(),
                PublicChatSession.expires_at > now,
            )
            existing = (await self.session.execute(stmt)).scalar_one_or_none()
            if existing:
                existing.updated_at = now
                await self.session.commit()
                return existing

        new_session = PublicChatSession(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            publication_id=publication_id,
            session_token=f"sess_{secrets.token_urlsafe(24)}",
            client_ip_hash=secrets.token_hex(16) if client_ip else None,
            user_agent=user_agent[:250] if user_agent else None,
            expires_at=now + timedelta(days=7),
        )
        self.session.add(new_session)
        await self.session.commit()
        await self.session.refresh(new_session)
        return new_session
