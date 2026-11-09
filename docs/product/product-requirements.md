# Product Requirements Document (PRD) — Multi-Tenant AI Assistant Platform

**Document Version:** 1.0.0  
**Status:** Requirements Specification  
**Architecture:** Modular Monolith (FastAPI + Next.js App Router)  
**Security Boundary:** Multi-Tenant Isolation (RBAC + Tenant Scoping)  

---

## 1. System Scope & Technical Boundaries

The Multi-Tenant AI Assistant Platform operates as a modular monolith with clearly encapsulated boundaries:
- **Core Backend:** Python 3.12+, FastAPI, SQLAlchemy 2.0 (Async), Pydantic v2, Alembic.
- **Frontend:** Next.js (App Router), TypeScript, Tailwind CSS, Lucide React, React Hook Form, Zod.
- **Relational Storage:** PostgreSQL 16+ as production source of truth; SQLite supported for local fast test suites.
- **Vector Storage:** PostgreSQL (`pgvector`), Qdrant vector database, and vectorless PostgreSQL Full-Text Search (FTS).
- **Security & Cryptography:** Argon2id password hashing, AES-256-GCM BYOK credential encryption, strict JWT token validation with workspace claims.

---

## 2. Functional Requirements

### 2.1 Studio 1: Assistant Studio & Guided Lifecycle

#### FR-AST-01: Guided Assistant Creation Wizard
- The platform shall provide a multi-step creation wizard for non-technical users:
  - **Step 1 (Purpose & Identity):** Name, slug, description, category, and purpose template selection.
  - **Step 2 (Audience & Persona):** Target audience level (Beginner, Intermediate, Expert, Academic, Public), language preference, and tone (Professional, Conversational, Socratic, Concise, Empathetic).
  - **Step 3 (Knowledge Linkage):** Selection of existing Knowledge Bases or inline document upload.
  - **Step 4 (Behavior & Rules):** System prompt configuration, citation strictness (Strict Grounding vs. Synthesizing), handling of missing knowledge (Refusal vs. General Knowledge fallback), and response formatting.
  - **Step 5 (Review & Launch):** Summary preview, test sandbox link, and publishing settings.

#### FR-AST-02: Template Registry
- The system shall provide extensible out-of-the-box assistant templates:
  - **Education:**
    - *Exam Prep Assistant:* Emphasizes practice questions, active recall, flashcards, and step-by-step solutions.
    - *Subject Tutor:* Explains complex topics, adjusts vocabulary to student grade level, uses Socratic questioning.
    - *MCQ & Quiz Generator:* Generates structured multi-choice questions with answer keys, explanations, and citation links.
  - **Business & Operations:**
    - *Company Handbook & HR:* Answers policy, benefits, and onboarding questions; strictly references company SOPs.
    - *Customer Support:* Resolves client queries, enforces friendly brand tone, provides escalation triggers.
    - *Product Documentation Assistant:* Summarizes technical manuals, API specs, and release notes.
  - **Personal & Professional:**
    - *Personal Document Vault:* Queries personal files, resumes, and medical/insurance summaries with privacy disclaimers.
    - *Legal Research Assistant:* Explains contract clauses with prominent "Not Legal Advice" disclaimers.

#### FR-AST-03: Dual-Mode Experience (Simple vs. Advanced)
- **Simple Mode (Default):**
  - Shows plain-English selections: Purpose, Audience, Response Style, and Knowledge Source.
  - Automatically assigns optimal parameters: `retrieval_mode="hybrid"`, `top_k=5`, `temperature=0.3` for factual grounding, `similarity_metric="cosine"`.
- **Advanced Mode (Toggle):**
  - Exposes granular parameters: System prompt editor with variable injection, LLM provider selection, model identifier, temperature (0.0 to 1.0), max output tokens, Top-K chunks (1 to 20), similarity threshold (0.0 to 1.0), hybrid fusion weights (dense vs. BM25), and prompt version history.

#### FR-AST-04: Prompt Management & Guardrails
- The system shall store versioned prompt snapshots (`AssistantVersion` and `AssistantPrompt`).
- The assistant runtime shall enforce strict 4-tier prompt layering to prevent user prompt injection:
  1. **Platform Security Layer (Immutable):** Guardrails preventing credential leakage, unauthorized SQL generation, and system prompt disclosure.
  2. **Assistant Instructions Layer (Configured):** Persona, role, tone, and refusal rules defined by the assistant creator.
  3. **Retrieved Context Layer (Untrusted Data):** Grounded chunks wrapped in isolation delimiters (e.g. `<retrieved_context>` blocks) with source metadata.
  4. **User Conversation Layer (Untrusted Input):** The current message and historical conversation turns.

