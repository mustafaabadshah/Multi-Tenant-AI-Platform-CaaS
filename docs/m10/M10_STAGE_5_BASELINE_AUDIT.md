# M10 Stage 5 — Baseline Audit Report
**Project:** Multi-Tenant AI Assistant Platform (Chatbot-as-a-Service / CaaS)  
**Workspace:** `E:\MM Office\Multi-Tanant-CaaS`  
**Git Branch:** `main` (HEAD commit: `9479847`)  
**Milestone:** M10 Stage 5  
**Audit Date:** 2026-11-11  

---

## 1. Executive Summary

Milestone M10 Stage 4 established the foundational Woice-inspired light SaaS design system, including centralized CSS variables in `globals.css`, core UI primitives in `components/ui/`, a collapsible application shell (`dashboard/layout.tsx`), and refactored conversational, organizational, and administrative interfaces.

However, a systematic source audit conducted during Stage 0 has revealed critical visual debt:
1. **Root Layout Dark Inheritance:** `frontend/app/layout.tsx` explicitly sets `className="dark"` on `<html>` and `bg-slate-950 text-slate-100` on `<body>`, causing unnested routes (`/login`, `/register`, `/p/*`, `/embed/*`) and modals to inherit dark defaults.
2. **Legacy Dark Authentication:** Both `/login` and `/register` utilize `bg-slate-950`, `bg-slate-900/80`, `border-slate-800`, and `text-slate-100` containers rather than the light SaaS card design.
3. **Assistant Studio Visual Inconsistencies:** `dashboard/assistants/page.tsx`, `AssistantCreationWizard.tsx`, `AssistantWorkspaceView.tsx`, `EvaluationTab.tsx`, and `PublishTab.tsx` feature dark backgrounds, slate modals, and dark card surfaces.
4. **Knowledge Studio Tabs:** `knowledge/page.tsx`, `RetrievalSettingsTab.tsx`, `RetrievalPreviewTab.tsx`, and `IndexStatusTab.tsx` contain legacy dark containers.
5. **Provider Vault & Telemetry:** `dashboard/providers/page.tsx` and `dashboard/observability/page.tsx` use dark slate card backgrounds.
6. **Public & Embed Chat:** `/p/[publicId]` and `/embed/[publicId]` use dark slate backgrounds.

This audit establishes the baseline repository state and defines the remediation plan to achieve 100% global light-theme consistency across all 20 frontend routes, followed by a thorough production reliability audit.

---

## 2. Actual Git State

```text
Branch: main
HEAD Commit: 9479847 feat(m08): implement Public Assistant Publishing, Embed Widgets, Developer API, and SDKs
Prior Commits:
  ad46a44 feat(m07): implement Knowledge Studio, Retrieval Playground, BYOK Vault, and Quota Management
  9595339 feat(m06): implement Assistant Studio, 12 templates, 5-step wizard, versioning and prompt trust hierarchy
  4f75f68 docs(staging): add M05 local UI verification and staging deployment evidence
  bc194d0 feat(deployment): M05 UI verification, staging readiness, Render and Vercel blueprints
```

All working changes from M09 and M10 Stages 1–4 are tracked in the working tree and staging area without conflicts.

---

## 3. Centralized Design System & Tokens

Defined in `frontend/app/globals.css`:
```css
:root {
  --background: #f9fafb;          /* Neutral canvas */
  --background-secondary: #ffffff;/* Clean white surfaces */
  --foreground: #111827;          /* Primary dark text */
  --foreground-secondary: #374151;/* Secondary gray text */
  --card: #ffffff;                /* Card surface */
  --card-foreground: #111827;
  --border: #e5e7eb;              /* Subtle border */
  --border-focus: #2563eb;        /* Focused ring */
  --primary: #2563eb;             /* Modern blue accent */
  --primary-hover: #1d4ed8;
  --primary-light: #eff6ff;
  --accent: #7c3aed;
  --muted: #6b7280;               /* Muted text */
  --muted-light: #f3f4f6;         /* Light hover fills */
  --muted-foreground: #9ca3af;
  --success: #10b981;
  --success-light: #ecfdf5;
  --warning: #f59e0b;
  --warning-light: #fffbeb;
  --danger: #ef4444;
  --danger-light: #fef2f2;
}
```

