# M09 Preflight: Repository & Environment Baseline

**Project:** Multi-Tenant AI Assistant Platform (Chatbot-as-a-Service / CaaS)  
**Date:** November 10, 2026  
**Auditor:** Principal Software Architect & QA Lead  
**Milestone:** M09 — Platform Quality, M08 Security Closure, AI Evaluation & Reliability  

---

## 1. Git Repository State

| Parameter | Verified Value | Reconciliation / Notes |
|---|---|---|
| **Repository Path** | `E:\MM Office\Multi-Tanant-CaaS` | Local NVMe/SSD workspace on Drive E: |
| **Active Branch** | `main` | Verified via `git branch --show-current` |
| **Current HEAD Commit** | `9479847b846aaae43cb8f51e81cf18aaf2646d0f` | Matches reported M08 release commit `9479847` |
| **Upstream Tracking** | `origin/main` | Remote branch at `4f75f68` |
| **Branch Ahead Count** | Ahead by 3 commits | Commits `9595339` (M06), `ad46a44` (M07), `9479847` (M08) |
| **Working Tree Status** | Clean | Verified via `git status --short --branch` |
| **Uncommitted Changes** | 0 files | Working directory completely clean |
| **Diff Check** | Clean | Verified via `git diff --check` (no whitespace/merge errors) |

### Recent Commit Hierarchy
```text
9479847 (HEAD -> main) feat(m08): implement Public Assistant Publishing, Embed Widgets, Developer API, and SDKs
ad46a44 feat(m07): implement Knowledge Studio, Retrieval Playground, BYOK Vault, and Quota Management
9595339 feat(m06): implement Assistant Studio, 12 templates, 5-step wizard, versioning and prompt trust hierarchy
4f75f68 (origin/main) docs(staging): add M05 local UI verification and staging deployment evidence
bc194d0 feat(deployment): M05 UI verification, staging readiness, Render and Vercel blueprints
448431c feat: complete M03.1-M03.3 hardening, CPU semantic embeddings, and M04 Conversational RAG
```

---

## 2. Database & Alembic Schema Baseline

| Parameter | Value | Details |
|---|---|---|
| **Alembic Head** | `0008_assistant_publishing_and_api_keys` | Current active migration head |
| **Migration History Length** | 8 revisions | Full linear chain from `<base>` to `0008` without forks |
| **Database Engines** | SQLite (Dev) & PostgreSQL (Prod) | Local dev uses `backend/data/mmaip_dev.db` |
| **Tables Verified** | 43 relational tables | Includes all M01–M08 entities |

### Alembic Migration Chain
```text
<base>
  └── 0001_initial_core_schema (Core users, tenants, roles, permissions)
        └── 0002_document_ingestion_engine (Documents, versions, chunks, ingestion jobs)
              └── 0003_embeddings_and_vector_stores (Chunk embeddings, retrieval configs)
                    └── 0004_assistants_and_conversations (Assistants, prompts, conversations, citations)
                          └── 0005_add_assistant_byok_encrypted_key (Per-assistant BYOK key)
                                └── 0006_assistant_versions_and_configuration (Assistant versions, templates, config)
                                      └── 0007_provider_credentials_and_usage (BYOK vault, quotas, usage logs)
                                            └── 0008_assistant_publishing_and_api_keys (Head: publications, api keys, sessions)
```

---

## 3. Host System & Hardware Resources

| Resource | Verified Specification | Operational Constraint |
|---|---|---|
| **Operating System** | Windows 10 Pro (Build 19045 / 64-bit) | PowerShell 5.1 / 7.x primary shell |
| **CPU** | Intel Core i3-7100U @ 2.40 GHz (2 Cores, 4 Threads) | Low-power CPU, strict single-threaded or light async workloads |
| **Total Physical RAM** | 8,008,680 KB (7.64 GB) | Physical limit; hard cap at 8 GB |
| **Free Physical RAM** | ~564,800 KB (~550 MB free) | **HIGH RESTRAINT REQUIRED**: Avoid concurrent heavy processes |
| **GPU / Acceleration** | Intel HD Graphics 620 | **No dedicated GPU**. CPU-only inference, embeddings, and tests |
| **Storage Layout** | Drive E: (NVMe/SSD workspace) | Keep venvs, DBs, models, and node_modules on E: |

---

## 4. Runtimes & Dependencies

| Toolchain | Version | Location |
|---|---|---|
| **Python** | Python 3.12.x (64-bit) | `E:\MM Office\Multi-Tanant-CaaS\backend\.venv\` |
| **Node.js** | Node.js v20+ / npm | `frontend/node_modules/` |
| **Next.js** | Next.js 16.0.7 (App Router) | `frontend/package.json` |
| **FastAPI** | FastAPI 0.115+ | Async ASGI server running on Uvicorn |
| **SQLAlchemy** | SQLAlchemy 2.0.x (Async) | Supports asyncpg and aiosqlite |
| **Pydantic** | Pydantic v2.x | Strict validation schemas |
