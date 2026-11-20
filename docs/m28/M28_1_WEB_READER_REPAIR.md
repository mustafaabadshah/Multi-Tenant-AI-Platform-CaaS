# M28.1 — Web Reader Repair (Problem A Fix)

## 1. Problem Statement
When asking an assistant a direct query with a public URL:
`https://www.w3schools.com/cpp/cpp_for_loop.asp read this for knowledge using tool`
The assistant previously responded:
> *"I'm not able to retrieve or view external web pages..."*

## 2. Root Cause Analysis
1. **Model Spontaneous Calling Dependency:** The architecture relied entirely on the LLM autonomously deciding to generate a function call (`web_read_url`) from raw user text. When a provider or model lacked native tool calling or refused to call tools on plain URLs, the tool was never invoked.
2. **Missing Anti-Refusal System Instructions:** Default system prompts did not explicitly inform the LLM that real-time web reading tools were enabled, causing model weights to emit standard canned refusals ("As an AI without internet access...").
3. **Lack of Frontend SSE Progress Feedback:** There was no SSE stream event indicating whether a webpage was being fetched, completed, or blocked.

## 3. Engineering Fix
1. **Deterministic Web URL Preflight in `AssistantRuntime`:**
   - Detects explicit URLs via regex pattern matching in incoming user messages.
   - Executes authorized preflight retrieval via `WebFetchService.read_webpage()` with strict SSRF filtering, domain restrictions, and content size bounding.
   - Caches the retrieved page into the conversation's web context store.
   - Injects the extracted page text directly at index 0 of `explicit_web_chunks` so the LLM generation has immediate, guaranteed access to the webpage content without depending on function-calling luck.
2. **Anti-Refusal Instruction Injection in `build_rag_context`:**
   - Injects a strict system instruction:
     > *"WEB BROWSING & TOOLS: You have access to real-time web reading tools (web_read_url, web_search) and provided web page sources. If web context is provided, ground your answers in it. NEVER claim you cannot access the internet or view external web pages when web context or browsing tools are enabled."*
   - Appends contextual `WEB NOTICE` when a URL is retrieved or failed.
3. **Frontend SSE Telemetry:**
   - Emits SSE events: `web_reading_started`, `web_source_discovered`, `web_reading_completed`, and `web_reading_failed`.
   - Frontend displays a live, non-intrusive status pill above the streaming response ("Reading webpage...", "Webpage read: [Title]", or actionable error chip if inaccessible).
