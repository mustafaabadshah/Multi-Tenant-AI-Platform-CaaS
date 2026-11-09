# Platform System Architecture — Modular Monolith Standard

**System Architecture Status:** Target Architecture for M08 and Beyond  
**Architecture Pattern:** Modular Monolith (Python FastAPI + Next.js App Router + PostgreSQL)  

---

## 1. High-Level System Architecture Diagram

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 Client Presentation Layer                              │
│                                                                                        │
│   Next.js 16 (App Router)          Public Web Page              Host Web Sites         │
│   Dashboard (Linear Style)         (/p/[publicId])              (Embed Iframe Widget)  │
│             │                             │                              │             │
└─────────────┼─────────────────────────────┼──────────────────────────────┼─────────────┘
              │                             │                              │
              │ REST / SSE                  │ REST / SSE                   │ REST / SSE
              ▼                             ▼                              ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                           FastAPI Gateway & Security Boundary                          │
│                                                                                        │
│  - JWT Bearer Authentication                 - Opaque Public ID Resolver               │
│  - Tenant Membership Validation              - Allowed Domain / Origin Filter          │
│  - RBAC & Permission Scopes                  - IP & Session Rate Limiter               │
│  - Server-Side Quota Guard (Pre-Check)       - Secret Key Hasher (SHA-256)             │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              Core Business Domain Services                             │
│                                                                                        │
│  ┌───────────────────────┐  ┌───────────────────────┐  ┌────────────────────────────┐  │
│  │   Assistant Studio    │  │   Knowledge Studio    │  │    Provider BYOK Vault     │  │
│  │ - 12 Starter Registry │  │ - Multi-Parser Ingest │  │ - Fernet Symmetric Crypto  │  │
│  │ - Version Snapshots   │  │ - Safe URL Ingestion  │  │ - Provider Catalog         │  │
│  │ - Forward Rollback    │  │ - Chunk Provenance    │  │ - Key Lifecycle & Masking  │  │
│  └───────────────────────┘  └───────────────────────┘  └────────────────────────────┘  │
│                                           │                                            │
│  ┌────────────────────────────────────────┴─────────────────────────────────────────┐  │
│  │                           Unified Assistant Runtime                              │  │
│  │ - 4-Tier Prompt Assembly Engine (Platform Guardrails -> Instructions -> Context)│  │
│  │ - Authorized Retrieval Orchestrator (Lexical ts_rank_cd, Semantic, Hybrid RRF)  │  │
│  │ - Dynamic Provider Dispatch (Groq, Anthropic, Gemini, OpenAI, Mock)             │  │
│  │ - Real-Time Server-Sent Events (SSE) Token Streaming                            │  │
│  │ - Atomic Usage Logging (ProviderUsageLog)                                       │  │
│  └──────────────────────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               Persistent Storage Tier                                  │
│                                                                                        │
│  PostgreSQL (Relational Source of Truth)        Vector Storage (pgvector / Qdrant)     │
│  - Tenants, Users, Memberships, Roles           - Document Chunk Embeddings            │
│  - Assistants, Versions, Publications           - HNSW Cosine Distance Indexing        │
│  - Documents, Chunks, Full-Text tsvector        - Partitioned by tenant_id filter      │
│  - BYOK Credentials, Usage Logs, Audit Logs                                            │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Architectural Principles & Non-Negotiables

1. **Modular Monolith Integrity:** The entire backend resides inside `backend/app/`. Do not introduce microservices, distributed RPC, or independent daemon runtimes until enterprise throughput demands it.
2. **Single Assistant Runtime:** Internal Studio chat, public web page chat, embed widget chat, and developer API chat ALL execute through the single unified `AssistantRuntime.stream_chat()` pipeline. There are zero separate public inference implementations.
3. **Database-Enforced Composite Isolation:** Every query on tenant-owned entities MUST filter explicitly by `tenant_id == ctx.tenant.id`. Public access tokens and API keys are mapped to their respective tenant and assistant before inference begins.
4. **Hardware & Cost Efficiency:** Operates within 8 GB RAM on CPU without requiring dedicated GPUs, mandatory Redis instances, or external paid gateways.
