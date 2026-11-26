# M11 Manual UI Acceptance Handoff

| Field | Value |
|---|---|
| Milestone | M11 - private staging readiness |
| Document | Concrete 18-area manual UI acceptance checklist and results handoff |
| Repository | `E:\MM Office\Multi-Tanant-CaaS` |
| Baseline | `HEAD` = `fdb12463a8308d86015cba8d82546faf0f546c8b`; M11 UI-affecting changes are uncommitted in the working tree |
| Date | 2026-11-12 |
| Execution status | `MANUAL_UI_ACCEPTANCE = PENDING_USER_VERIFICATION` |
| Browser execution | **None.** No browser, screenshot, device emulation, or visual verification was performed for this handoff. |
| Source basis | `M11_STAGE_10_MANUAL_UI_ACCEPTANCE.md` (18 areas, 82 sub-checks) and the current `frontend/app/**` source tree |

> This document is a handoff, not a result. Every row below is **PENDING**. The tester must execute the actions against a running backend/frontend, record pass/fail per sub-check, and sign the results table. Do not mark an area PASS from source inspection alone.

---

## 1. Automated evidence already recorded

| Check | Command / evidence | Result | Meaning |
|---|---|---|---|
| Frontend typecheck | `npx tsc --noEmit` | Exit 0, no diagnostics | Types compile |
| Production build | `NEXT_TELEMETRY_DISABLED=1 npm run build` | Exit 0; `20/20` static pages | The App Router tree builds |
| Frontend lint | `npm run lint` | Exit 1; `122 problems (38 errors, 84 warnings)` | Pre-existing debt, not fixed; not a build blocker |
| Backend health on live PostgreSQL | `GET /health`, `GET /ready` | 200 / 200 (`database=connected`) | API can serve the UI locally/PG |
| Backend security smoke | unauth `GET /api/v1/embedding-providers` | 401 | Protected routes are not anonymous |
| SDKs | TS SDK `tsc` exit 0; Python SDK `2 passed` | PASS | Client libraries compile/test |

Lint details: errors are dominated by `@typescript-eslint/no-explicit-any` plus two `react-hooks/purity` errors at `frontend/app/dashboard/assistants/page.tsx:261` and `:270` (`Date.now()` during render). Warnings are dominated by unused imports/variables and `react-hooks/exhaustive-deps`. This debt is **pre-existing and unchanged**; do not treat it as acceptance evidence for UI behavior.

---

## 2. Environment prerequisites

| Item | Required value |
|---|---|
| Backend | Local FastAPI, e.g. `http://127.0.0.1:8000`; `/health` and `/ready` both 200 |
| Frontend | Local Next.js, e.g. `http://localhost:3000`; `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000` (origin only, **no** `/api/v1`) |
| Backend CORS | Must allow the exact frontend origin |
| Database | Disposable local SQLite or disposable PostgreSQL 16; never a real/staging database for destructive checks |
| Accounts | One owner account; a second tenant/owner for switching; an invited employee for invitation acceptance |
| Seed data | One KB with a multi-page PDF, DOCX, TXT, MD; one assistant connected to the KB; one existing conversation with citations; optional disposable BYOK key |
| Public publishing | **Disabled for staging.** Execute AC-14 only in a disposable local environment, or record it as waived/blocked for staging. Do not create a PUBLIC publication in staging. |
| Data | **Synthetic only.** Do not upload real documents. |
| Browser | Chromium 1440x900; mobile emulation 390x844; tablet 768x1024; optional second browser smoke |

Registration policy note: the frontend still renders `/register` and a login-page link. With `ALLOW_PUBLIC_REGISTRATION=false` (or non-development `ENVIRONMENT` without an explicit true), the API returns 403. The UI check is that the user sees an error and no workspace is created, not that the page is hidden.

---

## 3. 18-area manual checklist

Result values: `PASS` (all sub-checks), `FAIL` (at least one), `BLOCKED` (environment/seed/dependency), `PENDING` (not executed). Sub-check IDs follow `M11_STAGE_10_MANUAL_UI_ACCEPTANCE.md`.

