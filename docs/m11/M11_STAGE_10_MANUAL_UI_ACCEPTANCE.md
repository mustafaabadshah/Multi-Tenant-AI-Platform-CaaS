# M11 Stage 10 — Manual UI Acceptance Handoff

| Field | Value |
|---|---|
| Milestone | M11 — Manual UI Acceptance |
| Stage | 10 — Manual UI Acceptance Handoff |
| Repository | `E:\MM Office\Multi-Tanant-CaaS` |
| Baseline inspected | `fdb1246` on `main` (read-only) |
| Inspection date | 2026-11-12 |
| Method | Static, read-only source inspection of `frontend/app/**` and `frontend/lib/**`; backend consulted only to verify public/embed route provenance |
| Manual acceptance status | **PENDING — USER RESPONSIBILITY** |
| Browser automation | **None performed** |
| Screenshots / visual verification | **None performed** |
| Code changes | **None** |
| Git mutations | **None** |

> **Status statement**
>
> Manual UI acceptance for M11 is **PENDING**. This document is a source-grounded handoff checklist for a human tester. No browser was launched, no route was rendered, no screenshot was captured, no visual or responsive behavior was verified, and no browser automation was run during this phase. Results below must be filled in by the tester against a running environment.

---

## 1. Scope and method

- Routes and interactive elements were derived from the actual App Router tree under `frontend/app/` (17 page routes).
- Expected behavior is grounded in the page source and the API client (`frontend/lib/api.ts`), not in runtime observation.
- Backend URL and public/embed provenance were checked only where needed to define prerequisites and known integration risks.
- Items marked **Watch-out** are source-level observations that the tester should explicitly probe; they are not runtime-confirmed failures.
- Seed-dependent checks are marked **SEED** in the checklist.

---

## 2. Actual route inventory

All routes below exist in source. There are no `route.ts` handlers, middleware, or rewrites under `frontend/app/`, and `next.config.ts` defines no `rewrites`/`redirects` for API or embed paths.

| # | Route | Source file | Access | Purpose and key interactive elements |
|---|---|---|---|---|
| 1 | `/` | `frontend/app/page.tsx` | Public | Boot redirect: authenticated → `/dashboard`; unauthenticated → `/login`; full-screen spinner |
| 2 | `/login` | `frontend/app/login/page.tsx` | Public | Email/password form, inline error banner, submitting spinner, quick-fill demo buttons (`owner_a@companya.com`, `owner_b@companyb.com`), link to `/register` |
| 3 | `/register` | `frontend/app/register/page.tsx` | Public | Full name, email, password (min 8), Individual/Organization selector, conditional organization name, inline error, submit, link to `/login` |
| 4 | `/dashboard` | `frontend/app/dashboard/page.tsx` | Client-guarded | Metrics cards (Knowledge Bases, AI Assistants, Conversations, Team Members), Quick Actions links, recent audit activity list / empty state |
| 5 | `/dashboard/assistants` | `frontend/app/dashboard/assistants/page.tsx` | Client-guarded | Assistant Studio split view: assistant search/list, New Assistant wizard, conversation list (new/rename/delete), Workspace & Versions / Chat Sandbox switch, streaming chat, copy/retry, citation inspector modal, 5-step creation wizard |
| 6 | `/dashboard/knowledge` | `frontend/app/dashboard/knowledge/page.tsx` | Client-guarded | KB grid, create/edit/delete modals, document dropzone and file picker, multi-file queue, Upload & Ingest, URL ingestion modal, documents table with status/pages/chunks, inspect modal (Overview / Extracted Text / Chunks / Processing History), Pipeline Config modal; tabs Retrieval & Vectors, Search Sandbox, Index Status |
| 7 | `/dashboard/conversations` | `frontend/app/dashboard/conversations/page.tsx` | Client-guarded | Conversation list, assistant filter, search, New Chat, rename inline, delete confirmation modal, streaming chat, sources tray, citation inspection modal, empty state |
| 8 | `/dashboard/providers` | `frontend/app/dashboard/providers/page.tsx` | Client-guarded | BYOK Vault / Provider Directory / Usage tabs, add credential modal, test, rotate, revoke, delete, masked secrets, health status, token usage cards |
| 9 | `/dashboard/observability` | `frontend/app/dashboard/observability/page.tsx` | Client-guarded | Telemetry metric cards, trace search, status/channel filters, trace table, trace detail modal with execution spans |
| 10 | `/dashboard/settings` | `frontend/app/dashboard/settings/page.tsx` | Client-guarded | Infrastructure & Quotas tab; Developer API Keys tab (create key modal with scopes/expiry, one-time secret banner, copy, key table, revoke) |
| 11 | `/dashboard/audit` | `frontend/app/dashboard/audit/page.tsx` | Client-guarded | Audit table (timestamp, action, actor, resource, IP), Inspect payload modal with JSON, empty state |
| 12 | `/dashboard/workspace` | `frontend/app/dashboard/workspace/page.tsx` | Client-guarded | Read-only Organization Profile: legal name, domain, tax ID, role, tenant boundary notice |
| 13 | `/dashboard/departments` | `frontend/app/dashboard/departments/page.tsx` | Client-guarded | Department cards, create modal, delete with confirmation, member count, empty state |
| 14 | `/dashboard/employees` | `frontend/app/dashboard/employees/page.tsx` | Client-guarded | Member table, search, Invite Member modal (email/role/department/title), remove member, empty state |
| 15 | `/dashboard/groups` | `frontend/app/dashboard/groups/page.tsx` | Client-guarded | Employee group cards, create modal with optional department, delete, member count, empty state |
| 16 | `/p/[publicId]` | `frontend/app/p/[publicId]/page.tsx` | Public | Standalone public chat: assistant metadata, greeting, streaming chat, Markdown, expandable citations, unavailable/error state, brand color |
| 17 | `/embed/[publicId]` | `frontend/app/embed/[publicId]/page.tsx` | Public | Compact iframe widget: branded header, minimize postMessage, streaming chat, expandable citations, unavailable state |

