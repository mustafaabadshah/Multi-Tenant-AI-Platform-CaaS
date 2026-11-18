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

from app.assistant_runtime.context import build_rag_context, normalize_markdown
from app.llm import LLMConfig, get_llm_registry
from app.llm.base import LLMMessage
from app.models.assistant import Assistant, AssistantKnowledgeBase
from app.models.conversation import Conversation, Message, MessageCitation
from app.models.knowledge import KnowledgeBase
from app.models.mcp import ToolInvocationLog
from app.observability.policy import ObservabilityPolicyService
from app.observability.tracer import get_tracer
from app.retrieval.service import RetrievalService
from app.services.byok_vault import BYOKVaultService
from app.services.quota_service import QuotaService
from app.services.tools.approval_service import ToolApprovalService
from app.services.tools.registry import ToolRegistryService
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
        is_public: bool = False,
        traffic_type: str = "internal",
        expected_assistant_id: Optional[uuid.UUID] = None,
        require_conversation_owner: bool = False,
    ) -> AsyncIterator[str]:
        """Stream an assistant response with citations via Server-Sent Events."""
        start_time = time.perf_counter()

        # 1. Fetch & authorize Conversation
        conv_stmt = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.tenant_id == self.tenant_id,
        )
        conv = (await self.session.execute(conv_stmt)).scalar_one_or_none()
        owner_check_required = require_conversation_owner or not self.is_admin
        if (
            not conv
            or (expected_assistant_id is not None and conv.assistant_id != expected_assistant_id)
            or (not is_public and owner_check_required and conv.user_id != self.user_id)
        ):
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

        policy_svc = ObservabilityPolicyService(self.session, self.tenant_id)
        policy = await policy_svc.get_policy()

        tracer = get_tracer()
        trace = tracer.start_trace(
            tenant_id=self.tenant_id,
            assistant_id=asst.id,
            assistant_name=asst.name,
            conversation_id=conversation_id,
            traffic_type=traffic_type,
        )
        trace.provider = asst.llm_provider
        trace.model = asst.default_model or "auto"
        trace.retrieval_mode = asst.retrieval_mode or "hybrid"
        if policy.capture_mode == "REDACTED_PREVIEW":
            trace.set_previews(user_input=user_message, max_length=policy.max_preview_length)

        yield format_sse(
            "message_start",
            {
                "conversation_id": str(conversation_id),
                "assistant_id": str(asst.id),
                "assistant_name": asst.name,
                "trace_id": trace.trace_id,
            },
        )

        # Auto-update conversation title if default, and immediately persist user message to history
        conv_stmt = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.tenant_id == self.tenant_id,
        )
        conv_res = await self.session.execute(conv_stmt)
        conv = conv_res.scalar_one_or_none()
        if conv and (not conv.title or conv.title in ("New Conversation", "New Chat")):
            clean_title = user_message.strip().replace("\n", " ")
            conv.title = clean_title[:45] + ("..." if len(clean_title) > 45 else "")

        user_msg = Message(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            conversation_id=conversation_id,
            sender_type="user",
            content=user_message,
            token_count=len(user_message.split()),
        )
        self.session.add(user_msg)
        await self.session.commit()

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
        explicit_web_chunks: list[VectorSearchResult] = []
        web_preflight_triggered = False
        web_preflight_notice: str | None = None

        # 4a. Deterministic Explicit Web URL Preflight (M28.1 & M28.2)
        # If user explicitly asks to read or query a public URL, fetch it immediately to guarantee grounded context.
        # Strips code blocks and blockquotes so URLs in code snippets or quotes never trigger unwanted egress.
        if not is_public:
            clean_msg_for_url = re.sub(r"```[\s\S]*?```", "", user_message)
            clean_msg_for_url = re.sub(r"`[^`]*`", "", clean_msg_for_url)
            clean_msg_for_url = re.sub(r"^>.*$", "", clean_msg_for_url, flags=re.MULTILINE)
            url_matches = re.findall(r"https?://[^\s<>'\"{}|\\^`]+", clean_msg_for_url)
            if url_matches:
                target_url = url_matches[0].rstrip(".,;!?)]}")
                lower_msg = user_message.lower()
                read_keywords = (
                    "read", "explain", "summarize", "what is", "check", "browse",
                    "analyze", "content", "page", "knowledge", "using tool", "tool",
                    "look at", "visit", "tell me about", "from this url", "fetch",
                )
                is_explicit_read = (
                    any(kw in lower_msg for kw in read_keywords)
                    or len(user_message.strip()) <= len(target_url) + 12
                )
                if is_explicit_read:
                    web_preflight_triggered = True
                    yield format_sse("web_reading_started", {"url": target_url})
                    try:
                        from app.services.web.reader import get_web_fetch_service
                        from app.services.web.context_store import get_web_context_store, WebPageContext
                        from datetime import datetime, timezone

                        web_svc = get_web_fetch_service(tenant_id=self.tenant_id)
                        fetch_res = await web_svc.read_webpage(target_url, tenant_id=self.tenant_id)

                        if fetch_res.get("status") in ("SUCCESS", "FALLBACK_PARSED") and fetch_res.get("extracted_text"):
                            canonical_url = fetch_res.get("canonical_url") or target_url
                            page_title = fetch_res.get("title") or fetch_res.get("domain") or canonical_url
                            domain = fetch_res.get("domain") or ""

                            web_store = get_web_context_store()
                            web_store.store_page(
                                conversation_id=conversation_id,
                                page=WebPageContext(
                                    canonical_url=canonical_url,
                                    original_url=target_url,
                                    title=page_title,
                                    extracted_text=fetch_res.get("extracted_text", ""),
                                    hostname=domain,
                                    content_type=fetch_res.get("content_type", "text/html"),
                                    retrieved_at=datetime.now(timezone.utc),
                                ),
                            )
                            yield format_sse("web_source_discovered", {
                                "url": canonical_url,
                                "title": page_title,
                                "domain": domain,
                                "status": "SUCCESS",
                            })
                            yield format_sse("web_reading_completed", {
                                "url": canonical_url,
                                "title": page_title,
                            })

                            web_chunk = VectorSearchResult(
                                chunk_id=str(uuid.uuid5(uuid.NAMESPACE_URL, canonical_url)),
                                document_id=str(canonical_url),
                                document_title=page_title,
                                knowledge_base_id=None,
                                content=fetch_res.get("extracted_text", "")[:4000],
                                score=0.99,
                                metadata={
                                    "source_type": "web",
                                    "source_url": canonical_url,
                                    "domain": domain,
                                    "title": page_title,
                                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                                },
                            )
                            explicit_web_chunks.append(web_chunk)
                        else:
                            error_reason = fetch_res.get("description") or fetch_res.get("status") or "Page unreachable"
                            yield format_sse("web_reading_failed", {
                                "url": target_url,
                                "error": error_reason,
                            })
                            web_preflight_notice = (
                                f"WEB NOTICE: The requested webpage ({target_url}) could not be retrieved "
                                f"due to: {error_reason}. Inform the user clearly that this specific webpage could not be accessed, "
                                f"explain the reason, and do not make up facts or cite unrelated documents."
                            )
                    except Exception as pre_err:
                        logger.warning(f"Error in web URL preflight: {pre_err}")
                        yield format_sse("web_reading_failed", {
                            "url": target_url,
                            "error": str(pre_err),
                        })

        if candidate_kb_ids:
            yield format_sse(
                "retrieval_start",
                {"connected_kb_count": len(candidate_kb_ids)},
            )

            retrieval_span = trace.start_span("retrieval")
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
                target_doc_ids = None
                if is_public:
                    # Public access boundary: only retrieve chunks from documents with access_level == "PUBLIC"
                    from app.models.knowledge import Document
                    pub_doc_stmt = select(Document.id).where(
                        Document.knowledge_base_id.in_(authorized_kb_ids),
                        Document.tenant_id == self.tenant_id,
                        Document.access_level == "PUBLIC",
                        Document.status != "DELETED",
                    )
                    target_doc_ids = list((await self.session.execute(pub_doc_stmt)).scalars().all())

                search_resp = await retrieval_svc.search(
                    query=user_message,
                    knowledge_base_ids=list(authorized_kb_ids),
                    mode=asst.retrieval_mode or "hybrid",
                    top_k=asst.top_k or 5,
                    document_ids=target_doc_ids,
                )
                retrieved_results = search_resp.results
                trace.retrieval_metadata = search_resp.diagnostics
                retrieval_span.set_attribute("timing_ms", search_resp.diagnostics.get("timing_ms", {}))
                retrieval_span.set_attribute("vector_store", search_resp.diagnostics.get("vector_store"))
                retrieval_span.set_attribute("candidates_found", search_resp.diagnostics.get("candidates_found", 0))
                retrieval_span.set_attribute("authorized_count", search_resp.diagnostics.get("authorized_count", 0))
            
            retrieval_span.set_attribute("candidate_kbs", len(authorized_kb_ids) if authorized_kb_ids else 0)
            retrieval_span.set_attribute("results_count", len(retrieved_results))
            retrieval_span.finish()
            trace.retrieved_chunk_count = len(retrieved_results)

        # 4b. Chat-Scoped Conversation Attachment Retrieval (M22)
        if not is_public:
            try:
                from app.services.conversation_attachment_service import ConversationAttachmentService
                att_svc = ConversationAttachmentService(self.session, self.tenant_id)
                att_results = await att_svc.search_attachment_chunks(
                    conversation_id=conversation_id,
                    query=user_message,
                    top_k=4,
                )
                if att_results:
                    # Place conversation attachment chunks at the front for grounded chat focus
                    retrieved_results = att_results + retrieved_results
            except Exception as att_err:
                logger.warning(f"Error searching conversation attachments: {att_err}")

        # 4c. Conversation-Scoped Web Context Retrieval (M27)
        if not is_public:
            try:
                from app.services.web.context_store import get_web_context_store
                web_store = get_web_context_store()
                cached_pages = web_store.get_pages(conversation_id)
                if cached_pages:
                    for cp in cached_pages:
                        if not any(r.document_id == str(cp.canonical_url) for r in retrieved_results):
                            web_chunk = VectorSearchResult(
                                chunk_id=str(uuid.uuid5(uuid.NAMESPACE_URL, cp.canonical_url)),
                                document_id=str(cp.canonical_url),
                                document_title=cp.title or cp.hostname,
                                knowledge_base_id=None,
                                content=cp.extracted_text[:2000],
                                score=0.95,
                                metadata={
                                    "source_type": "web",
                                    "source_url": cp.canonical_url,
                                    "domain": cp.hostname,
                                    "title": cp.title,
                                    "retrieved_at": cp.retrieved_at.isoformat(),
                                },
                            )
                            retrieved_results.append(web_chunk)
            except Exception as web_err:
                logger.warning(f"Error loading conversation web context: {web_err}")

        # 4d. Source-Aware Grounding & Citation Filtering (M28.1 & M28.2)
        # For explicit webpage requests, requested web content is the primary context.
        # Only retain KB documents if user explicitly requested comparison or document retrieval.
        if explicit_web_chunks:
            lower_user_msg = user_message.lower()
            wants_comparison = any(
                w in lower_user_msg
                for w in ("document", "file", "kb", "knowledge base", "compare", "pdf", "attachment", "both")
            )
            if wants_comparison:
                retrieved_results = explicit_web_chunks + [
                    r for r in retrieved_results
                    if (r.score is not None and r.score >= 0.70)
                ]
            else:
                retrieved_results = explicit_web_chunks
        elif web_preflight_triggered and web_preflight_notice:
            # When explicit URL failed to fetch, discard unrelated KB matches unless comparison was asked
            lower_user_msg = user_message.lower()
            if not any(w in lower_user_msg for w in ("document", "file", "kb", "knowledge base", "compare")):
                retrieved_results = []
            else:
                retrieved_results = [
                    r for r in retrieved_results
                    if (r.score is not None and r.score >= 0.75)
                ]

        # 5. Assemble Context & Citations with 4-Tier Trust Hierarchy
        ctx_span = trace.start_span("context_assembly")
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
            web_notice=web_preflight_notice,
        )
        ctx_span.set_attribute("citations", len(citations_data))
        ctx_span.finish()
        trace.citation_count = len(citations_data)

        yield format_sse(
            "retrieval_complete",
            {
                "citation_count": len(citations_data),
                "citations": citations_data,
            },
        )

        # 6. Quota Check, Reservation & Key Resolution
        quota_svc = QuotaService(self.session, self.tenant_id)
        byok_svc = BYOKVaultService(self.session, self.tenant_id)

        input_token_estimate = sum(len(m.content.split()) for m in messages)
        reservation_id = None
        try:
            reservation_id = await quota_svc.reserve_quota(estimated_tokens=input_token_estimate)
        except Exception as q_err:
            detail_msg = getattr(q_err, "detail", str(q_err))
            err_msg = f"Quota exceeded: {detail_msg}"
            trace.finish(status="FAILED", error=err_msg)
            await tracer.persist_to_database(trace, session=self.session)
            err_msg_obj = Message(
                id=uuid.uuid4(),
                tenant_id=self.tenant_id,
                conversation_id=conversation_id,
                sender_type="assistant",
                content=f"⚠️ {err_msg}",
                token_count=0,
            )
            self.session.add(err_msg_obj)
            await self.session.commit()
            yield format_sse("message_error", {"error": err_msg})
            return

        # Strict BYOK policy: Never silently fall back to platform keys for commercial providers
        resolved_key, resolved_base_url = await byok_svc.resolve_plaintext_key(asst.llm_provider)
        if asst.llm_provider in ("openai", "anthropic", "gemini", "groq") and not resolved_key:
            quota_svc.release_reservation(reservation_id)
            await quota_svc.release_reservation_async(reservation_id)
            err_msg = (
                f"Provider '{asst.llm_provider}' is not configured with an active BYOK credential for this workspace. "
                f"Please add your API key under Providers & Keys."
            )
            trace.finish(status="FAILED", error=err_msg)
            await tracer.persist_to_database(trace, session=self.session)
            err_msg_obj = Message(
                id=uuid.uuid4(),
                tenant_id=self.tenant_id,
                conversation_id=conversation_id,
                sender_type="assistant",
                content=f"⚠️ {err_msg}",
                token_count=0,
            )
            self.session.add(err_msg_obj)
            await self.session.commit()
            yield format_sse("message_error", {"error": err_msg})
            return

        # 7. Stream tokens via LLM Provider
        llm_registry = get_llm_registry()
        provider = llm_registry.get_provider(asst.llm_provider)

        llm_config = LLMConfig(
            provider=asst.llm_provider,
            model=asst.default_model or "auto",
            temperature=asst.temperature,
            max_tokens=asst.max_tokens,
            api_key=resolved_key,
            base_url=resolved_base_url,
        )

        # Resolve enabled tools for active assistant configuration
        tools_cfg = asst.tools_config or {}
        enabled_ids = tools_cfg.get("enabled_tool_ids")
        max_agent_steps = int(tools_cfg.get("max_execution_steps", 5))
        require_approval_all = bool(tools_cfg.get("require_approval_all", False))

        tool_svc = ToolRegistryService(self.session, self.tenant_id, user_id=self.user_id)
        raw_tools = await tool_svc.list_tools()
        if enabled_ids is not None:
            raw_tools = [
                t for t in raw_tools
                if t["id"] in enabled_ids or t["name"] in enabled_ids or f"builtin_{t['name']}" in enabled_ids
            ]

        from app.llm.capabilities import get_model_capability_registry

        cap_reg = get_model_capability_registry()
        model_cap = cap_reg.get_model(asst.llm_provider, asst.default_model or "auto")
        if model_cap and not model_cap.supports_tools:
            raw_tools = []

        llm_config.tools = raw_tools

        full_content_chunks: list[str] = []
        dynamic_citations: list[dict[str, Any]] = []
        gen_span = trace.start_span("provider_generation")
        gen_span.set_attribute("provider", asst.llm_provider)
        gen_span.set_attribute("model", asst.default_model or "auto")

        agent_steps = 0

        try:
            while agent_steps < max_agent_steps:
                agent_steps += 1
                has_tool_call = False
                pending_tool_calls = []

                async for chunk in provider.generate_stream(messages, llm_config):
                    if chunk.tool_calls:
                        has_tool_call = True
                        pending_tool_calls.extend(chunk.tool_calls)
                    elif chunk.content_delta:
                        trace.mark_first_token()
                        full_content_chunks.append(chunk.content_delta)
                        yield format_sse("token", {"delta": chunk.content_delta})

                if not has_tool_call:
                    break

                pause_for_approval = False
                for tc in pending_tool_calls:
                    tc_name = tc.get("name")
                    tc_args = tc.get("arguments", {})
                    yield format_sse("tool_call_proposed", {"tool_name": tc_name, "arguments": tc_args})

                    tool_def = next((t for t in raw_tools if t["name"] == tc_name), None)
                    requires_approval = False
                    risk_level = "READ_ONLY"
                    if tool_def:
                        requires_approval = tool_def.get("requires_approval", False)
                        risk_level = tool_def.get("risk_level", "READ_ONLY")

                    if requires_approval or risk_level in ("WRITE", "HIGH_RISK") or require_approval_all:
                        approval_svc = ToolApprovalService(self.session, self.tenant_id)
                        appr = await approval_svc.request_approval(
                            conversation_id=conversation_id,
                            assistant_id=asst.id,
                            user_id=self.user_id,
                            tool_id=tool_def["id"] if tool_def else tc_name,
                            tool_name=tc_name,
                            arguments=tc_args,
                        )
                        yield format_sse("tool_approval_required", {
                            "approval_id": str(appr.id),
                            "tool_name": tc_name,
                            "arguments": tc_args,
                            "token": appr.approval_token,
                            "expires_at": appr.expires_at.isoformat(),
                        })
                        approval_prompt = f"⚠️ Action '{tc_name}' requires human approval before proceeding. Approval request ID: {appr.id}"
                        full_content_chunks.append(approval_prompt)
                        pause_for_approval = True
                        break

                    yield format_sse("tool_call_started", {"tool_name": tc_name})
                    t_start = time.perf_counter()
                    try:
                        tool_id_to_run = tool_def["id"] if tool_def else tc_name
                        exec_result = await tool_svc.execute_tool(tool_id_to_run, tc_args)
                        duration_ms = int((time.perf_counter() - t_start) * 1000)
                        summary = json.dumps(exec_result.get("data", exec_result)) if isinstance(exec_result, dict) else str(exec_result)

                        inv_log = ToolInvocationLog(
                            tenant_id=self.tenant_id,
                            conversation_id=conversation_id,
                            assistant_id=asst.id,
                            user_id=self.user_id,
                            trace_id=trace.trace_id,
                            tool_id=tool_id_to_run,
                            tool_name=tc_name,
                            tool_type=tool_def.get("tool_type", "CUSTOM") if tool_def else "BUILTIN",
                            arguments=tc_args,
                            result_summary=summary[:1000],
                            status="SUCCESS",
                            duration_ms=duration_ms,
                        )
                        self.session.add(inv_log)
                        await self.session.commit()

                        yield format_sse("tool_call_completed", {"tool_name": tc_name, "result_summary": summary[:500]})
                        messages.append(LLMMessage(role="tool", content=summary))

                        # M27: Web Source Discovered Hook
                        if tc_name == "web_read_url" and isinstance(exec_result, dict) and exec_result.get("status") == "SUCCESS":
                            try:
                                from app.services.web.context_store import get_web_context_store, WebPageContext
                                from datetime import datetime, timezone
                                web_store = get_web_context_store()
                                canonical_url = exec_result.get("canonical_url") or exec_result.get("url") or tc_args.get("url", "")
                                page_title = exec_result.get("title") or exec_result.get("hostname") or canonical_url
                                web_store.store_page(
                                    conversation_id=conversation_id,
                                    page=WebPageContext(
                                        canonical_url=canonical_url,
                                        original_url=exec_result.get("original_url", canonical_url),
                                        title=page_title,
                                        extracted_text=exec_result.get("extracted_text", ""),
                                        hostname=exec_result.get("hostname", ""),
                                        content_type=exec_result.get("content_type", "text/html"),
                                        retrieved_at=datetime.now(timezone.utc),
                                    ),
                                )
                                yield format_sse("web_source_discovered", {
                                    "url": canonical_url,
                                    "title": page_title,
                                    "domain": exec_result.get("hostname", ""),
                                    "status": "SUCCESS",
                                })
                                cit_num = len(citations_data) + len(dynamic_citations) + 1
                                dynamic_citations.append({
                                    "id": str(uuid.uuid5(uuid.NAMESPACE_URL, canonical_url)),
                                    "citation_num": cit_num,
                                    "chunk_id": None,
                                    "document_name": page_title[:255],
                                    "page_number": None,
                                    "heading_path": None,
                                    "snippet": (exec_result.get("extracted_text") or "")[:300],
                                    "citation_text": (exec_result.get("extracted_text") or "")[:300],
                                    "source_type": "web",
                                    "source_url": canonical_url,
                                    "domain": exec_result.get("hostname", ""),
                                })
                            except Exception as c_err:
                                logger.warning(f"Error recording web source: {c_err}")

                    except Exception as t_err:
                        duration_ms = int((time.perf_counter() - t_start) * 1000)
                        err_msg = str(t_err)
                        yield format_sse("tool_call_failed", {"tool_name": tc_name, "error": err_msg})
                        messages.append(LLMMessage(role="tool", content=f"Error executing {tc_name}: {err_msg}"))

                if pause_for_approval:
                    break

            gen_span.finish(status="COMPLETED")

        except GeneratorExit:
            quota_svc.release_reservation(reservation_id)
            await quota_svc.release_reservation_async(reservation_id)
            logger.info(f"Stream connection closed by client for trace {trace.trace_id}")
            gen_span.finish(status="CANCELLED", error="Client connection aborted")
            trace.finish(status="CANCELLED", error="Client connection aborted")
            try:
                await tracer.persist_to_database(trace)
            except Exception:
                pass
            raise
        except Exception as e:
            quota_svc.release_reservation(reservation_id)
            await quota_svc.release_reservation_async(reservation_id)
            logger.exception("LLM generation stream failed")
            safe_err = sanitize_error_message(str(e))
            gen_span.finish(status="FAILED", error=safe_err)
            trace.finish(status="FAILED", error=safe_err)
            await tracer.persist_to_database(trace, session=self.session)
            err_msg_obj = Message(
                id=uuid.uuid4(),
                tenant_id=self.tenant_id,
                conversation_id=conversation_id,
                sender_type="assistant",
                content=f"⚠️ LLM generation failed: {safe_err}",
                token_count=0,
            )
            self.session.add(err_msg_obj)
            await self.session.commit()
            yield format_sse("message_error", {"error": f"LLM generation failed: {safe_err}"})
            return

        final_content = "".join(full_content_chunks)
        if not final_content.strip():
            quota_svc.release_reservation(reservation_id)
            await quota_svc.release_reservation_async(reservation_id)
            logger.warning("LLM provider returned empty response stream")
            trace.finish(status="FAILED", error="Empty response stream received")
            await tracer.persist_to_database(trace, session=self.session)
            err_msg_obj = Message(
                id=uuid.uuid4(),
                tenant_id=self.tenant_id,
                conversation_id=conversation_id,
                sender_type="assistant",
                content="⚠️ LLM generation failed: Empty response stream received",
                token_count=0,
            )
            self.session.add(err_msg_obj)
            await self.session.commit()
            yield format_sse("message_error", {"error": "LLM generation failed: Empty response stream received"})
            return

        # 8. Persist Assistant Message and Citations in Database
        final_normalized_content = normalize_markdown(final_content)
        assistant_msg = Message(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            conversation_id=conversation_id,
            sender_type="assistant",
            content=final_normalized_content,
            token_count=len(final_normalized_content.split()),
        )
        self.session.add(assistant_msg)
        await self.session.flush()

        all_citations_to_save = citations_data + dynamic_citations
        for c in all_citations_to_save:
            citation_obj = MessageCitation(
                id=uuid.uuid4(),
                tenant_id=self.tenant_id,
                message_id=assistant_msg.id,
                chunk_id=uuid.UUID(c["chunk_id"]) if c.get("chunk_id") else None,
                document_name=c["document_name"],
                citation_num=c["citation_num"],
                citation_text=c.get("snippet") or c.get("citation_text") or "",
            )
            self.session.add(citation_obj)

        await self.session.commit()

        # 9. Record Atomic Usage
        output_token_estimate = len(final_content.split())
        await quota_svc.record_usage(
            provider_name=asst.llm_provider,
            model_name=asst.default_model or "auto",
            prompt_tokens=input_token_estimate,
            completion_tokens=output_token_estimate,
            assistant_id=asst.id,
            user_id=self.user_id,
            is_preview=False,
            traffic_type=traffic_type,
            reservation_id=reservation_id,
        )

        duration = round((time.perf_counter() - start_time) * 1000, 2)

        # Complete Observability Trace
        if policy.capture_mode == "REDACTED_PREVIEW":
            trace.set_previews(
                user_input=user_message,
                output_text=final_content,
                max_length=policy.max_preview_length,
            )
        trace.input_tokens = input_token_estimate
        trace.output_tokens = output_token_estimate
        trace.total_tokens = input_token_estimate + output_token_estimate
        trace.is_token_estimated = True
        trace.finish(status="COMPLETED")
        await tracer.persist_to_database(trace, session=self.session)

        yield format_sse(
            "usage",
            {
                "input_tokens": sum(len(m.content.split()) for m in messages),
                "output_tokens": len(final_content.split()),
                "duration_ms": duration,
                "model": asst.default_model,
                "trace_id": trace.trace_id,
            },
        )
        yield format_sse(
            "message_complete",
            {
                "message_id": str(assistant_msg.id),
                "conversation_id": str(conversation_id),
                "status": "COMPLETED",
                "trace_id": trace.trace_id,
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

        policy_svc = ObservabilityPolicyService(self.session, self.tenant_id)
        policy = await policy_svc.get_policy()

        tracer = get_tracer()
        trace = tracer.start_trace(
            tenant_id=self.tenant_id,
            assistant_id=None,
            assistant_name="Preview Simulator",
            conversation_id=None,
            traffic_type="preview",
        )
        trace.provider = llm_provider
        trace.model = default_model or "auto"
        trace.retrieval_mode = retrieval_mode or "hybrid"
        if policy.capture_mode == "REDACTED_PREVIEW":
            trace.set_previews(user_input=user_message, max_length=policy.max_preview_length)

        yield format_sse("message_start", {"preview": True, "model": default_model, "trace_id": trace.trace_id})

        retrieved_results: list[VectorSearchResult] = []
        citations_data: list[dict[str, Any]] = []

        candidate_kb_ids = knowledge_base_ids or []
        if candidate_kb_ids:
            yield format_sse("retrieval_start", {"connected_kb_count": len(candidate_kb_ids)})
            ret_span = trace.start_span("retrieval")
            ret_span.set_attribute("candidate_kbs", len(candidate_kb_ids))
            ret_span.set_attribute("mode", retrieval_mode or "hybrid")

            valid_kb_stmt = select(KnowledgeBase.id).where(
                KnowledgeBase.id.in_(candidate_kb_ids),
                KnowledgeBase.tenant_id == self.tenant_id,
                KnowledgeBase.status == "ACTIVE",
            )
            authorized_kb_ids = (await self.session.execute(valid_kb_stmt)).scalars().all()
            ret_span.set_attribute("authorized_kbs", len(authorized_kb_ids))

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
                ret_span.set_attribute("results_count", len(retrieved_results))
                ret_span.set_attribute("retrieval_timing_ms", search_resp.diagnostics.get("timing_ms", {}))
                trace.retrieval_metadata = {
                    "mode": retrieval_mode or "hybrid",
                    "top_k": top_k or 5,
                    "connected_kb_count": len(candidate_kb_ids),
                    "authorized_kb_count": len(authorized_kb_ids),
                    "candidate_chunks_found": len(retrieved_results),
                    "timing_ms": search_resp.diagnostics.get("timing_ms", {}),
                    "vector_store": "pgvector",
                }
            else:
                trace.retrieval_metadata = {
                    "mode": retrieval_mode or "hybrid",
                    "connected_kb_count": len(candidate_kb_ids),
                    "authorized_kb_count": 0,
                    "candidate_chunks_found": 0,
                    "status": "NO_AUTHORIZED_KBS",
                }
            ret_span.finish(status="COMPLETED")
        else:
            trace.retrieval_metadata = {
                "mode": "none",
                "connected_kb_count": 0,
                "candidate_chunks_found": 0,
                "status": "NO_KNOWLEDGE_BASES",
            }

        ctx_span = trace.start_span("context_assembly")
        ctx_span.set_attribute("max_tokens", max_tokens)
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
        ctx_span.set_attribute("message_count", len(messages))
        ctx_span.set_attribute("citation_count", len(citations_data))
        ctx_span.finish(status="COMPLETED")

        yield format_sse(
            "retrieval_complete",
            {
                "citation_count": len(citations_data),
                "citations": citations_data,
            },
        )

        # Quota Check & Key Resolution
        quota_svc = QuotaService(self.session, self.tenant_id)
        byok_svc = BYOKVaultService(self.session, self.tenant_id)

        input_token_estimate = sum(len(m.content.split()) for m in messages)
        try:
            await quota_svc.check_quota(estimated_tokens=input_token_estimate)
        except Exception as q_err:
            detail_msg = getattr(q_err, "detail", str(q_err))
            trace.finish(status="FAILED", error=f"Quota exceeded: {detail_msg}")
            await tracer.persist_to_database(trace, session=self.session)
            yield format_sse("message_error", {"error": f"Quota exceeded: {detail_msg}"})
            return

        resolved_key, resolved_base_url = await byok_svc.resolve_plaintext_key(llm_provider)
        if llm_provider in ("openai", "anthropic", "gemini", "groq") and not resolved_key:
            err_msg = (
                f"Provider '{llm_provider}' is not configured with an active BYOK credential for this workspace. "
                f"Please add your API key under Providers & Keys."
            )
            trace.finish(status="FAILED", error=err_msg)
            await tracer.persist_to_database(trace, session=self.session)
            yield format_sse("message_error", {"error": err_msg})
            return

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
            api_key=resolved_key,
            base_url=resolved_base_url,
        )

        full_content_chunks: list[str] = []
        gen_span = trace.start_span("provider_generation")
        gen_span.set_attribute("provider", llm_provider)
        gen_span.set_attribute("model", default_model or "auto")

        try:
            async for chunk in provider.generate_stream(messages, llm_config):
                if chunk.content_delta:
                    trace.mark_first_token()
                    full_content_chunks.append(chunk.content_delta)
                    yield format_sse("token", {"delta": chunk.content_delta})
            gen_span.finish(status="COMPLETED")
        except GeneratorExit:
            logger.info(f"Preview stream connection closed by client for trace {trace.trace_id}")
            gen_span.finish(status="CANCELLED", error="Client connection aborted")
            trace.finish(status="CANCELLED", error="Client connection aborted")
            try:
                await tracer.persist_to_database(trace)
            except Exception:
                pass
            raise
        except Exception as e:
            logger.exception("Preview LLM generation stream failed")
            safe_err = sanitize_error_message(str(e))
            gen_span.finish(status="FAILED", error=safe_err)
            trace.finish(status="FAILED", error=safe_err)
            await tracer.persist_to_database(trace, session=self.session)
            yield format_sse("message_error", {"error": f"LLM generation failed: {safe_err}"})
            return

        final_content = "".join(full_content_chunks)
        if not final_content.strip():
            trace.finish(status="FAILED", error="Empty response stream received")
            await tracer.persist_to_database(trace, session=self.session)
            yield format_sse("message_error", {"error": "LLM generation failed: Empty response stream received"})
            return

        output_token_estimate = len(final_content.split())
        await quota_svc.record_usage(
            provider_name=llm_provider,
            model_name=default_model or "auto",
            prompt_tokens=input_token_estimate,
            completion_tokens=output_token_estimate,
            user_id=self.user_id,
            is_preview=True,
        )

        duration = round((time.perf_counter() - start_time) * 1000, 2)

        # Complete Observability Trace
        if policy.capture_mode == "REDACTED_PREVIEW":
            trace.set_previews(
                user_input=user_message,
                output_text=final_content,
                max_length=policy.max_preview_length,
            )
        trace.input_tokens = input_token_estimate
        trace.output_tokens = output_token_estimate
        trace.total_tokens = input_token_estimate + output_token_estimate
        trace.is_token_estimated = True
        trace.finish(status="COMPLETED")
        await tracer.persist_to_database(trace, session=self.session)

        yield format_sse(
            "usage",
            {
                "input_tokens": sum(len(m.content.split()) for m in messages),
                "output_tokens": len(final_content.split()),
                "duration_ms": duration,
                "model": default_model,
                "trace_id": trace.trace_id,
            },
        )
        yield format_sse(
            "message_complete",
            {
                "status": "COMPLETED",
                "preview": True,
                "trace_id": trace.trace_id,
            },
        )