| # | Area (sub-checks) | Concrete actions | Expected results | Result | Evidence / notes |
|---:|---|---|---|---|---|
| 1 | Login and registration policy (AC-01.1-01.5) | Open `/register`; try Organization and Individual registration. With registration disabled, submit a unique email. Open `/login`; sign in with a valid account; try a wrong password; try registering an existing email. | When enabled: account/workspace created, redirect to `/dashboard`, correct organization/individual type. When disabled: clear 403/error, no user/tenant created. Wrong password: inline error, no token, stay on `/login`. Duplicate email: clear conflict error. | PENDING | Record the exact error text and whether `/register` remains linked |
| 2 | Dashboard and navigation (AC-02.1-02.4) | Log in; open `/dashboard`; click every sidebar item (Overview, Assistants, Knowledge, Conversations, Observability, Employees, Departments, Groups, Organization, Providers & Keys, Audit Logs, Settings); use all four Quick Actions. | Four metric cards render with numbers; recent activity or descriptive empty state; each route loads without 404/blank/uncaught error; active item highlighted; mobile drawer closes; Quick Actions reach the correct page/control. | PENDING | API Reference is hard-coded to `http://localhost:8000/docs` (M-11); record the deployed behavior |
| 3 | Workspace switching and tenant isolation (AC-03.1-03.4) | With two workspaces, switch A -> B in the sidebar; create a new workspace; record A's assistant/KB/conversation/employee/department/group/provider/audit names, switch to B, open each page; reload. | B shows only B records; no A names/counts leak; new workspace persists; reload keeps the active workspace; no flash of A data. | PENDING | Also run one API-level cross-tenant negative with A's token and B's ID (supplement, not a substitute) |
| 4 | Assistant creation wizard (AC-04.1-04.6) | Open `/dashboard/assistants` -> New; walk Steps 1-5: category/template, name/description, KB selection (and no-KB case), Simple/Advanced toggles, optional test message, Save. | Wizard opens at Step 1/5; template populates fields; empty name is blocked with visible feedback; KB checkboxes/counts work; no-KB empty state is explanatory; toggles preserve values; Save creates the assistant and shows `v1`; preview streams or shows a clear non-blocking error. | PENDING | Source risk: `saveError` is set but not rendered (M-17); record whether the empty-name click gives feedback |
| 5 | Assistant editing and versioning (AC-05.1-05.5) | Edit name/description and save; change model/temperature or prompt and save; open Version History; inspect a version; rollback an older version; change connected KBs and save. | Save shows `Saved!` and persists after reload; a new version row appears with `Current`; Inspect shows immutable `config_snapshot`; rollback creates a new forward version and preserves history; KB counts update consistently. | PENDING | No assistant delete control exists (M-01); record as a product gap, not a failed save |
| 6 | Knowledge-base creation (AC-06.1-06.4) | Create a KB; view the empty state in a fresh workspace; rename/edit; delete and confirm/cancel. | Card appears with name/description/date/`0 Documents`; empty state has explanatory copy and CTA; rename updates breadcrumb/heading/card and persists; delete removes the KB; cancel preserves it. | PENDING | Deleting a KB leaves stored objects in the current backend; do not treat as clean erasure |
| 7 | Real document upload (AC-07.1-07.5) | Upload a multi-page PDF, a valid DOCX, TXT, MD; select multiple files at once; try `.exe` and a >50 MB file. | PDF/DOCX/TXT/MD accepted and queued; each row has independent status; page/chunk counts appear; unsupported/oversized rejected with a clear error and no document row; prior selection remains/clearable. | PENDING | **Synthetic files only.** Accepted extensions: `.pdf,.docx,.xlsx,.xlsm,.pptx,.csv,.tsv,.json,.jsonl,.sql,.ddl,.txt,.md`; `.doc`/`.ppt` are not in the picker (M-10) |
| 8 | Ingestion status visibility (AC-08.1-08.5) | Watch the documents table after upload; open Inspect on a completed document; view Overview/Extracted Text/Chunks/Processing History; trigger a failing file and Reprocess; open Index Status and Reindex. | Status shows QUEUED/PROCESSING then COMPLETED without manual refresh (about 2.5 s polling); Inspect shows MIME/pages/chunks/SHA-256/tenant path; extracted text/chunks/history are populated; FAILED shows an error and Reprocess starts a new attempt; reindex reports success/clear error and jobs table. | PENDING | Source risk: possible KB detail re-fetch loop (M-15); inspect the Network panel |
| 9 | Chat and Markdown rendering (AC-09.1-09.5) | In Chat Sandbox, send a prompt; ask for H2, bold, italic, 3 bullets, 2 numbered items; ask for a fenced Python block; ask for a 3-column table; ask for a blockquote and a safe link. | Streaming token-by-token with Send->Stop; heading/bold/italic/lists render with no raw markers; code block has language label, dark surface, horizontal scroll, is selectable and not executed; table renders; blockquote styles; safe link opens in a new tab with `noopener noreferrer`; unsafe schemes are not linked. | PENDING | Capture a screenshot per render type |
| 10 | Citations and source preview (AC-10.1-10.4) | Ask a question answered on a known PDF page; click an inline `[N]`; switch Visual Page/Context & Text; repeat on Conversations sources and `/p/{publicId}`. | Inline chips map to retrieved sources; modal shows document name, **Page N**, excerpt; N matches the seeded page; both tabs show the same excerpt; sources survive reload; conversations/public page show the same page/snippet. | PENDING | "Visual Page" is a styled excerpt, not a PDF image (M-09); record as a presentation limitation |
| 11 | BYOK provider configuration (AC-11.1-11.5) | Open Providers; add a disposable key (provider/label/key/optional base URL/default); Test; Rotate; Revoke; Delete; open Provider Directory and Usage. | Row shows provider/label/masked secret/status; Test updates Healthy/Unhealthy + timestamp; Rotate re-encrypts and never returns plaintext; Revoke hides actions; Delete removes it; Directory/Usage render or show an explicit empty state. | PENDING | Never use production keys; mask any key visible in evidence. Do not set a custom `base_url` to a private/loopback target (F-15) |
| 12 | Conversation history and persistence (AC-12.1-12.4) | Open Conversations -> New Chat; send two messages; reload; rename; search; filter by assistant; delete and cancel. | New conversation selected and listed at the top; messages persist in order with timestamps/citations; rename updates list/header and survives reload; search/filter work; delete confirmation names the title and removes messages; cancel preserves. | PENDING | No per-conversation URL (M-04); refresh selects the first returned conversation |
| 13 | Developer API key create/revoke (AC-13.1-13.4) | Settings -> Developer API Keys -> Create Key; choose scopes and 30/90/365/none; Generate; copy the one-time secret; Done; reload; inspect the table; revoke. | Key created; one-time banner shows once; Copy works; after Done/reload only the prefix is shown; table shows name/prefix/scopes/created/expiry/action; revoke confirms and removes the row; optional API check returns 401 after revoke. | PENDING | Redact the one-time secret in all evidence |
| 14 | Public publishing and embed (AC-14.1-14.6) | **Disposable/local only.** Publish PUBLIC with greeting/brand/domains; open `/p/{publicId}` incognito; ask a cited question; set Private/Unpublish; open `/embed/{publicId}` directly and in the copied iframe snippet; try the JS snippet from a different origin. | Public page loads without auth; greeting/brand/name visible; streaming Markdown + expandable citations; unpublish shows "Assistant Unavailable" and no chat; embed widget renders 400x600, streams, expands citations, posts minimize; JS snippet loads only behind a same-origin proxy. | PENDING | **Do not enable public publishing in staging.** For staging record `BLOCKED/WAIVED`; source risk M-02: no frontend route/rewrite for `embed.js` |
| 15 | Mobile and responsive behavior (AC-15.1-15.4) | At 390x844: login/register scroll+submit; dashboard drawer; Employees/Audit/Providers/Knowledge documents tables; Assistants/Conversations split panes. Repeat Assistants/Conversations at 768x1024. | No horizontal page scroll; fields/buttons reachable; drawer has backdrop and closes; wide tables scroll inside their container; split panes remain usable with both list and chat reachable. | PENDING | Source risk: fixed `w-80` panes with no mobile collapse (M-16); record FAIL if chat is unusable |
| 16 | Error and empty states (AC-16.1-16.4) | Visit fresh-workspace Assistants/Knowledge/Conversations/Departments/Groups/Employees/Audit/Providers/API Keys; stop the backend or corrupt the token and reload `/dashboard`; open `/p/does-not-exist` and `/embed/does-not-exist`; trigger wrong login, unsupported/oversized upload, URL ingestion `127.0.0.1`, `169.254.169.254`, invalid scheme. | Each page has a descriptive empty state/CTA; backend failure shows a visible error, not silent zeros; unknown public IDs show "Assistant Unavailable", no stack trace/dashboard chrome; each client error is inline, sanitized, and does not queue the request. | PENDING | Source risk: dashboard `Promise.allSettled` can show 0 on failure (M-14) |
| 17 | Light-theme consistency (AC-17.1-17.4) | Walk login/register/dashboard/assistants/knowledge/conversations/providers/settings/audit/public/embed; inspect inputs/buttons/labels/focus/disabled; inspect code/JSON/trace panes; test all brand presets on public/embed. | Light gray/white surfaces with dark text; blue primary actions; amber knowledge accents; no unexpected dark page; labels/placeholders/focus rings legible; dark code/JSON panes are intentional and contained; every brand preset keeps readable text and a light background. | PENDING | Light-only product; no dark-mode toggle (M-18) |
| 18 | Logout and session expiry (AC-18.1-18.4) | Click logout; open `/dashboard` in a fresh incognito window; remove/corrupt `mmaip_token` and refresh/trigger an API action; log out and press Back then refresh. | Logout redirects to `/login` and clears tenant/token state; unauthenticated `/dashboard` redirects to `/login` without rendering protected content; invalid/expired token is detected and the user is redirected or prompted; Back/refresh shows no cached tenant data. | PENDING | Source risk: no global 401 handler and refresh token is unused (M-03); record actual behavior |