### 2.1 Routes that do not exist (deep links / management pages)

| Missing route | Observation | Impact |
|---|---|---|
| `/dashboard/assistants/[id]` | Assistant selection is internal state in the split view; no URL per assistant | No deep link, bookmark, or refresh-to-same-assistant; no shareable assistant URL |
| `/dashboard/knowledge/[id]` | KB detail is internal state; no URL per KB | No deep link to a KB, its documents, or index status |
| `/dashboard/conversations/[id]` | Active conversation is internal state only | No shareable chat URL; refresh selects the first conversation returned |
| `/dashboard/publications` | Publishing is configured per assistant under the Publish & Embed tab | No consolidated publication inventory |
| `/dashboard/profile` | User identity/password settings are not exposed | No self-service profile or password change UI |
| `/p` or public directory | Only `/p/[publicId]` exists | No public assistant index (by design) |
| `frontend/app/api/...` | No Next.js API routes or rewrites | The copied embed script URL assumes an external same-origin proxy (see M-02) |

---

## 3. Environment prerequisites

### 3.1 URLs and configuration

| Item | Local value | Deployed value | Notes |
|---|---|---|---|
| Backend origin | `http://127.0.0.1:8000` | TBD — record before execution | FastAPI; all endpoints under `/api/v1` |
| Backend health | `http://127.0.0.1:8000/health` | TBD | Must return healthy before testing |
| OpenAPI docs | `http://127.0.0.1:8000/docs` | TBD | Useful for reproducing API-level negative checks |
| Frontend URL | `http://localhost:3000` | TBD — record before execution | Next.js App Router |
| API base env | `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000` | Same origin-only pattern | Client appends `/api/v1`; **do not include `/api/v1` in this value** |
| Alternate env | `NEXT_PUBLIC_API_URL` | Same | Fallback only; same origin-only rule |
| Backend `FRONTEND_URL` | `http://localhost:3000` | Deployed frontend URL | Used by public/embed metadata |
| Backend `BACKEND_URL` | `http://localhost:8000` | Deployed backend URL | Used by `embed.js` metadata |
| CORS | Backend must allow the frontend origin | Must allow deployed frontend origin | Verify preflight/login works |
| OmniRoute | `http://localhost:20128/v1`, model `auto` | Per environment | Required only for real inference; `mock` provider can substitute for deterministic checks |

> **Watch-out — runbook mismatch (M-13):** `docs/runbooks/local-development.md` shows `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000/api/v1`. The client (`frontend/lib/api.ts:1-40`) appends `/api/v1` itself, so this value produces `/api/v1/api/v1/...` and blocks login. Use the origin only.

### 3.2 Test accounts

| Account | Credentials | Availability |
|---|---|---|
| Tenant A demo | `owner_a@companya.com` / `Password123!` | Quick-fill exists on `/login`, but these users are created by `backend/tests/conftest.py`, **not by an application seed script**. Do not assume they exist in a manually migrated database. |
| Tenant B demo | `owner_b@companyb.com` / `Password123!` | Same caveat as above |
| Fresh Tenant A | Register via `/register` with a unique email | Recommended baseline; creates a workspace and tenant-owner membership |
| Fresh Tenant B | Register in a separate incognito profile with a different email | Required for cross-tenant negative checks |
| Second workspace for A | Create via workspace dropdown → New Workspace | Required for workspace-switching checks without a second user |

- Password minimum is 8 characters (`/register` input `minLength={8}`).
- The dashboard has no account/profile screen; create accounts before the run and record them in a test log.
- Never use shared production accounts.

### 3.3 Provider-key policy

- **Do not use production provider keys.** Use one disposable key only if the BYOK health check requires a real provider, or use OmniRoute / `mock` instead.
- BYOK keys are stored encrypted (Fernet) and returned masked; plaintext must never appear in API responses, screenshots, logs, or this document.
- If a key is visible on screen during evidence capture, mask it before attaching evidence.
- Revoke/delete any disposable key immediately after the run.
- OmniRoute is the default gateway (`llm_provider = omniroute`, model `auto`); `mock` is available in the assistant Advanced Mode for offline deterministic checks.

### 3.4 Browser and viewport matrix

| Profile | Viewport | Purpose |
|---|---|---|
| Desktop Chromium (latest) | 1440 × 900, 100% zoom | Primary functional pass |
| Mobile Chromium emulation | 390 × 844 | Responsive/mobile checks |
| Tablet width | 768 × 1024 | Split-pane and table behavior |
| Optional second browser | Firefox or WebKit latest | Smoke only (login, dashboard, chat, public page) |

Use a clean profile or incognito for public/unauthenticated checks. Disable extensions that alter layout or block clipboard access.

### 3.5 Seed data required

| Seed item | Required for | Suggested fixture |
|---|---|---|
| Two tenants/workspaces with distinct names | AC-03, cross-tenant negatives | Tenant A and Tenant B, each with recognizable prefix |
| Tenant A user + Tenant B user | AC-03, AC-18 | Two accounts, each member of only its own tenant |
| Knowledge base A with indexed documents | AC-06–AC-10 | One KB named `M11 Acceptance KB` |
| Multi-page PDF with distinct page content | AC-07, AC-10 | ≥3 pages; known phrase on page 2 or 3 |
| DOCX, TXT, MD files | AC-07 | Small, valid files with unique phrases |
| Assistant connected to KB A | AC-04, AC-05, AC-09, AC-10 | Named `M11 Acceptance Assistant`, model `omniroute`/`auto` or `mock` |
| Published public assistant | AC-14 | Visibility PUBLIC, greeting and brand color set |
| Existing conversation with messages | AC-12 | At least two turns, preferably with citations |
| Optional BYOK credential | AC-11 | Disposable test key or skip if only mock/OmniRoute is used |
| Audit events | AC-02, AC-11, AC-16 | Generated by the setup actions above |
| Corrupted or unsupported file | AC-07, AC-08, AC-16 | Optional; for FAILED/reprocess checks |

