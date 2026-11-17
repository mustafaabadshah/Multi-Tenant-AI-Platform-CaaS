"""Conversation-Scoped Web Context Store for Follow-up Questions and Citation Tracking (M27)."""

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class WebPageContext:
    """Structured in-memory representation of an extracted web page within a conversation."""
    canonical_url: str
    original_url: str
    title: str
    extracted_text: str
    hostname: str
    content_type: str = "text/html"
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonical_url": self.canonical_url,
            "original_url": self.original_url,
            "title": self.title,
            "extracted_text": self.extracted_text,
            "hostname": self.hostname,
            "content_type": self.content_type,
            "retrieved_at": self.retrieved_at.isoformat(),
        }


# In-memory conversation-scoped web context store:
# str(conversation_id) -> list of WebPageContext
_CONVERSATION_WEB_STORE: dict[str, list[WebPageContext]] = {}
_MAX_SOURCES_PER_CONVERSATION = 5
_DEFAULT_TTL_SECONDS = 3600  # 1 hour


class ConversationWebContextStore:
    """Manages temporary web context associated with an active conversation."""

    def __init__(self, ttl_seconds: int = _DEFAULT_TTL_SECONDS, max_pages_per_conversation: int = _MAX_SOURCES_PER_CONVERSATION):
        self.ttl_seconds = ttl_seconds
        self.max_pages = max_pages_per_conversation

    def store_page(self, conversation_id: uuid.UUID | str, page: WebPageContext):
        """Add or update an extracted web page in the conversation context."""
        key = str(conversation_id)
        pages = _CONVERSATION_WEB_STORE.setdefault(key, [])

        now = datetime.now(timezone.utc)
        # Clean expired
        pages[:] = [
            p for p in pages
            if (now - p.retrieved_at).total_seconds() < self.ttl_seconds
        ]

        # Deduplicate on canonical URL
        pages[:] = [p for p in pages if p.canonical_url != page.canonical_url]
        pages.insert(0, page)

        if len(pages) > self.max_pages:
            pages.pop()

    def get_pages(self, conversation_id: uuid.UUID | str) -> list[WebPageContext]:
        """Retrieve active cached web pages for this conversation."""
        key = str(conversation_id)
        now = datetime.now(timezone.utc)
        pages = _CONVERSATION_WEB_STORE.get(key, [])
        valid_pages = [
            p for p in pages
            if (now - p.retrieved_at).total_seconds() < self.ttl_seconds
        ]
        _CONVERSATION_WEB_STORE[key] = valid_pages
        return list(valid_pages)

    def get_page_by_url(self, conversation_id: uuid.UUID | str, url: str) -> Optional[WebPageContext]:
        """Retrieve a specific cached page by canonical or original URL."""
        pages = self.get_pages(conversation_id)
        for p in pages:
            if p.canonical_url == url or p.original_url == url:
                return p
        return None

    def clear(self, conversation_id: uuid.UUID | str):
        """Clear all cached pages for a conversation."""
        _CONVERSATION_WEB_STORE.pop(str(conversation_id), None)

    # Backwards-compatible classmethods
    @classmethod
    def add_source(cls, tenant_id: uuid.UUID, conversation_id: uuid.UUID, web_source: dict[str, Any]):
        store = get_web_context_store()
        page = WebPageContext(
            canonical_url=web_source.get("canonical_url", ""),
            original_url=web_source.get("original_url", web_source.get("canonical_url", "")),
            title=web_source.get("title", ""),
            extracted_text=web_source.get("extracted_text", web_source.get("text", "")),
            hostname=web_source.get("hostname", ""),
            content_type=web_source.get("content_type", "text/html"),
        )
        store.store_page(conversation_id, page)

    @classmethod
    def get_sources(cls, tenant_id: uuid.UUID, conversation_id: uuid.UUID) -> list[dict[str, Any]]:
        store = get_web_context_store()
        return [p.to_dict() for p in store.get_pages(conversation_id)]

    @classmethod
    def clear_conversation(cls, tenant_id: uuid.UUID, conversation_id: uuid.UUID):
        store = get_web_context_store()
        store.clear(conversation_id)


_GLOBAL_STORE = ConversationWebContextStore()


def get_web_context_store() -> ConversationWebContextStore:
    return _GLOBAL_STORE
