# M28.8 Release Readiness & Pre-Deployment Audit

**Milestone:** M28.8  
**Date:** November 19, 2026  
**Status:** Verification Complete — Local Work Ready — Staging Approval Required  
**Verdict:** `M28_8_LOCAL_PASS_STAGING_APPROVAL_REQUIRED`

---

## 1. Readiness Inventory

| Check | Requirement | Status |
|---|---|---|
| **Git Safety** | Remote HEAD `648b9f6` preserved. Zero unapproved commits or pushes. | PASSED |
| **M28.7 Continuity** | Web extraction, boilerplate filtering, cache contract, context expansion preserved. | PASSED |
| **Unified Shell** | 4-destination core + 2 management + collapsible advanced navigation. | PASSED |
| **Task-Oriented Home** | Direct assistant selector + prompt composer + recent conversation resumption. | PASSED |
| **Primary Chat Canvas** | SearchParams hydration (`assistantId`, `draft`), Add Webpage modal, speech controls. | PASSED |
| **Hybrid Assistants** | Clean list/cards + detail view; duplicate chat drawer removed. | PASSED |
| **Simplified Wizard** | 1-screen creation (Name + Purpose) + progressive advanced disclosure. | PASSED |
| **Agent Skill** | `.agents/skills/caas-product-ux/SKILL.md` created with YAML frontmatter. | PASSED |
| **Frontend Tests** | 20/20 passed in 4.59s. | PASSED |
| **TypeScript Check** | Exit code 0 (`npx tsc --noEmit`). | PASSED |
| **Production Build** | Exit code 0 (`npm run build`). | PASSED |
| **Backend Regression** | 80/80 passed in 16.00s. | PASSED |
| **Database Migrations** | 0 new migrations required (Alembic `0018` verified). | PASSED |

---

## 2. Release Allowlist of Changed Files

```
# Core Navigation & Layout
frontend/app/dashboard/layout.tsx

# Overview / Home
frontend/app/dashboard/page.tsx

# Chat Studio
frontend/app/dashboard/conversations/page.tsx

# Assistant Management & Wizard
frontend/app/dashboard/assistants/page.tsx
frontend/app/dashboard/assistants/AssistantCreationWizard.tsx

# API Types (Citations)
frontend/lib/api.ts

# Tests & Skills
frontend/lib/__tests__/workspace-ux.test.ts
.agents/skills/caas-product-ux/SKILL.md

# Preserved M28.7 Backend Fixes
backend/app/assistant_runtime/runtime.py
backend/app/main.py
backend/app/services/web/extractor.py
backend/app/services/web/reader.py
backend/tests/test_m28_7_web_extraction_and_ux.py
```
