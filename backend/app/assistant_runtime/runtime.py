"""Assistant Runtime Orchestrator: Conversational RAG with SSE Streaming and Citation Provenance."""

import json
import logging
import re
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assistant_runtime.context import build_rag_context
from app.llm import LLMConfig, get_llm_registry
from app.models.assistant import Assistant, AssistantKnowledgeBase
from app.models.conversation import Conversation, Message, MessageCitation
from app.models.knowledge import KnowledgeBase
from app.retrieval.service import RetrievalService
from app.vectorstores.base import VectorSearchResult

logger = logging.getLogger("mmaip.assistant_runtime")


def format_sse(event: str, data: dict[str, Any]) -> str:
    """Format an SSE frame according to the W3C spec."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def sanitize_error_message(err_msg: str) -> str:
    """Redact sensitive credentials, API keys, and secret tokens from user-facing error messages."""
    sanitized = re.sub(r"(sk-[a-zA-Z0-9_\-]{8,})", "[REDACTED_API_KEY]", err_msg)
    sanitized = re.sub(r"(Bearer\s+)[a-zA-Z0-9_\-\.]{8,}", r"\1[REDACTED_TOKEN]", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"TEST_SECRET_[A-Z0-9_]+", "[REDACTED_SECRET]", sanitized)
    sanitized = re.sub(r"(password|pwd|secret|api_key|token)\s*=\s*['\"]?[^'\"\s]+['\"]?", r"\1=[REDACTED]", sanitized, flags=re.IGNORECASE)
    return sanitized


class AssistantRuntime:
    """Runtime orchestrating conversational RAG with strict tenant authorization and SSE streaming."""

    def __init__(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        is_admin: bool = False,
        user_department_id: Optional[uuid.UUID] = None,
    ):
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.is_admin = is_admin
        self.user_department_id = user_department_id

    async def stream_chat(
        self,
        conversation_id: uuid.UUID,
        user_message: str,
    ) -> AsyncIterator[str]:
        """Stream an assistant response with citations via Server-Sent Events."""
        start_time = time.perf_counter()

        # 1. Fetch & authorize Conversation
        conv_stmt = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.tenant_id == self.tenant_id,
        )
        conv = (await self.session.execute(conv_stmt)).scalar_one_or_none()
        if not conv or (not self.is_admin and conv.user_id != self.user_id):
            yield format_sse("message_error", {"error": "Conversation not found or unauthorized"})
            return

        # 2. Fetch Assistant
        asst_stmt = select(Assistant).where(
            Assistant.id == conv.assistant_id,
            Assistant.tenant_id == self.tenant_id,
        )
        asst = (await self.session.execute(asst_stmt)).scalar_one_or_none()
        if not asst:
            yield format_sse("message_error", {"error": "Assistant not found or unauthorized"})
            return

        yield format_sse(
            "message_start",
            {
                "conversation_id": str(conversation_id),
                "assistant_id": str(asst.id),
                "assistant_name": asst.name,
            },
        )

        # 3. Retrieve conversation history (up to last 10 messages)
        hist_stmt = (
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.tenant_id == self.tenant_id,
            )
            .order_by(Message.created_at.desc())
            .limit(10)
        )
        hist_rows = (await self.session.execute(hist_stmt)).scalars().all()
        conversation_history = [
            {"role": m.sender_type, "content": m.content}
            for m in reversed(hist_rows)
        ]

        # 4. Revalidate & resolve connected Knowledge Bases
        kb_assoc_stmt = select(AssistantKnowledgeBase).where(
            AssistantKnowledgeBase.assistant_id == asst.id,
            AssistantKnowledgeBase.tenant_id == self.tenant_id,
        )
        kb_assocs = (await self.session.execute(kb_assoc_stmt)).scalars().all()
        candidate_kb_ids = [a.knowledge_base_id for a in kb_assocs]

        retrieved_results: list[VectorSearchResult] = []
        citations_data: list[dict[str, Any]] = []


        if candidate_kb_ids:
            yield format_sse(
                "retrieval_start",
                {"connected_kb_count": len(candidate_kb_ids)},
            )

            # Execution-time check: Filter to active KBs belonging to this tenant
            valid_kb_stmt = select(KnowledgeBase.id).where(
                KnowledgeBase.id.in_(candidate_kb_ids),
                KnowledgeBase.tenant_id == self.tenant_id,
                KnowledgeBase.status == "ACTIVE",
            )
            authorized_kb_ids = (await self.session.execute(valid_kb_stmt)).scalars().all()

            if authorized_kb_ids:
                retrieval_svc = RetrievalService(
                    session=self.session,
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                    is_admin=self.is_admin,
                    user_department_id=self.user_department_id,
                )
                search_resp = await retrieval_svc.search(
                    query=user_message,
                    knowledge_base_ids=list(authorized_kb_ids),
                    mode=asst.retrieval_mode or "hybrid",
                    top_k=asst.top_k or 5,
                )
                retrieved_results = search_resp.results

        # 5. Assemble Context & Citations with 4-Tier Trust Hierarchy
        messages, citations_data = build_rag_context(
            system_prompt=asst.system_prompt,
            conversation_history=conversation_history,
            current_user_message=user_message,
            retrieved_results=retrieved_results,
            max_context_tokens=asst.max_tokens * 3,
            audience_level=getattr(asst, "audience_level", "general"),
            response_style=getattr(asst, "response_style", "balanced"),
            uncertainty_behavior=getattr(asst, "uncertainty_behavior", "admit"),
            citation_style=getattr(asst, "citation_style", "strict"),
        )

        yield format_sse(
            "retrieval_complete",
            {
                "citation_count": len(citations_data),
                "citations": citations_data,
            },
        )

        # 6. Stream tokens via LLM Provider
        llm_registry = get_llm_registry()
        provider = llm_registry.get_provider(asst.llm_provider)

        llm_config = LLMConfig(
            provider=asst.llm_provider,
            model=asst.default_model or "auto",
            temperature=asst.temperature,
            max_tokens=asst.max_tokens,
        )

        full_content_chunks: list[str] = []
        try:
            async for chunk in provider.generate_stream(messages, llm_config):
                if chunk.content_delta:
                    full_content_chunks.append(chunk.content_delta)
                    yield format_sse("token", {"delta": chunk.content_delta})
        except Exception as e:
            logger.exception("LLM generation stream failed")
            safe_err = sanitize_error_message(str(e))
            yield format_sse("message_error", {"error": f"LLM generation failed: {safe_err}"})
            return

        final_content = "".join(full_content_chunks)
        if not final_content.strip():
            logger.warning("LLM provider returned empty response stream")
            yield format_sse("message_error", {"error": "LLM generation failed: Empty response stream received"})
            return

        # 7. Persist User Message, Assistant Message, and Citations in Database
        user_msg = Message(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            conversation_id=conversation_id,
            sender_type="user",
            content=user_message,
            token_count=len(user_message.split()),
        )
        assistant_msg = Message(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            conversation_id=conversation_id,
            sender_type="assistant",
            content=final_content,
            token_count=len(final_content.split()),
        )
        self.session.add_all([user_msg, assistant_msg])
        await self.session.flush()

        for c in citations_data:
            citation_obj = MessageCitation(
                id=uuid.uuid4(),
                tenant_id=self.tenant_id,
                message_id=assistant_msg.id,
                chunk_id=uuid.UUID(c["chunk_id"]) if c.get("chunk_id") else None,
                document_name=c["document_name"],
                citation_num=c["citation_num"],
                citation_text=c["snippet"],
            )
            self.session.add(citation_obj)

        await self.session.commit()

        duration = round((time.perf_counter() - start_time) * 1000, 2)
        yield format_sse(
            "usage",
            {
                "input_tokens": sum(len(m.content.split()) for m in messages),
                "output_tokens": len(final_content.split()),
                "duration_ms": duration,
                "model": asst.default_model,
            },
        )
        yield format_sse(
            "message_complete",
            {
                "message_id": str(assistant_msg.id),
                "conversation_id": str(conversation_id),
                "status": "COMPLETED",
            },
        )

    async def stream_preview(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        audience_level: str = "general",
        response_style: str = "balanced",
        uncertainty_behavior: str = "admit",
        citation_style: str = "strict",
        llm_provider: str = "omniroute",
        default_model: str = "auto",
        temperature: float = 0.7,
        max_tokens: int = 1024,
        retrieval_mode: str = "hybrid",
        top_k: int = 5,
        knowledge_base_ids: Optional[list[uuid.UUID]] = None,
    ) -> AsyncIterator[str]:
        """Stream a live test preview using real retrieval and LLM inference without persisting conversations."""
        start_time = time.perf_counter()

        yield format_sse("message_start", {"preview": True, "model": default_model})

        retrieved_results: list[VectorSearchResult] = []
        citations_data: list[dict[str, Any]] = []

        candidate_kb_ids = knowledge_base_ids or []
        if candidate_kb_ids:
            yield format_sse("retrieval_start", {"connected_kb_count": len(candidate_kb_ids)})

            valid_kb_stmt = select(KnowledgeBase.id).where(
                KnowledgeBase.id.in_(candidate_kb_ids),
                KnowledgeBase.tenant_id == self.tenant_id,
                KnowledgeBase.status == "ACTIVE",
            )
            authorized_kb_ids = (await self.session.execute(valid_kb_stmt)).scalars().all()

            if authorized_kb_ids:
                retrieval_svc = RetrievalService(
                    session=self.session,
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                    is_admin=self.is_admin,
                    user_department_id=self.user_department_id,
                )
                search_resp = await retrieval_svc.search(
                    query=user_message,
                    knowledge_base_ids=list(authorized_kb_ids),
                    mode=retrieval_mode or "hybrid",
                    top_k=top_k or 5,
                )
                retrieved_results = search_resp.results

        messages, citations_data = build_rag_context(
            system_prompt=system_prompt,
            conversation_history=[],
            current_user_message=user_message,
            retrieved_results=retrieved_results,
            max_context_tokens=max_tokens * 3,
            audience_level=audience_level,
            response_style=response_style,
            uncertainty_behavior=uncertainty_behavior,
            citation_style=citation_style,
        )

        yield format_sse(
            "retrieval_complete",
            {
                "citation_count": len(citations_data),
                "citations": citations_data,
            },
        )

        llm_registry = get_llm_registry()
        try:
            provider = llm_registry.get_provider(llm_provider)
        except Exception:
            provider = llm_registry.get_provider("omniroute")

        llm_config = LLMConfig(
            provider=llm_provider,
            model=default_model or "auto",
            temperature=temperature,
            max_tokens=max_tokens,
        )

        full_content_chunks: list[str] = []
        try:
            async for chunk in provider.generate_stream(messages, llm_config):
                if chunk.content_delta:
                    full_content_chunks.append(chunk.content_delta)
                    yield format_sse("token", {"delta": chunk.content_delta})
        except Exception as e:
            logger.exception("Preview LLM generation stream failed")
            safe_err = sanitize_error_message(str(e))
            yield format_sse("message_error", {"error": f"LLM generation failed: {safe_err}"})
            return

        final_content = "".join(full_content_chunks)
        if not final_content.strip():
            yield format_sse("message_error", {"error": "LLM generation failed: Empty response stream received"})
            return

        duration = round((time.perf_counter() - start_time) * 1000, 2)
        yield format_sse(
            "usage",
            {
                "input_tokens": sum(len(m.content.split()) for m in messages),
                "output_tokens": len(final_content.split()),
                "duration_ms": duration,
                "model": default_model,
            },
        )
        yield format_sse(
            "message_complete",
            {
                "status": "COMPLETED",
                "preview": True,
            },
        )
