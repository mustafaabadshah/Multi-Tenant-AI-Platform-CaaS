# Platform Product Vision — Multi-Tenant AI Assistant Platform (Chatbot-as-a-Service)

**Product Vision Status:** Living Reference & Source of Truth  
**Target Architecture:** Modular Monolith (FastAPI + Next.js App Router + PostgreSQL)  
**Security Standard:** Zero-Trust Multi-Tenant Isolation  

---

## 1. Core Vision & Philosophy

The **Multi-Tenant AI Assistant Platform (Chatbot-as-a-Service / CaaS)** is an enterprise-grade, general-purpose system empowering both non-technical creators and organizations to build, configure, test, publish, and integrate knowledge-grounded AI assistants.

The platform is built on three fundamental architectural principles:
1. **User Empowerment without Complexity:** Users should be able to create an assistant, attach textbooks, SOPs, or lecture notes, and test or publish it in minutes without knowing what RAG, vector embeddings, BM25, or cosine similarity mean.
2. **Ironclad Multi-Tenant Isolation:** Zero data leaks between organizations. All entities (assistants, documents, knowledge bases, vector chunks, credentials, conversation histories, and usage logs) are strictly scoped by composite database foreign keys to the authenticated tenant.
3. **Provider Agnosticism & Cost Protection:** Freedom of model choice (Groq, Anthropic, Google Gemini, OpenAI, or optional local routers). Bring-Your-Own-Key (BYOK) encrypted vaults ensure organizations own their billing relationship without unexpected platform expenditures or forced vendor lock-in.

---

## 2. Supported Personas & Product Archetypes

### A. Individuals & Students
- **Exam Preparation & Study Companion:** Upload syllabi, lecture slides, and notes; create an assistant that quizzes the student, clarifies difficult concepts, and strictly cites course notes.
- **Personal Knowledge Hub:** Research paper summarizer, personal notebook assistant, and document analyzer.

### B. Educators & Academic Institutions
- **MCQ & Quiz Generator:** Ingest textbooks and generate curriculum-aligned questions with deterministic answer keys grounded in chapter text.
- **Subject Tutoring Assistant:** Provide 24/7 course assistance to enrolled students with guardrails preventing direct homework completion.

### C. Organizations & Enterprises
- **Internal HR & Employee Handbook Assistant:** Ingest company policies, benefits, and onboarding documentation; department-scoped retrieval prevents unauthorized personnel from accessing restricted executive compensation data.
- **Customer Support Bot:** Publicly published assistant grounded in approved customer documentation, embedded seamlessly into marketing websites with immediate administrative revocation.
- **Operational SOPs & Compliance:** Interactive operational guidance for frontline staff adhering strictly to safety manuals.

### D. Developers & System Integrators
- **External Application Integration:** Provision scoped API keys (`assistant:read`, `assistant:chat`) and embed streaming assistant dialogs into third-party web apps or mobile backends via official lightweight TypeScript and Python SDKs.

---

## 3. End-to-End User Experience Lifecycle

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ 1. Create Asst  │ ──► │ 2. Attach Docs  │ ──► │ 3. Configure &  │ ──► │ 4. Publish or   │ ──► │ 5. Integrate &  │
│ Select Template │     │ Safe Ingestion  │     │ Live Test       │     │ Select Scope    │     │ Monitor Quota   │
└─────────────────┘     └─────────────────┘     └─────────────────┘     └─────────────────┘     └─────────────────┘
```

1. **Create Assistant:** Select from 12 pre-configured templates (e.g. Student Exam Prep, Customer Support, HR Policy) or start custom.
2. **Attach Knowledge:** Upload PDFs, DOCX, TXT, or ingest safe web URLs with automatic text extraction, chunking, and vector indexing.
3. **Configure & Test:** Tune response style and uncertainty behavior in Simple mode or retrieval parameters in Advanced mode. Test immediately in the zero-persistence Studio Preview.
4. **Publish Assistant:** Choose visibility (`Private`, `Workspace Members`, or `Public Web/Embed`). Generate shareable links or embed codes with domain restrictions.
5. **Integrate & Monitor:** Connect external apps via API keys, stream responses, and track token usage against tenant quotas in real time.