---

## 4. Results table

| Area | Sub-checks | Result | Notes / defect reference | Evidence reference | Tester | Date |
|---|---:|---|---|---|---|---|
| 1. Login / registration policy | 5 | PENDING |  |  |  |  |
| 2. Dashboard / navigation | 4 | PENDING |  |  |  |  |
| 3. Workspace switching / isolation | 4 | PENDING |  |  |  |  |
| 4. Assistant creation wizard | 6 | PENDING |  |  |  |  |
| 5. Assistant editing / versioning | 5 | PENDING |  |  |  |  |
| 6. Knowledge-base creation | 4 | PENDING |  |  |  |  |
| 7. Real document upload | 5 | PENDING |  |  |  |  |
| 8. Ingestion status visibility | 5 | PENDING |  |  |  |  |
| 9. Chat + Markdown rendering | 5 | PENDING |  |  |  |  |
| 10. Citations + source preview | 4 | PENDING |  |  |  |  |
| 11. BYOK provider configuration | 5 | PENDING |  |  |  |  |
| 12. Conversation history / persistence | 4 | PENDING |  |  |  |  |
| 13. Developer API key create / revoke | 4 | PENDING |  |  |  |  |
| 14. Public publishing + embed | 6 | PENDING | Staging: BLOCKED/WAIVED (publishing must stay off) |  |  |  |
| 15. Mobile / responsive | 4 | PENDING |  |  |  |  |
| 16. Error / empty states | 4 | PENDING |  |  |  |  |
| 17. Light-theme consistency | 4 | PENDING |  |  |  |  |
| 18. Logout / session expiry | 4 | PENDING |  |  |  |  |

