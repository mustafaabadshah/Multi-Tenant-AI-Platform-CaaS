# M20.3 — Git Release Integration Report

**Document Version:** 1.0.0  
**Date:** 2026-11-16  
**Workspace:** `E:\MM Office\Multi-Tanant-CaaS`  
**Target Branch:** `main`  
**Current Local HEAD:** `318fa3e665a0a1683c8d9768a40779b61eb1b4ec`  
**Remote Origin HEAD:** `c152ccc047ff5b83122fcb6f9d5dcc7b35f15266`  

---

## 1. Lineage & Ancestry Reconciliation

- **Local Commit:** `318fa3e` ("docs: update README with Observability 2.0...")
- **Remote Commit:** `c152ccc` ("Update README.md")
- **Merge Base:** `318fa3e665a0a1683c8d9768a40779b61eb1b4ec`
- **Reconciliation Finding:** `318fa3e` is an exact direct ancestor of `c152ccc`. Remote commit `c152ccc` modified only `README.md` (re-positioning the product status section). The working tree has no uncommitted edits to `README.md`, making the fast-forward / merge entirely conflict-free.

---

## 2. Release File Allowlist

### Modified Files (43 files)
```text
backend/app/api/deps.py
backend/app/api/v1/assistants.py
backend/app/api/v1/auth.py
backend/app/api/v1/groups.py
backend/app/api/v1/members.py
backend/app/api/v1/observability.py
backend/app/api/v1/router.py
backend/app/api/v1/tools.py
backend/app/assistant_runtime/runtime.py
backend/app/core/config.py
backend/app/core/rate_limit.py
backend/app/core/security.py
backend/app/evaluation/metrics.py
backend/app/evaluation/starter_benchmarks.py
backend/app/llm/base.py
backend/app/llm/providers/mock_provider.py
backend/app/llm/providers/openai_provider.py
backend/app/models/__init__.py
backend/app/models/administration.py
backend/app/models/assistant.py
backend/app/models/invitation.py
backend/app/models/user.py
backend/app/repositories/assistant_repository.py
backend/app/repositories/group_repository.py
backend/app/schemas/assistant.py
backend/app/schemas/auth.py
backend/app/schemas/evaluation.py
backend/app/schemas/group.py
backend/app/schemas/member.py
backend/app/services/evaluation_service.py
backend/app/services/invitation_service.py
backend/app/services/quota_service.py
backend/app/storage/local.py
backend/app/storage/s3.py
backend/pyproject.toml
backend/tests/test_evaluation.py
backend/tests/test_m11_invitation_acceptance.py
backend/tests/test_observability.py
frontend/app/dashboard/assistants/AssistantWorkspaceView.tsx
frontend/app/dashboard/conversations/page.tsx
frontend/app/dashboard/layout.tsx
frontend/lib/api.ts
render.yaml
```

### Untracked Files to Include (25 files)
```text
backend/alembic/versions/0012_m16_auth_sessions_and_invitations.py
backend/alembic/versions/0013_m17_durable_quota_reservations.py
backend/alembic/versions/0014_m19_tool_registry.py
backend/alembic/versions/0015_m20_mcp_agentic_runtime.py
backend/alembic/versions/0016_m20_2_assistant_tools_config.py
backend/app/api/v1/approvals.py
backend/app/api/v1/mcp.py
backend/app/models/mcp.py
backend/app/models/session.py
backend/app/models/tool.py
backend/app/schemas/approval.py
backend/app/schemas/mcp.py
backend/app/schemas/tool.py
backend/app/services/mcp/
backend/app/services/session_service.py
backend/app/services/tools/
backend/tests/test_m16_security.py
backend/tests/test_m17_reliability.py
backend/tests/test_m18_rag_evaluation.py
backend/tests/test_m19_tools.py
backend/tests/test_m20_1_real_mcp_and_approvals.py
backend/tests/test_m20_2_integrations_and_release.py
backend/tests/test_m20_mcp_agentic.py
backend/tests/test_m20_migration_compatibility.py
frontend/app/dashboard/integrations/page.tsx
frontend/app/dashboard/tools/page.tsx
docs/m20/
```

### Files Explicitly Excluded
- `.agents/`
- `.kilo/`
- `.neon`
- `skills-lock.json`
- `.env*` local configuration files
- Virtual environments (`.venv/`)
- Temporary cache files (`__pycache__/`, `.pytest_cache/`, `.next/`)

---

## 3. Planned Release Commit Message
```text
feat(platform): release M16-M20 secure sessions, durable quotas, evaluations, tools and MCP integrations

- M16: Add server-side sessions, refresh token rotation, and coherent token-based invitations
- M17: Add durable quota reservations, tracer persistence, and client IP rate limiting
- M18: Add RAG quality evaluations, mathematical metrics (NDCG, MRR, Precision@K), and starter benchmarks
- M19: Add tool registry, outbound SSRF security validation, and employee groups
- M20: Add MCP client, streamable HTTP session support, and human-in-the-loop approval service
- M20.2: Add MCP Connections Workspace, Custom Tools Registry, Assistant Tools tab, and in-chat approval cards
- Alembic: Extend linear migration DAG 0011 -> 0016 (tools_config on assistants)
```