---

## 4. Manual acceptance checklist — 18 required areas

Legend: **SEED** = requires seeded data; **NEG** = negative/abuse check; **WATCH** = source-level risk to probe explicitly.

### AC-01 — Login and registration (5 checks)

| ID | Exact action (URL + UI steps) | Expected result | Evidence to capture |
|---|---|---|---|
| AC-01.1 | Open `/register`; choose **Organization**; fill Full Name, unique email, password ≥8, Company name; click **Create Workspace**. | Account and organization workspace created; token stored; redirect to `/dashboard`; header/sidebar show the organization name and `ORGANIZATION`; user footer shows name/email and tenant-owner role. | Screenshot of dashboard header + URL; network `201` from `/auth/register` if visible. |
| AC-01.2 | Open `/register` in a clean profile; choose **Individual**; leave organization name absent; submit. | Individual workspace created; dashboard loads; tenant type `INDIVIDUAL`; no organization field required. | Screenshot of header/type badge and dashboard. |
| AC-01.3 | Open `/login`; enter the registered email/password; click **Sign In**. | Successful login; redirect to `/dashboard`; no error banner; workspace data loads. | Screenshot after redirect; optional network `200`. |
| AC-01.4 | Open `/login`; enter a valid email with a wrong password; submit. **NEG** | Red inline error appears; user stays on `/login`; no token is stored; no dashboard access. | Screenshot of error banner and URL. |
| AC-01.5 | Open `/register`; submit with an email already registered. **NEG** | Clear duplicate-account error; no second workspace/user created; form remains editable. | Screenshot of error; note exact message. |

### AC-02 — Dashboard and navigation (4 checks)

| ID | Exact action (URL + UI steps) | Expected result | Evidence to capture |
|---|---|---|---|
| AC-02.1 | Log in and open `/dashboard`. | Four metric cards render with numeric values (not blank/spinner after load); Recent Activity shows entries or a descriptive empty state; Quick Actions panel is visible. | Screenshot of full dashboard; note values. |
| AC-02.2 | Click every sidebar item: Overview, Assistants, Knowledge, Conversations, Observability, Employees, Departments, Groups, Organization, Providers & Keys, Audit Logs, Settings. | Each route loads its expected page without 404, blank screen, or uncaught error; active item is highlighted; mobile drawer closes after navigation. | Per-route screenshots or a screen recording; browser console/network errors noted. |
| AC-02.3 | Inspect the top bar and sidebar footer. | Tenant name and slug are visible; “Tenant Isolated” and “RBAC & BYOK Active” indicators render; role badge matches the account; API Reference link opens docs. **WATCH:** the link is hard-coded to `http://localhost:8000/docs` (M-11), so record whether it is correct in the deployed environment. | Screenshot of top bar/sidebar; note the API Reference target URL. |
| AC-02.4 | Use each Quick Action: Start New Conversation, Upload Knowledge Base, Create AI Assistant, Manage BYOK API Keys. | Each navigates to the correct page and the target control is visible/usable. | Screenshot or short recording; list the resulting URLs. |

### AC-03 — Workspace switching and tenant isolation (4 checks)

| ID | Exact action (URL + UI steps) | Expected result | Evidence to capture |
|---|---|---|---|
| AC-03.1 | Ensure two workspaces exist; open the sidebar workspace dropdown; switch from Tenant A to Tenant B. **SEED** | Dashboard reloads with Tenant B name/slug/type; role badge and data update; no Tenant A records remain visible. | Before/after screenshots including tenant chip and URL. |
| AC-03.2 | In the same dropdown, click **New Workspace**; enter a name; choose Organization or Individual; submit. **SEED** | Workspace is created, appears in the dropdown, and becomes active; it survives a full page reload. | Screenshot of modal, dropdown, and resulting active workspace. |
| AC-03.3 | Record Tenant A’s assistant, KB, conversation, employee, department, group, provider credential, and audit entries. Switch to Tenant B and open each corresponding page. **SEED / NEG** | Tenant B pages show only B records; none of A’s named records appear. No count or list leaks A data. | Side-by-side screenshots per page; list visible record names and counts. |
| AC-03.4 | Switch to Tenant B, then reload the browser and reopen `/dashboard`. | Active workspace persists as B; data still scoped to B; no transient flash of A data. | Screenshot after reload; note active workspace only (do not expose tokens). |

> **NEG note:** UI-level cross-tenant checks are limited to workspace switching because most entities have no per-ID route. For direct-object authorization, use the API with Tenant A’s token and Tenant B’s resource ID and record the response; this is an optional API-level supplement, not a substitute for UI acceptance.

### AC-04 — Assistant creation wizard (6 checks)

| ID | Exact action (URL + UI steps) | Expected result | Evidence to capture |
|---|---|---|---|
| AC-04.1 | Open `/dashboard/assistants`; click **New** or **New Assistant**. | “Assistant Studio · Guided Creation” modal opens at Step 1 of 5; stepper shows 1–5; category pills All/Education/Business/Personal/Domain and template cards plus **Custom Domain Assistant** are visible. | Screenshot of Step 1 and stepper. |
| AC-04.2 | Select a category and a template card. | Selected card gets a blue ring; name, description, audience, response style, uncertainty behavior, citation style, instructions, retrieval mode, top-K, and temperature populate from the template. | Screenshot showing selected card and populated Step 2 fields. |
| AC-04.3 | Continue to Step 2; clear **Assistant Name**; click **Continue**. **NEG / WATCH** | Creation is blocked and an inline validation message explains that a name is required. **Source observation:** `saveError` is set but never rendered in the wizard JSX (M-17), so the field may silently refuse to advance; record actual behavior. | Screenshot/video of the click; note whether any error text appears. |
| AC-04.4 | Go to Step 3 with KBs present; check/uncheck one or more KBs. Then test the no-KB case in a fresh workspace. **SEED** | Checkboxes update selection and document counts; the no-KB case shows the “No Knowledge Bases in Workspace” explanatory empty state; Continue remains available because knowledge is optional. | Screenshot of selected KBs and of the empty state. |
| AC-04.5 | Go to Step 4; switch **Simple Mode** and **Advanced Mode**. | Simple Mode shows response style, missing-information behavior, citation strictness, and system instructions; Advanced Mode reveals provider, model, temperature, retrieval mode, top-K, max tokens, and full instructions; values persist when toggling. | Screenshots of both modes; note any lost values. |
| AC-04.6 | Go to Step 5; optionally send a test message; then click **Save Assistant**. **SEED** | Preview streams (or shows a clear generation error without blocking save); Save creates the assistant, selects it in the studio, and displays version `v1`. | Screenshot of preview and created assistant; record test prompt/response. |