**Totals:** 18 areas, 82 discrete sub-checks. `MANUAL_UI_ACCEPTANCE = PENDING_USER_VERIFICATION`. The overall result is not PASS until every applicable row is completed and signed. Area 14 is expected to be `BLOCKED/WAIVED` for staging because public publishing must remain disabled.

### 4.1 Sign-off

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

## 5. Missing routes and features to record as gaps

These are source-level observations from `M11_STAGE_10_MANUAL_UI_ACCEPTANCE.md` and the current `frontend/app/**` tree. They are not runtime-confirmed failures, but they limit what an acceptance pass can prove.

| ID | Missing / limited item | Observation | Acceptance impact |
|---|---|---|---|
| UI-G1 | Assistant detail/deep links | No `/dashboard/assistants/[id]` route; selection is internal state in the split view. Also no per-KB (`/dashboard/knowledge/[id]`) or per-conversation (`/dashboard/conversations/[id]`) route. | No bookmark, shareable record, refresh-to-same-item, or deep-link test. Record as a product gap, not a failed navigation. |
| UI-G2 | Profile/password settings | No `/dashboard/profile` or account settings page. The workspace profile is read-only. | Users cannot self-manage identity/password. Password reset is also absent at the API (F-13). |
| UI-G3 | Global 401 handling | `api.request` has no global 401 handler; the refresh token is stored but unused; an expired token may leave the user on the page with repeated errors. | AC-18.3 may fail or behave inconsistently. Record the actual behavior and the network 401. |
| UI-G4 | Publication inventory | No `/dashboard/publications` route; publishing is per assistant under Publish & Embed. | No consolidated list to prove "no PUBLIC publication exists" from the UI. Use an API/DB check for the staging gate. |
| UI-G5 | Assistant delete | `onDelete` is declared/passed but no delete control is rendered. | Lifecycle cannot be completed from the UI. Record as a gap (M-01). |
| UI-G6 | Embed snippet integration | The copied snippet requests `${frontendOrigin}/api/v1/public/embed.js`; there is no Next.js route/rewrite, and the backend script derives the iframe origin from the script URL. | The snippet works only behind a same-origin reverse proxy (M-02). Test locally or record 404/blank as a failure. |
| UI-G7 | KB detail reload loop | `loadKBs` depends on `selectedKB` and resets it to a fresh object on each fetch; possible continuous re-fetch. | Check the Network panel while the KB detail is open (M-15). |
| UI-G8 | Mobile split panes | Assistants and Conversations use fixed `w-80` panes with no mobile collapse. | Chat may be squeezed/overflowing at 390 px (M-16). |
| UI-G9 | Wizard validation feedback | `saveError` is set but never rendered; empty-name Continue may silently do nothing. | AC-04.3 may have no visible error (M-17). |
| UI-G10 | Dashboard error masking | Metrics use `Promise.allSettled` and only set counts on success, so a backend failure can look like `0`. | AC-16.2 may show zeros without an error (M-14). |
| UI-G11 | API Reference link | Hard-coded to `http://localhost:8000/docs`. | Broken in a deployed environment (M-11). |
| UI-G12 | Placeholder quota data | Settings quotas/capacity are hard-coded strings, not tenant data. | Do not accept settings values as real quota evidence (M-12). |