### Shared UI Component Primitives (`frontend/components/ui/`):
- `Button`: Variants `primary`, `secondary`, `outline`, `ghost`, `danger`; sizes `sm`, `md`, `lg`.
- `Input`: Light input with labels, icons, error hints, focus ring.
- `Card`: White surface (`bg-white`), subtle border (`border-gray-200`), rounded-xl.
- `Badge`: Status badges with subtle tint backgrounds (`gray`, `blue`, `green`, `amber`, `red`, `purple`).
- `Spinner`: Clean SVG spinner (`text-blue-600`).
- `Modal`: Centered light dialog with backdrop blur and escape key handling.
- `ConfirmModal`: Standard confirmation dialog for destructive actions.
- `EmptyState`: Clean empty states with icon, title, description, and action button.
- `StatusIndicator`: Pulse / solid status dots (`active`, `idle`, `error`, `busy`).

---

## 4. Frontend Route & Component Inventory

| Route | File Path | Layout | Current Visual State | Target State |
|---|---|---|---|---|
| `/` | `app/page.tsx` | Root | Spinner with `bg-slate-950` | Clean light spinner (`bg-gray-50`) |
| `/login` | `app/login/page.tsx` | Root | Legacy dark (`bg-slate-950`, `bg-slate-900/80`) | Clean light card (`bg-white`, `border-gray-200`) |
| `/register` | `app/register/page.tsx` | Root | Legacy dark (`bg-slate-950`, `border-slate-800`) | Clean light card (`bg-white`, `border-gray-200`) |
| `/dashboard` | `app/dashboard/page.tsx` | Shell | Clean light Woice-inspired | Maintained |
| `/dashboard/conversations` | `app/dashboard/conversations/page.tsx` | Shell | Clean light Woice-inspired | Maintained (code blocks dark) |
| `/dashboard/assistants` | `app/dashboard/assistants/page.tsx` | Shell | Dark sidebar list & header | Clean light list & studio header |
| `Wizard` | `AssistantCreationWizard.tsx` | Modal | Dark modal (`bg-slate-950`, `border-slate-800`) | Clean light modal (`bg-white`) |
| `Studio View` | `AssistantWorkspaceView.tsx` | Subview | Dark slate tabs & cards | Clean light tabs (`border-gray-200`) |
| `Evaluation` | `EvaluationTab.tsx` | Subview | Dark slate cards & tables | Clean light benchmark cards |
| `Publishing` | `PublishTab.tsx` | Subview | Dark cards & inputs | Clean light checklists & forms |
| `/dashboard/knowledge` | `app/dashboard/knowledge/page.tsx` | Shell | Dark cards & modals | Clean light grid & document inspection |
| `Retrieval Settings` | `RetrievalSettingsTab.tsx` | Subview | Dark slate cards & radio boxes | Clean light configuration cards |
| `Retrieval Preview` | `RetrievalPreviewTab.tsx` | Subview | Dark query box & results | Clean light playground & candidate cards |
| `Index Status` | `IndexStatusTab.tsx` | Subview | Dark status panels | Clean light metrics & job tables |
| `/dashboard/providers` | `app/dashboard/providers/page.tsx` | Shell | Dark BYOK vault & provider cards | Clean light vault tables & modals |
| `/dashboard/observability` | `app/dashboard/observability/page.tsx` | Shell | Dark metric cards & traces table | Clean light telemetry dashboard |
| `/dashboard/departments` | `app/dashboard/departments/page.tsx` | Shell | Clean light Woice-inspired | Maintained |
| `/dashboard/employees` | `app/dashboard/employees/page.tsx` | Shell | Clean light Woice-inspired | Maintained |
| `/dashboard/groups` | `app/dashboard/groups/page.tsx` | Shell | Clean light Woice-inspired | Maintained |
| `/dashboard/workspace` | `app/dashboard/workspace/page.tsx` | Shell | Clean light Woice-inspired | Maintained |
| `/dashboard/audit` | `app/dashboard/audit/page.tsx` | Shell | Clean light Woice-inspired | Maintained (JSON code block dark) |
| `/dashboard/settings` | `app/dashboard/settings/page.tsx` | Shell | Clean light Woice-inspired | Maintained |
| `/p/[publicId]` | `app/p/[publicId]/page.tsx` | Standalone | Dark chat canvas (`bg-slate-950`) | Clean light standalone chat |
| `/embed/[publicId]` | `app/embed/[publicId]/page.tsx` | Iframe | Dark widget canvas (`bg-slate-950`) | Clean light embed widget |