### AC-05 — Assistant editing and versioning (5 checks)

| ID | Exact action (URL + UI steps) | Expected result | Evidence to capture |
|---|---|---|---|
| AC-05.1 | Select the assistant; on **Overview**, edit name/description; click **Save Changes**. | Button shows saving then **Saved!**; header/list reflect the new values; reload preserves them. | Screenshot before/after; reload screenshot. |
| AC-05.2 | Change the model/temperature on **Model & Retrieval** or the prompt on **Instructions & Behavior**; save; open **Version History**. | A new version row appears with a change summary, model, timestamp, and a **Current** badge; version number increments. | Screenshot of version table with two versions. |
| AC-05.3 | In Version History, click **Inspect** on a version. | Modal opens showing the immutable `config_snapshot` JSON; Close works; no edit controls. | Screenshot of snapshot modal (redact secrets if any). |
| AC-05.4 | Click **Rollback** on an older version; confirm. | A new forward version is created with the older configuration; rollback does not delete history; Current badge moves; UI values update. | Screenshot before/after version table and header version. |
| AC-05.5 | Open **Knowledge Bases** tab; change connected KBs; save; check the tab count and Overview connected count. **SEED** | Counts update consistently; save succeeds; reload preserves selection; chat retrieval uses the selected KBs (optional observation). | Screenshot of tab count, Overview card, and saved state. |

> **WATCH — assistant delete (M-01):** the API client has `deleteAssistant`, and the parent passes `onDelete`, but `AssistantWorkspaceView` never renders a delete control or invokes it. There is no way to delete an assistant from the UI.

### AC-06 — Knowledge-base creation (4 checks)

| ID | Exact action (URL + UI steps) | Expected result | Evidence to capture |
|---|---|---|---|
| AC-06.1 | Open `/dashboard/knowledge`; click **New Knowledge Base**; enter name and optional description; click **Save Container**. | Modal closes; new KB card appears with the name, description, current date, and `0 Documents`. | Screenshot of modal and resulting card. |
| AC-06.2 | Use a fresh workspace with no KBs. | Empty state displays “No Knowledge Bases created yet”, explanatory copy, and a **Create Container** CTA. | Screenshot of empty state. |
| AC-06.3 | Open the KB; click **Rename / Edit**; change name/description; save. | Breadcrumb, page heading, and grid card update; values persist after reload. | Before/after screenshot; reload. |
| AC-06.4 | Open the KB; click the trash icon; confirm. **NEG** | KB is removed from the grid; its documents/chunks are no longer reachable; canceling the confirm leaves it intact. | Screenshot of confirmation and post-delete grid. |

### AC-07 — Real document upload: PDF, DOCX, TXT, and others (5 checks)

| ID | Exact action (URL + UI steps) | Expected result | Evidence to capture |
|---|---|---|---|
| AC-07.1 | Open the KB → **Documents**; drag a multi-page PDF onto the dropzone (or click **browse files**); click **Upload & Ingest**. **SEED** | Success message reports queued document(s); row appears with filename, size, status, and later page/chunk counts; PDF icon is red. | Screenshot of upload queue, success message, and completed row. |
| AC-07.2 | Upload a valid `.docx` file the same way. **SEED** | Accepted and queued; completes with pages/chunks; DOCX icon is blue. | Screenshot of completed DOCX row. |
| AC-07.3 | Upload valid `.txt` and `.md` files. **SEED** | Both accepted; text is extracted and chunked; page count may be `—`/1, chunks > 0. | Screenshot of both rows. |
| AC-07.4 | Select PDF + DOCX + TXT in one picker and upload together. **SEED** | All files are queued independently; each row has its own status/progress; one failure does not cancel the others. | Screenshot of multi-file table. |
| AC-07.5 | Attempt an unsupported extension (e.g. `.exe`) and a file over 50 MB. **NEG** | Upload is rejected with a clear error; no document row is created; the previously selected files remain or can be cleared. **WATCH:** accepted extensions are `.pdf,.docx,.xlsx,.xlsm,.pptx,.csv,.tsv,.json,.jsonl,.sql,.ddl,.txt,.md`; legacy `.doc` is not in the file input even though an icon branch exists (M-10). | Screenshot of error; file name/size. |

### AC-08 — Ingestion status visibility (5 checks)