---

## 6. Execution and evidence rules

1. Use synthetic data only. Never upload a real document to staging.
2. Use a disposable local database or a disposable staging tenant; do not run destructive checks against a shared environment.
3. Record each sub-check as PASS/FAIL/BLOCKED with the AC ID (for example `AC-10.2`).
4. For a failure, capture: screenshot, browser console error, failing request (status + response body), and the seeded record name/ID.
5. Redact JWTs, API keys, invitation tokens, passwords, and personal data before attaching evidence.
6. Do not paste raw keys into this document. BYOK/developer-key evidence must show masked values only.
7. Name evidence files `M11_AC-XX.Y_<slug>.png`.
8. Store evidence outside the repository unless a designated artifact location is approved.
9. If the backend/frontend cannot be started, mark the affected areas `BLOCKED`, not `PASS`.
10. Area 14 (public publishing/embed) must be run only in a disposable local environment or recorded as `BLOCKED/WAIVED` for staging. A staging run must not create a PUBLIC publication.

---

## 7. Handoff status

| Item | Status |
|---|---|
| Checklist | Complete - 18 areas / 82 sub-checks, with concrete actions and expected results |
| Automated evidence | Recorded: `tsc` 0, build 20/20, lint 122 pre-existing problems |
| Manual execution | **PENDING** |
| Browser / screenshots / visual verification | **NOT PERFORMED** |
| Missing UI routes/features | Recorded (Section 5) |
| Code or Git changes | **None** |
| Overall verdict | `MANUAL_UI_ACCEPTANCE = PENDING_USER_VERIFICATION` |

The application is not UI-accepted. The staging decision may proceed only if the user completes this checklist or explicitly records a waiver for the closed synthetic cohort, with Area 14 kept disabled.