---

### 2.2 Studio 2: Knowledge Management & Document Intelligence

#### FR-KNW-01: Multi-Format Parser Engine
- The platform shall parse documents locally without third-party cloud data exposure:
  - Text & Markdown (`.txt`, `.md`)
  - Office Documents (`.docx`, `.pptx`, `.xlsx`)
  - Tabular & Structured (`.csv`, `.tsv`, `.json`, `.jsonl`)
  - Adobe Portable Document Format (`.pdf`) via PyPDF / pdfplumber.
  - Structured Query Language (`.sql`): Static AST analysis via `sqlglot` to extract schemas, table definitions, and relationships without executing code.
  - Scanned Documents & Images (`.png`, `.jpg`, `.tiff`): OCR processing via Tesseract with CPU fallback.
  - Web URLs: Sanitized HTML-to-markdown extraction with anti-SSRF IP verification (blocking `127.0.0.1`, `169.254.169.254`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`).

#### FR-KNW-02: Resilient Ingestion Lifecycle
- Every document must pass through tracked, idempotent states:
  `UPLOADED → VALIDATING → PARSING → OCR_PROCESSING → CHUNKING → EMBEDDING → INDEXING → READY`
- Failure states (`FAILED_VALIDATION`, `FAILED_PARSING`, `FAILED_EMBEDDING`) must record exact error messages, stage identifiers, and duration.
- The system must support background reprocessing and deletion without orphaned chunks.

#### FR-KNW-03: Chunk Inspection & Tuning
- The knowledge interface shall provide an interactive **Chunk Inspector**:
  - Filter and inspect individual chunks for any document.
  - View chunk text, character count, token estimate, heading provenance, and page numbers.
  - Compare chunking strategies: Recursive text splitting, Sentence-aware, Markdown heading-aware, and Table/Row-aware chunking.
  - Live chunking preview: Enter test parameters (chunk size, overlap) and view generated chunks before saving.

#### FR-KNW-04: Retrieval Playground
- Creators and administrators shall have an interactive **Retrieval Playground**:
  - Enter test queries and specify retrieval mode (`hybrid`, `semantic`, `lexical`).
  - View raw retrieved chunks with individual BM25 scores, dense cosine similarity scores, and reciprocal rank fusion (RRF) rank.
  - Validate that tenant and department ACL filters correctly exclude restricted documents.

---

### 2.3 Studio 3: Model & Integration Studio (BYOK & Quotas)

#### FR-MOD-01: Multi-Provider BYOK Architecture
- The system shall maintain a pluggable provider registry supporting:
  - **OpenAI:** `gpt-4o`, `gpt-4o-mini`, `o1-preview`, `text-embedding-3-small`.
  - **Anthropic:** `claude-3-5-sonnet`, `claude-3-5-haiku`.
  - **Google Gemini:** `gemini-1.5-pro`, `gemini-1.5-flash`.
  - **Groq:** Ultra-low-latency Llama 3.3 70B, Mixtral 8x7B.
  - **OpenRouter / DeepSeek / Mistral / Cerebras:** Standard OpenAI-compatible endpoints.
  - **Local Models:** Local CPU models (FastEmbed, sentence-transformers) and OmniRoute local gateway.
- Providers must support standard capabilities: Streaming SSE, Token Usage Reporting, Model Context Window introspection, and Function Calling.

#### FR-MOD-02: Key Encryption & Vault Security
- All user-supplied API keys must be encrypted using AES-256-GCM before database insertion.
- The database shall only store the encrypted ciphertext and initialization vector (IV). Plaintext keys shall never be logged, cached in memory beyond request scope, or returned to frontend clients.
- The UI shall provide a "Test Connection" button that executes a lightweight model ping (e.g. `max_tokens=1`) to verify key validity before saving.

#### FR-MOD-03: Quota & Cost Management
- The platform shall enforce tenant-level and user-level usage controls:
  - Daily / Monthly Token Quotas.
  - Concurrent Request Rate Limiting.
  - Storage Allocation Caps (MB / GB).
  - Maximum Active Assistants per Workspace.
- The system shall record token usage (prompt tokens, completion tokens) for every conversation turn to provide usage telemetry and estimated costs.

---

### 2.4 Studio 4: Chat & Conversation Experience

#### FR-CHT-01: Real-Time Streaming & Interaction
- Responses shall stream via Server-Sent Events (SSE) with immediate progressive text rendering.
- Users shall be able to:
  - Stop response generation in mid-stream (`AbortController`).
  - Regenerate assistant responses.
  - Copy response text or citations to clipboard with one click.
  - Provide thumbs-up / thumbs-down feedback on individual responses.

#### FR-CHT-02: Verified Visual Citations
- Citations must be grounded directly in retrieved knowledge chunks.
- The chat interface shall render citations as interactive badge pills (e.g. `[1]`, `[2]`).
- Clicking a citation pill opens the **Citation Inspector**:
  - **Visual View (PDFs):** Shows the document page with the verified bounding box highlight overlay. If geometric coordinates are available, exact coordinates are highlighted; if fallback text matching is used, it is explicitly labeled as *Verified Text Match*.
  - **Text View:** Shows the full chunk excerpt, source filename, page number, heading hierarchy, and similarity score.

#### FR-CHT-03: Conversation Management
- Full conversation history scoped to authenticated user and active workspace.
- Search conversations by keyword in title or message content.
- Inline title renaming and deletion with confirmation.
- Ephemeral turn attachments: Users may attach a PDF or TXT directly in the chat for immediate analysis without adding it to the persistent knowledge base.

---

### 2.5 Studio 5: Publishing, Administration & Observability

#### FR-PUB-01: Multi-Channel Publishing
- Assistants can be published across multiple channels:
  - **Workspace Private:** Only members of the tenant with appropriate department/group roles can access.
  - **Public Share Link:** A clean, unauthenticated or password-protected public URL (e.g. `/chat/share/{share_token}`).
  - **Embeddable Web Widget:** Lightweight `<script>` tag and `<iframe>` code snippet for external websites, with configurable primary color, position (bottom-right/bottom-left), greeting message, and suggested starter prompts.
  - **Developer API:** Tenant-scoped API keys allowing external applications to query assistants via `/api/v1/assistants/{id}/chat`.

#### FR-PUB-02: Tenant Administration & Security
- Complete Workspace RBAC:
  - **Owner:** Full workspace control, billing/quotas, member management, tenant deletion.
  - **Admin:** Assistant creation, knowledge base management, provider key configuration, user invitations.
  - **Member:** Chat with permitted assistants, create personal assistants (if enabled by tenant policy).
  - **Auditor:** Read-only access to audit logs, usage metrics, and evaluation reports.
- Comprehensive audit trail recording user logins, assistant creation/updates, document uploads/deletions, key updates, and sharing actions.

#### FR-PUB-03: Evaluation & Observability Studio
- **Automated Evaluations:** Run test question sets against assistants and calculate:
  - *Retrieval Recall:* Did retrieved chunks include the target reference document?
  - *Faithfulness:* Is the answer strictly derived from the retrieved context?
  - *Citation Accuracy:* Do citations match the actual claims made?
  - *Latency & Cost:* Average TTFT (time-to-first-token) and total execution cost.
- **Trace Observability:** Inspect query processing traces (normalization, retrieval time, LLM inference time, token count).

---

## 3. Non-Functional Requirements

### 3.1 Performance & Resource Efficiency
- **Lightweight Local Footprint:** Must run smoothly on developer hardware (Intel i3-7100U, 8 GB RAM, Windows 10, Drive E:).
- **Time to First Token (TTFT):** Under 800 ms for streaming chat responses when using cloud providers or local CPU mock.
- **Ingestion Throughput:** Ingest and chunk a 100-page standard text PDF in under 15 seconds using local CPU extraction.

### 3.2 Security & Compliance
- **Tenant Isolation:** Enforced on every SQL query via `tenant_id` where clause. Zero cross-tenant data leakage.
- **Password Security:** Argon2id with recommended OWASP memory and iteration parameters.
- **Zero Raw Code Execution:** Uploaded files (including SQL, CSV formulas, and Markdown) are parsed as inert data, never executed.
- **SSRF Defenses:** Web crawling endpoints reject loopback, link-local, and private RFC-1918 IPv4/IPv6 ranges.

### 3.3 UI Aesthetic & Usability (Linear × Apple Notes)
- High information density, restrained color palette (deep slate/black surfaces, soft off-whites, subtle light-blue `#38bdf8` / `#0284c7` accents).
- Zero decorative fake graphs or empty statistics.
- Responsive design supporting desktop, tablet, and mobile browsers.