| ID | Exact action (URL + UI steps) | Expected result | Evidence to capture |
|---|---|---|---|
| AC-08.1 | Immediately after upload, watch the Documents table. **SEED** | Status shows `QUEUED` and/or `PROCESSING` with the corresponding badge/spinner; the page polls automatically (about every 2.5 s) while jobs are active; no manual refresh required to see completion. | Screenshot(s) of transient states; optional network log showing repeated list calls. |
| AC-08.2 | Open **Inspect** on a `COMPLETED` document. | Overview shows MIME type, pages/sheets, generated chunks, SHA-256, and tenant-isolated storage path; status and version are visible in the header. | Screenshot of Overview tab. |
| AC-08.3 | In the Inspect modal, open **Extracted Text**, **Chunks**, and **Processing History**. | Extracted text matches the source; chunks show index, heading path/page, character/token counts, and content; history shows a chronological timeline with stage/message. | Screenshots of all three tabs. |
| AC-08.4 | Upload a corrupted or intentionally failing file (or use a known failed record); click **Reprocess**. **NEG / SEED** | Row shows `FAILED` with a red badge; Reprocess triggers a new attempt; status transitions and error details remain visible. | Screenshot of FAILED state and reprocess result. |
| AC-08.5 | Open the KB → **Index Status**; click **Reindex Knowledge Base**; confirm. **SEED** | Metrics show vector store health, embedding version, total chunks, indexed vectors/percentage; reindex reports success or a clear error; jobs table lists provider/model/version/chunks/timestamps. | Screenshot of metrics, progress bar, jobs table, and success/error message. |

> **WATCH — KB detail reload loop (M-15):** `loadKBs` is a `useCallback` dependent on `selectedKB`, and it sets `selectedKB` to a freshly fetched object on every run. Source inspection indicates the KB detail view may continuously re-fetch while open. Observe the Network panel; if requests repeat indefinitely, record a FAIL/defect rather than treating transient data as correct.

### AC-09 — Chat and Markdown rendering (5 checks)

| ID | Exact action (URL + UI steps) | Expected result | Evidence to capture |
|---|---|---|---|
| AC-09.1 | Open `/dashboard/assistants`; select an assistant; switch to **Chat Sandbox**; send a prompt. **SEED** | User message appears immediately; assistant response streams token-by-token; Send becomes Stop; completion leaves the final answer; copy works. | Screenshot of streaming and completed response; note stop-button behavior. |
| AC-09.2 | Prompt: “Reply with an H2 heading, a **bold** phrase, an *italic* phrase, a bullet list of 3 items, and a numbered list of 2 items.” | Heading, bold, italic, bullet list, and numbered list render correctly; no raw `#`, `**`, or `-` markers remain. | Screenshot of rendered answer. |
| AC-09.3 | Prompt: “Return a fenced Python code block that prints hello.” | Dark code block with language label and horizontally scrollable code; content is selectable, not executed. | Screenshot of code block. |
| AC-09.4 | Prompt: “Return a 3-column Markdown table with a header row and two data rows.” | Table renders with header, borders, alternating row background, and readable cells; no pipe characters shown as plain text. | Screenshot of table. |
| AC-09.5 | Prompt for a blockquote and a safe link (e.g. `https://example.com`); click the link. | Blockquote styling renders; safe link opens in a new tab with `noopener noreferrer`; unsafe schemes are not turned into links. | Screenshot of blockquote/link; note target tab. |

### AC-10 — Citations and source preview, including page numbers (4 checks)

| ID | Exact action (URL + UI steps) | Expected result | Evidence to capture |
|---|---|---|---|
| AC-10.1 | Ask a question whose answer is explicitly on a known page of the seeded multi-page PDF. **SEED** | Answer contains inline `[N]` citation chips mapped to retrieved sources; no orphan citation numbers. | Screenshot of answer with visible `[N]` chips. |
| AC-10.2 | Click an inline citation chip in the Assistants chat. | Citation inspector modal opens with document name, **Page N**, and the source excerpt; N matches the seeded PDF page. | Screenshot of modal header and excerpt; record expected vs displayed page. |
| AC-10.3 | In the citation modal, switch **Visual Page** and **Context & Text**. | Both tabs show the same excerpt and page label; the modal closes reliably. **WATCH:** “Visual Page” is a styled excerpt, not a rendered PDF page image (M-09); this is a presentation limitation, not a page-number failure. | Screenshots of both tabs. |
| AC-10.4 | Reproduce citation inspection on `/dashboard/conversations` (Sources tray `p.N`) and on `/p/{publicId}` (expand `[N]`). **SEED** | Each surface opens/expands the correct source with document name, page number, and snippet; citations survive message reload. | Screenshots from each surface. |

### AC-11 — BYOK provider configuration (5 checks)

| ID | Exact action (URL + UI steps) | Expected result | Evidence to capture |
|---|---|---|---|
| AC-11.1 | Open `/dashboard/providers`; click **Add Provider Key**; choose provider (Groq/Anthropic/Gemini/OpenAI/OmniRoute), display label, API key, optional base URL, optional default; click **Save Credential**. **SEED (key)** | Credential row appears; provider, label, masked secret, status, and last-tested fields render; default flag shows if selected. Plaintext key is never displayed in the table. | Screenshot with masked key; network response inspected to confirm no plaintext key. |
| AC-11.2 | Click **Test** on the credential. | Button shows Testing; status becomes Healthy or Unhealthy; last tested timestamp updates; unhealthy state exposes an error message/tooltip. | Screenshot of status/timestamp; record provider/error. |
| AC-11.3 | Click **Rotate**; enter a new disposable key; confirm **Rotate Secret**. | Secret is re-encrypted; status/last-tested update appropriately; no plaintext is returned; active assistants continue to resolve the credential. | Screenshot of rotate modal and post-rotate row; no key in evidence. |
| AC-11.4 | Click **Revoke**; confirm. **NEG** | Status becomes Revoked; test/rotate/revoke actions are hidden; inference requiring the key fails or falls back per policy; credential remains listed. | Screenshot of Revoked row. |
| AC-11.5 | Click the trash icon; confirm **Delete**. Also open Provider Directory and Usage tabs. | Credential is permanently removed; directory lists providers/models; usage cards and per-provider table render or show an explicit empty state. | Screenshots of deletion result, directory, and usage tabs. |

### AC-12 — Conversation history and persistence (4 checks)

