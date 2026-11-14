# M10 Final Integration — Stage G: Frontend, API & SDK Integration Audit

**Date:** 2026-11-11

---

## 1. Automated checks (measured this audit)

| Check | Command | Result |
|---|---|---|
| Frontend TypeScript | `cd frontend; npx tsc --noEmit` | **PASS** (exit 0) |
| Next.js production build | `npm run build` | **PASS** — 20/20 routes compiled (exit 0) |
| TypeScript SDK | `frontend\node_modules\.bin\tsc --project sdk/typescript/tsconfig.json` | **PASS** (exit 0). Note: root `npx tsc` fails because typescript is not installed at repo root — use the frontend binary. |
| Python SDK tests | `tests/test_sdk_python.py` | **PASS** (2 tests, in full suite) |
| Backend import integrity | `python -m compileall app` + `from app.main import app` | **PASS** (exit 0) |
| Backend lint | `python -m ruff check .` | **FAIL (127 errors)** — **pre-existing at HEAD** (unmodified tracked files like `api/v1/providers.py` already contain violations; confirmed via `git show HEAD:... | ruff check`). CI's ruff gate was red before M09/M10. |
| Backend format | `python -m ruff format --check .` | **FAIL (127 files)** — pre-existing, format never enforced. |
| Live run | backend :8000 + frontend :3000 | **PASS** — `/health`, `/ready` 200; `/`, `/login` 200. |

## 2. M10 Stage 6 (Markdown & citations) — prerequisite check

**Implementation status: COMPLETE and integrated; final Stage 6 report does NOT exist.**

- `frontend/components/chat/MarkdownRenderer.tsx` (517 lines): dependency-free markdown (block+inline), URL sanitizer (http/https/mailto only), citation `[N]` chips keyed to `MessageCitationItem.citation_num`, **no `dangerouslySetInnerHTML`**, streaming-safe via memoized parse.
- Used in **5 live surfaces**: `dashboard/assistants/page.tsx`, `AssistantCreationWizard.tsx` (sandbox), `dashboard/conversations/page.tsx` (streaming), `p/[publicId]/page.tsx`, `embed/[publicId]/page.tsx`.
- Backend contract: `runtime.py` emits `retrieval_complete` (citation array) once per stream; `context.py` Tier-1 instructions forbid auto-appended bibliographies; `normalize_markdown` applied to persisted content.
- Tenant-safe source preview: all surfaces render only `snippet`/`document_name` returned in the message payload; no document fetch-by-ID client path exists.

**Gaps (documented, not silently fixed):**
1. **No M10 Stage 6 milestone report** in `docs/m10/` or `artifacts/` → per prerequisite rule, **M10 cannot be declared fully closed**.
2. Citation accumulation in `p/[publicId]` and `embed/[publicId]` has no dedup (safe today because backend emits `retrieval_complete` once; fragile if contract changes).
3. `conversations/page.tsx` contains dead SSE branches (`message_end`, per-`citation`) for events the backend never emits; `message_complete` is consumed only inside `lib/api.ts`.
4. Backend markdown defects D1/D2: `context.py` contains **two `normalize_markdown` definitions** (the later one shadows the richer one); the untracked `markdown_normalizer.py` module is imported only by its own tests — the tested path is not the runtime path. Consequence: 2 of 6 failing tests are markdown-normalizer expectation drift.
5. `MarkdownRenderer` citation matching uses first-match `.find()` (no duplicate handling) — cosmetic.

## 3. Frontend integration findings

- API base: `lib/api.ts` resolves `NEXT_PUBLIC_API_BASE_URL`/`NEXT_PUBLIC_API_URL` → client `window.location` mapping → SSR fallback. Client-side fail-closed (throws) in production when env missing; **inconsistency:** `getPublicAssistant`/`getPublicEmbedConfig` still use the static `API_V1` const, whose SSR value falls back to `http://127.0.0.1:8000`.
- Token/tenant: dual-key fallback (`mmaip_token` || `token`), `X-Tenant-ID` propagated on all requests including SSE; `window` access is `typeof`-guarded (no SSR crash).
- SSE: `streamAssistantMessage`/`streamPublicChat` do not accept `AbortSignal`; the conversations page hand-rolls its own fetch+AbortController (duplicated parser) — works, but the shared client should own cancellation.
- Hardcoded URL: `dashboard/layout.tsx:416` links `http://localhost:8000/docs`; should derive from `getApiBase()`.
- **Contract defect (SEC-1):** invite role options `manager`/`admin` don't exist in the backend role catalog → HTTP 400 on invite.
- Theme: 0 residual dark theme classes; dark styling retained only for code blocks and modal scrims (intentional).
- Debug code: no `console.log`/TODO/FIXME; a few bare `console.error(err)` without context strings.

## 4. API ↔ SDK consistency

| Surface | Endpoints | Python SDK | TS SDK | Notes |
|---|---|---|---|---|
| Developer assistants | `GET /developer/assistants` | `list_assistants` | `assistants.list` | consistent |
| Developer chat SSE | `POST /developer/assistants/{id}/chat` | `stream_chat` (SSE parser) | `assistants.streamChat` (SSE parser) | consistent event shapes (`token`, `retrieval_complete`, `usage`, `message_complete`, `message_error`) |
| Auth | `Authorization: Bearer <api_key>` | yes | yes | consistent; assistant-scoped keys enforced server-side |
| Error handling | HTTP status + JSON detail | `MMAIPError(status_code)` | `MMAIPError(statusCode)` | consistent |
| Pagination | not present on these endpoints | n/a | n/a | out of SDK scope |

Both SDKs are narrower than the full API surface (by design — developer API only). No SDK expansion performed.

---

## Declarations

```text
FRONTEND_INTEGRATION = PASS
SDK_INTEGRATION = PASS
M10_STAGE_6 = CONDITIONAL_PASS   (implementation complete + integrated + tests exist; final Stage 6 report missing; 2 markdown tests failing; citation dedup gaps)
```
