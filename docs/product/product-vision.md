# Product Vision — Multi-Tenant AI Assistant Platform (Chatbot-as-a-Service / CaaS)

**Document Version:** 1.0.0  
**Status:** Architecture Proposal & Reassessment  
**Baseline Commit:** `4f75f68`  
**Target Design Aesthetic:** Linear × Apple Notes (Restrained black, crisp white, soft neutrals, restrained light blue accent)  
**Target System Paradigm:** Modular Monolith, API-first, Multi-Tenant, Provider-Agnostic, Free-First  

---

## 1. Executive Summary & Core Purpose

The Multi-Tenant AI Assistant Platform is a **Chatbot-as-a-Service (CaaS)** solution designed to democratize the creation, customization, operation, evaluation, and publishing of purpose-built AI assistants.

The product addresses a fundamental market divide:
1. **Consumer & Non-Technical Users (Students, Teachers, Small Businesses, Solo Practitioners):** Need immediate utility without confronting vector dimensions, chunking strategies, RAG retrieval scores, token windows, or API key configuration.
2. **Technical Users & Enterprise Operators (AI Engineers, Team Leads, Compliance Officers):** Demand granular control over model routing, temperature, Top-K retrieval, hybrid fusion weights, chunk boundaries, BYOK credentials, data isolation, and trace observability.

Rather than fragmenting into separate point solutions, the platform unifies these personas through a single, coherent design philosophy:

> **"Simple by default, powerful when needed."**  
> A non-technical user can create and publish an assistant in under 60 seconds using purpose-driven templates. A technical engineer can expand the advanced drawer to tune BM25/Dense hybrid fusion weights, inspect chunk hashes, and benchmark retrieval recall.

---

## 2. The Five Connected Product Experiences