| ID | Exact action (URL + UI steps) | Expected result | Evidence to capture |
|---|---|---|---|
| AC-12.1 | Open `/dashboard/conversations`; click **New Chat**; ensure an assistant is selected via the filter (or the first assistant is used). **SEED** | New conversation is created and selected; empty state invites the first message; conversation appears at the top of the list. | Screenshot of new conversation and list. |
| AC-12.2 | Send at least two messages; wait for completion; reload the page. **SEED** | Conversation and both messages persist in order with timestamps and citations; the same conversation is selected or can be reselected. | Before/after reload screenshots; note selected conversation. |
| AC-12.3 | Hover a conversation; click the pencil; rename; press Enter. Then use search and the assistant filter. | Title updates in the list and header; search finds the new title; assistant filter hides non-matching conversations; rename persists after reload. | Screenshots of rename and filtered list. |
| AC-12.4 | Hover a conversation; click trash (or header **Delete**); confirm. **NEG** | Confirmation modal appears with the title; Delete removes the conversation and its messages; the next conversation or empty state is shown; cancel preserves it. | Screenshot of modal and post-delete state. |

### AC-13 — Developer API key create/revoke (4 checks)

| ID | Exact action (URL + UI steps) | Expected result | Evidence to capture |
|---|---|---|---|
| AC-13.1 | Open `/dashboard/settings` → **Developer API Keys**; click **Create Key**; enter a name; select scopes (at least one remains); choose 30/90/365 days or no expiration; click **Generate Key**. **No seed required** | Key is created; the create modal closes; the one-time secret banner appears. | Screenshot of create modal and resulting banner (redact the secret). |
| AC-13.2 | In the one-time secret banner, click **Copy**; paste into a local scratch file to verify; click **Done**; reload the page. | Raw key copies exactly once; after **Done**/reload only the prefix is shown; the raw secret is never displayed again. | Screenshot of banner before dismissal; confirmation that post-reload table shows prefix only. |
| AC-13.3 | Inspect the keys table. | Name, key prefix, scope badges, created date, expiration (or “Never”), and revoke action render correctly. | Screenshot of table row. |
| AC-13.4 | Click the trash/revoke icon; confirm. **NEG** | Confirmation names the key; revoke removes the row; the key can no longer authenticate (optional API check: expect 401). | Screenshot of confirmation and empty/remaining table; optional curl result. |

### AC-14 — Public publishing and embed page (6 checks)

| ID | Exact action (URL + UI steps) | Expected result | Evidence to capture |
|---|---|---|---|
| AC-14.1 | Open the assistant → **Publish & Embed**; review the readiness checklist; select **Public**; set a greeting, brand color, and allowed domains; click **Save Publication Settings**. **SEED** | Success; banner changes to “Assistant is Live and Publicly Accessible”; public link and JS/iframe snippets appear; preflight statuses update. | Screenshot of settings, live banner, and snippets. |
| AC-14.2 | Copy the public link and open `/p/{publicId}` in an incognito window with no dashboard session. **SEED** | Public page loads without authentication; assistant name/description/greeting and brand color render; no sidebar/topbar; empty state or greeting is visible. | Screenshot of public page and URL; confirm logged-out state. |
| AC-14.3 | Send a question with a known answer in the public page. **SEED** | Streaming answer renders Markdown; citation sources `[N]` appear; expanding a citation shows document name, page, and snippet. | Screenshot of streamed answer and expanded citation. |
| AC-14.4 | Return to Publish & Embed; choose **Private** or click **Unpublish**; save/confirm. **NEG** | Live banner disappears; `/p/{publicId}` and `/embed/{publicId}` show “Assistant Unavailable”/private messaging; no chat is possible. | Screenshot of private banner and unavailable public page. |
| AC-14.5 | Re-publish; open `/embed/{publicId}` directly and inside the copied iframe snippet. **SEED** | Compact widget renders with branded header; chat streams; citations expand; minimize posts `mmaip:toggle-widget` to the parent; iframe is 400×600 and not broken. | Screenshot of embed page/iframe; note console postMessage. |
| AC-14.6 | Copy the JavaScript embed snippet into a local test HTML page and open it from a different origin/local server. **WATCH / SEED** | Floating widget loads and opens the embed iframe. **Source risk (M-02):** the copied snippet requests `${frontendOrigin}/api/v1/public/embed.js`, but the frontend has no rewrite/API route for it; backend `embed.js` also derives the iframe origin from the script URL. This works only behind a same-origin reverse proxy. Record 404/blank widget as a FAIL. | Screenshot/network log of script request and widget; record status code and URLs. |

### AC-15 — Mobile and responsive behavior (4 checks)

| ID | Exact action (URL + UI steps) | Expected result | Evidence to capture |
|---|---|---|---|
| AC-15.1 | At 390×844, open `/login` and `/register`; scroll and submit a form. | No horizontal page scroll; all fields, selectors, and submit buttons are reachable; focus/keyboard does not hide the primary action; error banner remains readable. | Screenshots at top/bottom of each form. |
| AC-15.2 | At 390×844, open `/dashboard`; tap the hamburger; open/close the drawer; navigate. | Drawer slides in with backdrop; body does not scroll behind it; links close the drawer; content is not clipped. | Screenshot of closed/open drawer and a destination page. |
| AC-15.3 | At 390×844, open Employees, Audit, Providers, and Knowledge → Documents. | Wide tables scroll horizontally inside their container; page itself does not overflow; action buttons remain reachable. | Screenshots of each table at mobile width. |
| AC-15.4 | At 390×844 and 768×1024, open Assistants and Conversations. | Split panes remain usable: assistant/conversation list and chat controls are both reachable without clipped or unreachable UI. **WATCH (M-16):** both pages use a fixed `w-80` (320 px) left pane with no mobile collapse; expect overflow/squeeze. Record FAIL if the chat is not usable. | Screenshots of both pages at both widths; note horizontal scroll/clipping. |

### AC-16 — Error and empty states (4 checks)

