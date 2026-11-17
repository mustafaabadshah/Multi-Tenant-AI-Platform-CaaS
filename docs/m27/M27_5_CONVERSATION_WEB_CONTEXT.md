# M27.5 — Conversation-Scoped Web Context & Follow-Up Grounding

## 1. Problem Statement

When a user pastes a URL (such as a documentation page or educational tutorial) into a conversation, they frequently ask follow-up questions:
- *User:* "Read https://www.w3schools.com/cpp/cpp_for_loop.asp and explain C++ for loops."
- *Assistant:* Explains syntax and structure.
- *User:* "Give me a different example with nested loops."

Without conversation-scoped context, the assistant would either:
1. Re-fetch the web page on every single message turn (wasting bandwidth and adding latency).
2. Forget the web page entirely and lose grounding.
3. Inappropriately persist external third-party content into permanent Knowledge Base tables without user consent.

---

## 2. In-Memory Conversation-Scoped Context Store

[context_store.py](file:///E:/MM%20Office/Multi-Tanant-CaaS/backend/app/services/web/context_store.py) implements `ConversationWebContextStore`:
- **Scope:** Keyed strictly by `conversation_id`.
- **Isolation:** A web page read in Conversation A is **never accessible** in Conversation B, even within the same tenant. Cross-tenant access is physically impossible.
- **Capacity:** Bounded to a maximum of **5 active web pages** per conversation (oldest evicted first).
- **TTL Expiration:** Default **3600 seconds (1 hour)** from initial retrieval. Expired pages are lazily evicted on subsequent access.
- **Zero Database Migration:** Stored purely in-memory; no Postgres or Alembic schema changes required.

---

## 3. Integration into AssistantRuntime Context Assembly

In [runtime.py](file:///E:/MM%20Office/Multi-Tanant-CaaS/backend/app/assistant_runtime/runtime.py) (Step 4c):
1. Prior to LLM generation, `AssistantRuntime` queries `ConversationWebContextStore.get_pages(conversation_id)`.
2. Any active cached web pages are mapped into synthetic `VectorSearchResult` items with `source_type="web"`, `source_url`, `domain`, and clean excerpts.
3. Chunks are sanitized through `sanitize_untrusted_content` in [context.py](file:///E:/MM%20Office/Multi-Tanant-CaaS/backend/app/assistant_runtime/context.py) to prevent prompt injection.
4. If the user asks a follow-up, the web page context is already present in Tier 4 of the context hierarchy, ensuring instantaneous, fully grounded answers without re-fetching.