The platform is structured around five cohesive, interconnected lifecycles:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                             THE CAAS LIFECYCLE                              │
├─────────────┬─────────────┬──────────────┬──────────────┬───────────────────┤
│  1. CREATE  │2. KNOWLEDGE │ 3. CONFIGURE │    4. USE    │5. PUBLISH & MANAGE│
│             │             │              │              │                   │
│ • Purpose   │ • Multi-    │ • Context &  │ • Streaming  │ • Shareable Link  │
│   Templates │   Source    │   Behavior   │   Chat       │ • Embed Widget    │
│ • Guided    │ • Chunk     │ • BYOK &     │ • Citations  │ • API Keys        │
│   Wizard    │   Inspector │   Registry   │ • Attach-    │ • Quota & Budget  │
│ • Simple vs │ • Retrieval │ • Hybrid RAG │   ments      │ • Evaluations     │
│   Advanced  │   Playground│ • Guardrails │ • History    │ • Observability   │
└─────────────┴─────────────┴──────────────┴──────────────┴───────────────────┘
```

### Experience 1: Create (Assistant Studio)
- **Guided Setup:** Users create assistants with understandable options: Name, Intended Purpose, Audience, Language, Tone, and Response Style.
- **Purpose Templates:** Extensible starting blueprints across:
  - **Education:** Exam-prep assistant, textbook Q&A, MCQ generator, subject tutor, study guide builder.
  - **Business:** Company handbook & HR onboarding, customer support, internal SOP & legal compliance, sales enablement.
  - **Personal & Professional:** Personal document vault, academic research assistant, technical documentation assistant.
  - **Sports & Specialized:** Coaching playbook assistant, league regulations, domain-specific FAQ.
- **Extensible Architecture:** Templates are database-driven schemas, not hardcoded frontend forks.

### Experience 2: Knowledge & Retrieval Studio
- **Multi-Source Ingestion:** Ingest documents (PDF, DOCX, XLSX, PPTX, CSV, JSON, SQL with AST analysis, TXT, Markdown) and securely crawled web URLs.
- **Processing Transparency:** Real-time visibility into the ingestion state: `UPLOADED → VALIDATING → PARSING → OCR → CHUNKING → EMBEDDING → INDEXING → READY`.
- **Chunk Inspection:** Visual verification of chunk boundaries, heading provenance, character/token counts, and hash identities.
- **Retrieval Playground:** Test search queries interactively with score inspection (BM25 vs. dense vs. fused RRF) before attaching knowledge to an assistant.

### Experience 3: Configure (Model & Integration Studio)
- **BYOK (Bring Your Own Key):** Users and organizations connect their own API keys for OpenAI, Anthropic, Google Gemini, Groq, OpenRouter, Mistral, and local endpoints.
- **Zero Lock-In & Zero Silent Upgrades:** Credentials are encrypted with AES-256-GCM. Paid models are never invoked without explicit user configuration.
- **Model Registry & Capabilities:** Context limits, tool-calling flags, token costs, and streaming capabilities are cataloged and enforced.
- **Routing & Policy:** Configurable fallback routing (e.g. primary fast tier → secondary fallback) with quota safeguards.

### Experience 4: Use (Complete Chat Experience)
- **Fluid Interaction:** Real-time Server-Sent Events (SSE) streaming with immediate markdown rendering and token-by-token display.
- **Verified Citations:** Grounded citations linked to source chunks, with visual PDF highlight bounds (preserving coordinate provenance without synthetic spoofing).
- **Session Control:** Persistent conversations, multi-turn context budgeting, rename, archive, search, and message regeneration.
- **Turn Attachments:** Ephemeral file attachments for single conversations without polluting permanent knowledge bases.

### Experience 5: Publish & Manage (Administration & Observability)
- **Controlled Visibility:** Private (personal), Workspace-only (team/department), or Public (external).
- **Public Distribution:** Shareable web links, customizable embeddable chat widgets (`<script>` / `<iframe>`), and tenant-scoped developer API keys.
- **Evaluation Studio:** Automated ground-truth testing (faithfulness, retrieval recall, citation precision, latency, and cost).
- **Tenant Administration & Auditing:** Comprehensive RBAC (Owner, Admin, Member, Auditor), department/group access control, token quotas, and immutable audit logging.

---

## 3. User Personas & Dual-Mode Philosophy

| Persona | Primary Needs | Default Experience | Advanced Capabilities Used |
|---|---|---|---|
| **Undergraduate Student** | Study notes, textbook Q&A, exam prep, flashcards | **Simple Mode** (Pick "Exam Prep" template, drag & drop syllabus PDF, start chatting) | None. High-level tone selector ("Explain like I'm a beginner"). |
| **High School Teacher** | Generate quizzes, MCQs with rubrics, course FAQ bot | **Simple Mode** (Pick "MCQ Generator" template, upload lesson notes, export Q&A) | Output formatting controls, citation strictness. |
| **Small Business Owner** | Public website customer support bot, lead qualifier | **Simple Mode** (Pick "Customer Support" template, enter website URL, copy embed code) | Custom branding, allowed domains, daily conversation limits. |
| **Enterprise HR Lead** | Internal employee policy bot with department permissions | **Advanced Mode** (Select department ACL, configure retrieval mode, link handbook) | Department-level document ACLs, audit logs, employee group assignment. |
| **AI / Software Engineer** | High-performance RAG pipeline, custom endpoints, BYOK | **Advanced Mode** (Configure pgvector vs. Qdrant, hybrid RRF weights, evaluate recall) | Chunking strategy, Top-K, similarity thresholds, Phoenix traces, custom BYOK endpoints. |

---

## 4. Architectural Principles

1. **Multi-Tenant Isolation is Sacred:** Every single query, document, vector, chunk, conversation, and API key is strictly scoped by `tenant_id`. Cross-tenant data leakage is prevented at both the database level (foreign keys and unique composite constraints) and the service layer.
2. **Provider Agnostic & Free-First:** The platform operates fully with CPU embeddings (FastEmbed / all-MiniLM-L6-v2), PostgreSQL FTS (vectorless), and free-tier API endpoints. Paid API keys or external vector databases are strictly optional.
3. **Transparent Provenance:** No hallucinations without consequence. The system distinguishes exact source-extracted text from synthetic fallback positions and provides clickable, inspectable citations.
4. **Security by Construction:** Static parsing for SQL files (no raw execution), SSRF/DNS rebinding defenses for web crawlers, AES-256-GCM envelope encryption for stored API keys, and server-side RBAC validation on every route.
5. **Aesthetic Discipline:** Linear-style density, Apple Notes clarity, ultra-fast UI interactions, dark/light coherence, and zero visual clutter.