---

## 5. Detailed Visual Debt Findings

Automated regex analysis of the frontend codebase identified **373 lines** across 17 files containing legacy dark classes:

1. **`app/layout.tsx` (1 line):** `<html lang="en" className="dark">` and `<body className="... bg-slate-950 text-slate-100 ...">` forces dark mode at the HTML document level.
2. **`app/page.tsx` (1 line):** Loading redirect view utilizes `bg-slate-950`.
3. **`app/login/page.tsx` (8 lines):** `bg-slate-950`, `bg-slate-900/80`, `border-slate-800`, `bg-red-950/60`, `border-red-800/80`.
4. **`app/register/page.tsx` (9 lines):** `bg-slate-950`, `bg-slate-900/80`, `border-slate-800`, `bg-blue-950/40`.
5. **`app/dashboard/assistants/page.tsx` (49 lines):** `bg-slate-950/80`, `border-slate-800/80`, `bg-slate-900/80`, `text-slate-400`.
6. **`AssistantCreationWizard.tsx` (40 lines):** Step modal container `bg-slate-950`, template cards `bg-slate-950`, preview test pane `bg-slate-950`.
7. **`AssistantWorkspaceView.tsx` (42 lines):** Studio header, settings tabs, version history table in `bg-slate-950` / `bg-slate-900`.
8. **`EvaluationTab.tsx` (22 lines):** Benchmark execution panel, metrics, dataset comparison in dark slate.
9. **`PublishTab.tsx` (30 lines):** Readiness preflight checklist, embed snippet panels, allowed origin inputs in dark slate.
10. **`app/dashboard/knowledge/page.tsx` (96 lines):** Knowledge container grid, drag-and-drop upload zone, document table, document inspector modal.
11. **`RetrievalSettingsTab.tsx` (33 lines):** Retrieval mode selector cards, weight sliders, vector store credential inputs in dark slate.
12. **`RetrievalPreviewTab.tsx` (18 lines):** Search query input, candidate chunk result cards in dark slate.
13. **`IndexStatusTab.tsx` (13 lines):** Collection status summary, chunk stats, embedding job table in dark slate.
14. **`app/dashboard/providers/page.tsx` (59 lines):** BYOK vault credentials table, provider catalog cards, quota progress bars, Add Key modal.
15. **`app/dashboard/observability/page.tsx` (32 lines):** 6 telemetry KPI cards, channel breakdown, provider breakdown, trace explorer table, trace detail drawer.
16. **`app/p/[publicId]/page.tsx` (17 lines):** Standalone public chat view, header, messages, input bar in `bg-slate-950`.
17. **`app/embed/[publicId]/page.tsx` (11 lines):** Embeddable iframe chat widget in `bg-slate-950`.

### Intentional Dark Surfaces (To Be Retained & Documented):
- **Code Highlighting Blocks (`<pre>`):**
  - `app/dashboard/conversations/page.tsx` (Lines 163–164): Code blocks rendered within assistant markdown messages (`bg-gray-900 text-gray-100`).
  - `app/dashboard/audit/page.tsx` (Line 146): Raw JSON payload inspector in audit log drawer (`bg-gray-900 text-gray-100`).
  - `app/dashboard/assistants/PublishTab.tsx`: Code snippet display for `<script>` embed widget tags (`bg-gray-900 text-gray-100`).
- **Modal Backdrop Overlays:**
  - `app/dashboard/layout.tsx`: Mobile drawer overlay (`bg-gray-900/40 backdrop-blur-xs`).
  - `components/ui/Modal.tsx`: Standard modal backdrop (`bg-gray-900/50 backdrop-blur-xs`).

---

## 6. Functional Capabilities to Preserve