| ID | Exact action (URL + UI steps) | Expected result | Evidence to capture |
|---|---|---|---|
| AC-16.1 | In a fresh workspace, visit Assistants, Knowledge, Conversations, Departments, Groups, Employees, Audit, Providers, and Developer API Keys. | Each page shows a descriptive, page-specific empty state with a CTA where applicable; no blank white area, infinite spinner, or raw `[]`. | Screenshots of each empty state (or a montage). |
| AC-16.2 | Stop the backend (or corrupt the token) and reload `/dashboard`. **NEG / WATCH** | A visible error/banner explains the failure; the page does not silently render zeros as if successful. **Source observation (M-14):** dashboard metrics use `Promise.allSettled` and only set counts on success, so failures may appear as `0` with no error. Record actual behavior. | Screenshot of dashboard/error; network status. |
| AC-16.3 | Open `/p/does-not-exist` and `/embed/does-not-exist`. **NEG** | “Assistant Unavailable” card/message with a human-readable reason; no stack trace, blank screen, or dashboard chrome. | Screenshots of both routes. |
| AC-16.4 | Trigger client errors: wrong login, unsupported/oversized upload, URL ingestion of `http://127.0.0.1`, `http://169.254.169.254`, and an invalid scheme. **NEG** | Each shows a clear inline error; rejected URL/file is not queued; no secret or internal detail leaks; the form remains usable. | Screenshot of each error; note messages. |

### AC-17 — Light-theme consistency (4 checks)

| ID | Exact action (URL + UI steps) | Expected result | Evidence to capture |
|---|---|---|---|
| AC-17.1 | Walk `/login`, `/register`, `/dashboard`, `/dashboard/assistants`, `/dashboard/knowledge`, `/dashboard/conversations`, `/dashboard/providers`, `/dashboard/settings`, `/dashboard/audit`, `/p/{id}`, `/embed/{id}`. | Surfaces are light gray/white with dark text; primary actions are blue; knowledge accents are amber; no page unexpectedly renders a dark theme. | One screenshot per page or a montage; note any dark surface. |
| AC-17.2 | Inspect inputs, selects, buttons (default/hover/disabled/focus), labels, and muted helper text. | Labels are legible; placeholder/muted text is not too faint; focus rings are visible; disabled controls still readable; no white-on-white text. | Zoomed screenshots of controls in each state. |
| AC-17.3 | Inspect code blocks, JSON snapshot viewers, trace/audit payload panes. | Intentionally dark code/JSON panes are readable and contained; they are not mistaken for a theme inconsistency; horizontal overflow is handled. | Screenshot of a code block and a JSON pane. |
| AC-17.4 | Re-test public and embed pages with all brand presets (Sky Blue, Indigo, Emerald, Violet, Amber, Rose, Slate Dark). **SEED** | Accent color applies to header/icon/send button; text remains readable for every preset; the light background is preserved. Note there is no dark-mode toggle (light-only product). | Screenshot per preset or a representative set; note contrast issues. |

### AC-18 — Logout and session expiry (4 checks)

| ID | Exact action (URL + UI steps) | Expected result | Evidence to capture |
|---|---|---|---|
| AC-18.1 | Click the sidebar logout icon. | Redirect to `/login`; dashboard is no longer accessible; token/active-tenant keys are cleared; no stale user data remains in the UI. | Screenshot of login page; DevTools local storage (do not capture token values). |
| AC-18.2 | Open `/dashboard` in a fresh incognito window with no session. **NEG** | “Loading workspace…”/“Redirecting to sign in…” then redirect to `/login`; protected page content is not rendered. | Screenshot and final URL. |
| AC-18.3 | After login, remove or corrupt `mmaip_token` in DevTools; refresh `/dashboard` and trigger an API action. **NEG / WATCH** | The app detects the invalid session, clears state, and redirects to `/login` (or shows a re-authentication prompt). **Source observation (M-03):** `api.request` has no global 401 handler and the stored refresh token is never used; an expired token may leave the user on the page with repeated errors. Record actual behavior. | Screenshot of resulting page/error; network 401. |
| AC-18.4 | Log out, then press browser Back to the dashboard; refresh. | No cached protected content is shown; the app redirects to login or displays no tenant data. | Screenshot after Back and after refresh. |

---

## 5. Results table template

**Result values:** `PASS` = all sub-checks in the area pass; `FAIL` = at least one sub-check fails; `BLOCKED` = environment/seed/dependency prevented execution. Record the actual sub-check IDs in Notes.

| Area | Checks | Result (PASS / FAIL / BLOCKED) | Notes / defect reference | Evidence reference | Tester | Date |
|---|---|---|---|---|---|---|
| AC-01 Login / registration | 5 | PENDING |  |  |  |  |
| AC-02 Dashboard / navigation | 4 | PENDING |  |  |  |  |
| AC-03 Workspace switching / isolation | 4 | PENDING |  |  |  |  |
| AC-04 Assistant creation wizard | 6 | PENDING |  |  |  |  |
| AC-05 Assistant editing / versioning | 5 | PENDING |  |  |  |  |
| AC-06 Knowledge-base creation | 4 | PENDING |  |  |  |  |
| AC-07 Real document upload | 5 | PENDING |  |  |  |  |
| AC-08 Ingestion status visibility | 5 | PENDING |  |  |  |  |
| AC-09 Chat + Markdown rendering | 5 | PENDING |  |  |  |  |
| AC-10 Citations + source preview | 4 | PENDING |  |  |  |  |
| AC-11 BYOK provider configuration | 5 | PENDING |  |  |  |  |
| AC-12 Conversation history / persistence | 4 | PENDING |  |  |  |  |
| AC-13 Developer API key create / revoke | 4 | PENDING |  |  |  |  |
| AC-14 Public publishing + embed | 6 | PENDING |  |  |  |  |
| AC-15 Mobile / responsive | 4 | PENDING |  |  |  |  |
| AC-16 Error / empty states | 4 | PENDING |  |  |  |  |
| AC-17 Light-theme consistency | 4 | PENDING |  |  |  |  |
| AC-18 Logout / session expiry | 4 | PENDING |  |  |  |  |