All modifications must preserve existing backend integrations:
1. **Authentication & Multi-Tenant Context:** Argon2id password verification, JWT access tokens, workspace switching, multi-tenant session persistence.
2. **Assistant Studio & Lifecycle:** 12 starter templates, 5-step creation wizard, version snapshots, immutable rollback, prompt trust hierarchy.
3. **Knowledge Studio & Retrieval:** PDF/Docx/XLSX/SQL ingestion, OCR, chunking, hybrid Reciprocal Rank Fusion, vector store validation.
4. **Conversations:** Server-Sent Events (SSE) streaming, citation footnotes, source previews, Markdown code blocks with copy.
5. **Organizational Hierarchy:** Departments, employee groups, role-based access control (Owner, Admin, Member, Viewer).
6. **Publishing & Developer Tools:** Public assistants, anonymous visitor sessions, iframe embed widgets, SHA-256 API keys with permission scopes.
7. **BYOK Vault & Quotas:** AES-256 encrypted provider credentials, daily request caps, monthly token budgets.
8. **Observability & Evaluations:** Deterministic benchmarks, Groundedness/MRR evaluation, request telemetry.

---

## 7. Production-Readiness Gap Analysis

| Domain | Current Architecture | Identified Gap / Risk | Proposed M10 Stage 5 Action |
|---|---|---|---|
| **Background Jobs** | In-process FastAPI background tasks + startup recovery (`recover_orphaned_jobs`) | If server crashes mid-ingestion, interrupted jobs are marked `FAILED` at startup; no automatic retry without user intervention | Audit `recovery.py` and document idempotency, crash recovery, and bounded retry strategy |
| **Quota Enforcement** | Database tracking with in-memory `threading.Lock` | Process-local lock does not guarantee distributed atomicity across multiple concurrent server instances | Evaluate database-backed atomic token reservation using `SELECT ... FOR UPDATE` or SQL constraints |
| **Storage Authorization** | Local storage / MinIO with tenant-prefixed keys | Object key prefix alone does not replace backend authorization | Verify backend ACL checks on all file download, preview, and delete operations |
| **Backups & Recovery** | Docker compose dump script (`scripts/backup_db.sh`) | Covers PostgreSQL only; does not package uploaded artifacts, MinIO objects, or Qdrant snapshots | Document unified multi-service backup & restore procedure |
| **PostgreSQL Readiness** | Alembic migrations (0001–0009); tested on SQLite | SQLite test suite does not validate PostgreSQL UUID, JSONB, or FTS dialect nuances | Verify migration chain consistency and document PostgreSQL production deployment requirements |
| **Observability** | In-memory RingBuffer (10,000 traces) with redaction | Telemetry lost upon container restart; not durable | Document OpenTelemetry export readiness and verify secret redaction guardrails |
| **Deployment Blueprints** | Render (`render.yaml`) & Vercel (`vercel.json`) | Render free tier has ephemeral disk; uploads will be wiped on restart unless S3/MinIO is configured | Document production storage and database configuration requirements in deployment guide |

---

## 8. Proposed Remediation Order

1. **Step 1 (Root & Auth):** Fix `layout.tsx`, `page.tsx`, `login/page.tsx`, and `register/page.tsx` to establish the light theme foundation.
2. **Step 2 (Assistant Studio):** Refactor `assistants/page.tsx`, `AssistantCreationWizard.tsx`, `AssistantWorkspaceView.tsx`, `EvaluationTab.tsx`, and `PublishTab.tsx`.
3. **Step 3 (Knowledge Studio):** Refactor `knowledge/page.tsx`, `RetrievalSettingsTab.tsx`, `RetrievalPreviewTab.tsx`, and `IndexStatusTab.tsx`.
4. **Step 4 (Providers & Observability):** Refactor `providers/page.tsx` and `observability/page.tsx`.
5. **Step 5 (Public & Embed Chat):** Refactor `p/[publicId]/page.tsx` and `embed/[publicId]/page.tsx`.
6. **Step 6 (Theme Scanner & Verification):** Run automated theme scanner to confirm zero unintended dark classes remain.
7. **Step 7 (Automated Functional & Regression Verification):** Run `tsc --noEmit`, Next.js production build, TypeScript SDK check, and full backend pytest suite.
8. **Step 8 (Production Reliability & Security Audits):** Complete reliability, security, and deployment documentation.