**Totals:** 18 areas, 82 discrete sub-checks. Manual acceptance is **PENDING** until every row is completed and signed off by the user.

### 5.1 Overall sign-off

| Field | Value |
|---|---|
| Overall result | PENDING |
| Areas passed / failed / blocked | ___ / ___ / ___ |
| Open defects (IDs and severity) |  |
| Tester name |  |
| Execution date |  |
| Environment (frontend URL, backend URL, commit) |  |
| Recommendation | ACCEPT / ACCEPT WITH DEFECTS / REJECT |
| User sign-off |  |

---

## 6. Source-level missing / at-risk feature register (report only — not fixed)

These findings come from static inspection. They are not runtime-confirmed and were not remediated in this phase.

| ID | Type | Observation | Source evidence | Acceptance impact |
|---|---|---|---|---|
| M-01 | Missing UI control | No assistant delete button; `onDelete` prop is declared/passed but never used. | `frontend/app/dashboard/assistants/AssistantWorkspaceView.tsx:38,46`; `assistants/page.tsx:650`; `lib/api.ts:1214` | Lifecycle cannot be completed from the UI |
| M-02 | Missing integration / at risk | Embed script has no frontend route or rewrite. Copied snippet uses frontend origin; backend `embed.js` derives iframe origin from the script URL. Works only behind a same-origin reverse proxy. | `PublishTab.tsx:141-147`; `next.config.ts`; `backend/app/api/v1/public_chat.py:180-210` | Local-dev embed snippet likely 404/blank; deployed embed depends on proxy config |
| M-03 | Missing behavior | No global 401 handler, no refresh-token flow; access token in localStorage; refresh token stored but unused. | `frontend/lib/api.ts:799-840,855-876`; `auth-context.tsx` | Expired session may not redirect to login |
| M-04 | Missing routes | No per-assistant, per-KB, or per-conversation detail URLs. | App Router tree | No deep links/bookmarks/shareable records |
| M-05 | Missing UI | No profile/password/account settings page. | No route under `frontend/app/**` | Users cannot self-manage identity |
| M-06 | Missing UI | No member role editing; no department/group membership assignment (only counts and invite-time department). | `employees/page.tsx`; `departments/page.tsx`; `groups/page.tsx` | Organization administration is incomplete |
| M-07 | Missing UI | Organization profile is read-only; no edit form. | `workspace/page.tsx` | Tenant metadata cannot be maintained in UI |
| M-08 | Missing UI | No publication overview/list; only per-assistant settings. | No `/dashboard/publications` route | No inventory of public assistants |
| M-09 | Limited feature | Citation “Visual Page” renders a styled text excerpt, not the actual PDF page image. | `assistants/page.tsx:914-944` | Visual source verification is limited |
| M-10 | Limited upload | `.doc` is not in the file input accept list although icon logic handles it; `.ppt` is not accepted (only `.pptx`). | `knowledge/page.tsx:610`; `knowledge/page.tsx:371-378` | Legacy Office files cannot be uploaded |
| M-11 | Misconfiguration | Dashboard API Reference link is hard-coded to `http://localhost:8000/docs`. | `dashboard/layout.tsx:416` | Broken in deployed environments |
| M-12 | Placeholder data | Settings quotas/capacity are hard-coded strings, not tenant data. | `settings/page.tsx:63-91` | Misleading acceptance signal |
| M-13 | Documentation mismatch | Runbook sets `NEXT_PUBLIC_API_URL` with `/api/v1`, while the client appends `/api/v1`. | `docs/runbooks/local-development.md`; `frontend/lib/api.ts:1-40` | Login fails if the runbook is followed verbatim |
| M-14 | Error-state gap | Dashboard metrics swallow failures (`Promise.allSettled`) and can display `0` with no error. | `dashboard/page.tsx:37-55` | Backend failure can look like an empty workspace |
| M-15 | Performance risk | KB detail `loadKBs` depends on `selectedKB` and resets it to a fresh object each fetch; possible continuous re-fetch loop. | `knowledge/page.tsx:99-137` | Flaky loading/network churn; verify with Network panel |
| M-16 | Responsive risk | Assistants and Conversations use fixed `w-80` split panes with no mobile collapse. | `assistants/page.tsx:359`; `conversations/page.tsx:396` | Mobile chat may be squeezed/overflowing |
| M-17 | Validation gap | Wizard sets `saveError` but never renders it; empty-name Continue may silently do nothing. | `AssistantCreationWizard.tsx:89,884-888` | No feedback for required-field errors |
| M-18 | No dark mode | Light-only design; no theme toggle. | `globals.css`; all pages | Not a defect if light-only is intended; record as an explicit product limitation |

**Route completeness:** all routes requested for M11 Stage 10 exist (auth, dashboard areas, public, embed). The missing items are deep-link/management routes and controls listed above, not absent top-level dashboard pages.

---

## 7. Evidence and privacy rules

- Name evidence files `M11_AC-XX.Y_<short-slug>.png` (example: `M11_AC-10.2_citation-page-number.png`).
- Each evidence item should show the URL and tenant name; crop or redact tokens, API keys, passwords, and personal data.
- For failures, capture: screenshot, browser console error, failing network request (status + response body), and the seeded record IDs/names.
- Do not paste raw API keys or JWTs into reports. The BYOK and developer-key tables should show masked values only.
- Store evidence outside the repository unless the project explicitly designates an artifact location; this phase created no screenshots or artifacts.

---

## 8. Handoff status

| Item | Status |
|---|---|
| Route inventory | Complete (source inspection) |
| Checklist | Complete — 18 areas / 82 sub-checks |
| Environment prerequisites | Documented; deployed URLs TBD |
| Seed-data matrix | Documented; seeding is the tester’s responsibility |
| Manual execution | **PENDING** |
| Browser automation | **Not performed** |
| Screenshots / visual verification | **Not performed** |
| Code or git changes | **None** |
| Missing-feature report | Complete (Section 6) |
