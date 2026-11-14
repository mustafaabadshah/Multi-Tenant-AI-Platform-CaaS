# M10 Stage 6 — Final Report: Markdown Rendering & Citation Quality

**Project:** Multi-Tenant AI Assistant Platform (Chatbot-as-a-Service)
**Workspace:** `E:\MM Office\Multi-Tanant-CaaS`
**Branch:** `main` (HEAD `9479847`; no commits created by this closeout)
**Milestone:** M10
**Stage:** 6 — Markdown rendering and citation quality
**Closeout date:** 2026-11-12
**Status:** `M10_STAGE_6_STATUS = CONDITIONAL_PASS`

> Evidence scope: source inspection of the working tree, one targeted backend test run, and `tsc --noEmit`. No browser automation was executed, no screenshots were captured or inspected, and no visual acceptance is claimed. All line references are from the working tree at execution time.

---

## 1. Executive summary

The Stage 6 rendering path is present, wired, and type-safe:

- `frontend/components/chat/MarkdownRenderer.tsx` is a dependency-free React renderer. It never uses `dangerouslySetInnerHTML`, builds only React elements/text nodes, allowlists `https:`, `http:`, and `mailto:` URLs, and renders `[N]` citation tokens as chips keyed to `MessageCitationItem.citation_num`.
- Backend citation construction assigns stable `citation_num` values `1..N` and 300-character snippets; the assistant runtime emits one `retrieval_complete` event containing the full citation array, persists `MessageCitation` rows, and emits `message_complete`.
- Stage 6 is integrated in the five verified surfaces (Section 5).
- This closeout adds one defensive frontend behavior: citation accumulation now deduplicates by `citation_num`, then `chunk_id`, then `id`, in the public page, embed page, and conversations streaming parser.
- Verification: `npx tsc --noEmit` exited `0`; the targeted backend run reported **`11 passed in 0.19s`** (exit `0`).

The status remains conditional because there is no frontend component-test runner and no manual browser acceptance for this stage (Section 9).

---

## 2. Original issue and root causes

| # | Original issue | Root cause | Stage 6 resolution |
|---|---|---|---|
| 1 | Responses displayed literal escaped Markdown (`\*\*bold\*\*`, `\[1\]`) instead of formatted text. | Over-cautious local models backslash-escape Markdown punctuation. The renderer intentionally treats backslashes as text, so escapes were shown verbatim. | Backend normalization unescapes Markdown outside fenced code blocks (`markdown_normalizer.py:42-74`; equivalent logic in `context.py:64-115`), and Tier-1 forbids backslash escaping (`context.py:198`). |
| 2 | Every answer ended with a redundant “Sources / References / Citations” bibliography. | Models appended their own source list even though the UI already renders a structured citation tray from verified vector metadata. | Bibliography footer regex + stripper (`markdown_normalizer.py:20-39`; `context.py:43-61`) and an explicit Tier-1 prohibition (`context.py:199`). |
| 3 | Raw model HTML could become an injection risk if rendered with `innerHTML`. | Markdown renderers that use `dangerouslySetInnerHTML` execute model-controlled HTML. | `MarkdownRenderer` never uses `dangerouslySetInnerHTML`; raw HTML is rendered as inert text. Link URLs pass a scheme allowlist (`MarkdownRenderer.tsx:56-66`). |
| 4 | Citation badges could point at the wrong source, and repeated SSE events could append duplicate sources. | Correctness depends on `citation_num` matching between the prompt blocks and the structured payload; the public/embed handlers accumulated every event into an array. | Backend assigns `citation_num` from the same enumeration used for `[N]` prompt blocks (`context.py:175-186`); chips look up by `citation_num` (`MarkdownRenderer.tsx:336-349`); this closeout deduplicates accumulation. |
| 5 | Streaming partial Markdown could break rendering or show a blank bubble. | Token deltas arrive mid-Markdown (unclosed fences, partial lists, partial `[N]`). | The renderer re-parses memoized content on every update and tolerates unclosed structures; empty content renders a placeholder (`MarkdownRenderer.tsx:499-503`). |

---

## 3. Actual implementation

### 3.1 MarkdownRenderer contract

`frontend/components/chat/MarkdownRenderer.tsx` (517 lines):

- Props: `content`, optional `citations`, optional `onCitationClick`, optional `className` (`:23-32`).
- Block model: paragraphs, H1–H6, unordered/ordered lists, blockquotes, fenced code blocks, horizontal rules, GFM tables (`:34-42`).
- Inline model: text, bold, italic, inline code, links, and citation tokens (`:44-50`).
- Parsing is a handwritten block parser (`:157-282`) plus inline parser (`:72-151`); no third-party Markdown dependency and no new dependency was added.
- Rendering is React-only: `InlineView` (`:288-360`) and `BlockView` (`:362-487`).
- Content is parsed with `useMemo` keyed on `content` (`:499`), so citation-state updates do not re-parse text and each token update re-parses only the current accumulated content.
- Empty or whitespace-only content renders `…` (`:501-503`).

### 3.2 HTML and URL safety

- `sanitizeUrl` parses with `new URL(href, "https://SAFE_BASE")` and returns the original href only for `https:`, `http:`, or `mailto:` (`:56-66`).
- Link parsing applies the sanitizer; rejected URLs degrade to their visible label as plain text (`:106-127`).
- Rendered links use `target="_blank"` and `rel="noopener noreferrer"` (`:324-335`).
- No `dangerouslySetInnerHTML` call exists in the component. The only occurrence of the identifier is the design note at `:6`. Model-supplied HTML is therefore displayed as text, not executed.

### 3.3 Citation chips

- Inline parser recognizes `[N]` only when `N` is all digits (`:128-139`).
- `InlineView` finds the matching citation by `citation_num` and renders a keyboard-focusable button with an `aria-label` when `onCitationClick` is supplied (`:336-349`).
- If no matching citation exists, it renders muted `[N]` text instead of failing (`:351-352`).
- Backend citation objects carry `citation_num`, `chunk_id`, `document_name`, `page_number`, `heading_path`, `snippet`, `citation_text`, `score`, and `bounding_box` (`context.py:175-186`).

### 3.4 Backend normalization

`backend/app/assistant_runtime/markdown_normalizer.py` (new file, 133 lines) is the canonical normalization module:

- `BIBLIOGRAPHY_PATTERN` matches a trailing model-generated bibliography/source section (`:20-27`).
- `strip_generated_bibliography` removes it and only right-strips when a substitution occurred (`:30-39`).
- `_unescape_markdown` protects fenced code blocks via placeholders, then repairs escaped bold/italic/citation brackets and single-character Markdown punctuation (`:42-74`).
- `_normalize_spacing` inserts blank lines before headers/lists and after list blocks, then collapses 3+ newlines (`:77-113`).
- `normalize_markdown` applies bibliography stripping, CRLF conversion, spacing, then unescaping (`:116-133`).

**Runtime call site:** `backend/app/assistant_runtime/runtime.py:14` imports `normalize_markdown` from `app.assistant_runtime.context`, and `runtime.py:344` applies it to the final assistant content before persistence. `context.py` currently contains its own `normalize_markdown` implementation (`context.py:64-115`) that performs bibliography stripping and unescaping but not the spacing/CRLF passes from `markdown_normalizer.py`. This duplication is recorded as a limitation (Section 9), not changed by this closeout.

### 3.5 Tier-1 formatting instructions

`build_rag_context` prepends immutable platform instructions (`context.py:194-203`). Relevant Stage 6 clauses:

- Cite factual assertions with numeric bracket badges like `[1]`, `[2]` (`:197`).
- Use clean standard Markdown and do **not** backslash-escape Markdown syntax (`:198`).
- Never append a `Sources:`, `References:`, or `Verified Document Citations:` section (`:199`).

### 3.6 SSE and persistence contract

- `format_sse` serializes `event:` / `data:` frames (`runtime.py:28`).
- One `retrieval_complete` frame carries `citation_count` and the full `citations` array (`runtime.py:227-233`); preview uses the same shape (`runtime.py:475-481`).
- Each provider delta is emitted as `token` with `delta` (`runtime.py:300-304`).
- The final assistant content is normalized and persisted; each citation is persisted as a `MessageCitation` row with `chunk_id`, `document_name`, `citation_num`, and `citation_text` (`runtime.py:344-366`; model at `backend/app/models/conversation.py:72`).
- `message_complete` carries `message_id`, `conversation_id`, `status`, and `trace_id` (`runtime.py:402-410`).
- Message history serializes citations through `MessageCitationResponse` (`backend/app/api/v1/conversations.py:164-193`).
- `frontend/lib/api.ts` parses `token`, `retrieval_complete`, `citation`, `message_complete`, and `message_error` for authenticated chat (`:1492-1505`) and public chat (`:1715-1728`).

---

## 4. End-to-end flow verified

1. **Provider output** → `provider.generate_stream(...)` yields deltas (`runtime.py:300-304`).
2. **Runtime** → `build_rag_context(...)` receives retrieved results (`runtime.py:212-224`).
3. **Citation construction** → `build_rag_context` enumerates results from `1`, sanitizes titles/content, clips snippets to 300 characters, computes bounding boxes, and builds both `[N]` prompt blocks and the citations array (`context.py:118-189`).
4. **SSE serialization** → one `retrieval_complete` event (`runtime.py:227-233`), then `token` deltas (`:304`), then `usage` (`:392`), then `message_complete` (`:402-410`).
5. **Persistence** → normalized assistant message plus `MessageCitation` rows (`runtime.py:344-366`).
6. **Frontend parsing** → `streamChatMessage` (`api.ts:1428-1509`) and `streamPublicChat` (`api.ts:1662-1733`) dispatch callbacks.
7. **Page handlers** → each surface stores content/citations and passes them to `MarkdownRenderer` (Section 5).
8. **Rendering** → citation `[N]` tokens resolve against the stored array and become chips; matched chips invoke the surface-specific inspection action.

---

## 5. Integration surfaces verified

`MarkdownRenderer` is imported and rendered in exactly these five surfaces:

| # | Surface | Import | Render site | Citation handling |
|---|---|---|---|---|
| 1 | `frontend/app/dashboard/assistants/page.tsx` | `:41` | `:737` | `onCitations` replaces the message citation array wholesale (`:296-302`) — no accumulation. |
| 2 | `frontend/app/dashboard/assistants/AssistantCreationWizard.tsx` | `:31` | `:796` | `retrieval_complete` replaces the last assistant entry’s citations (`:179-191`) — no accumulation. |
| 3 | `frontend/app/dashboard/conversations/page.tsx` | `:38` | `:642` (persisted), `:693` (live streaming) | Local SSE parser deduplicates accumulated citations (`:308-314`). |
| 4 | `frontend/app/p/[publicId]/page.tsx` | `:22` | `:286` | `onCitations` / `onCitation` merge through `dedupeCitations` (`:125-144`). |
| 5 | `frontend/app/embed/[publicId]/page.tsx` | `:22` | `:259` | `onCitations` / `onCitation` merge through `dedupeCitations` (`:122-141`). |

The renderer itself is shared; no surface has a forked renderer.

---

## 6. Files changed

### 6.1 Stage 6 implementation set

Core rendering and normalization (per `docs/m10/M10_FINAL_GIT_INVENTORY.md` group D and verified source):

| File | Stage 6 role |
|---|---|
| `frontend/components/chat/MarkdownRenderer.tsx` | New shared renderer: block/inline parsing, URL allowlist, citation chips, streaming-safe memoization, no raw HTML. |
| `backend/app/assistant_runtime/context.py` | Citation construction, Tier-1 Markdown/citation instructions, bibliography strip and escape repair. |
| `backend/app/assistant_runtime/markdown_normalizer.py` | New canonical normalizer module: bibliography strip, escape repair, spacing, CRLF. |
| `backend/app/assistant_runtime/__init__.py` | Exports `normalize_markdown`. |
| `backend/tests/test_markdown_normalizer.py` | New 6-test normalizer suite. |

Integration edits (renderer adoption and citation state):

| File | Stage 6 role |
|---|---|
| `frontend/app/dashboard/assistants/page.tsx` | Renderer integration + citation inspection modal. |
| `frontend/app/dashboard/assistants/AssistantCreationWizard.tsx` | Renderer integration in the sandbox preview. |
| `frontend/app/dashboard/conversations/page.tsx` | Renderer integration in persisted and streaming bubbles. |
| `frontend/app/p/[publicId]/page.tsx` | Renderer integration in the public chat page. |
| `frontend/app/embed/[publicId]/page.tsx` | Renderer integration in the embed widget. |
| `backend/app/assistant_runtime/runtime.py` | Normalize-before-persist (`:344`), `retrieval_complete` (`:227-233`), citation persistence (`:356-366`), `message_complete` (`:402-410`). This file also carries M09 tracing/quota/BYOK changes, so it is not exclusively a Stage 6 file. |
| `frontend/lib/api.ts` | Stage 6 SSE callback plumbing (`retrieval_complete`, `citation`, `message_complete`) in `streamChatMessage` and `streamPublicChat`. The file also carries other M10 changes. |
| `docs/m10/M10_REMEDIATION_STAGE_6_TEST_RECONCILIATION.md` | Prior Stage 6 test reconciliation evidence. |

Note: `M10_FINAL_GIT_INVENTORY.md` group D also lists `backend/app/api/v1/conversations.py` and `backend/app/schemas/assistant.py`. Their diffs in this tree add the conversation PATCH endpoint and `ConversationUpdateRequest`, not Stage 6 Markdown/citation logic.

### 6.2 This closeout

| File | Change |
|---|---|
| `frontend/lib/citations.ts` | **New.** `dedupeCitations(existing, incoming)` merges in order, keyed by `citation_num`, then `chunk_id`, then `id`; entries with no identifier are preserved. |
| `frontend/app/p/[publicId]/page.tsx` | Added `dedupeCitations` import (`:10`); `onCitations` and `onCitation` now replace `activeCitations` with the deduplicated merge (`:125-144`). |
| `frontend/app/embed/[publicId]/page.tsx` | Same change (`:10`, `:122-141`). |
| `frontend/app/dashboard/conversations/page.tsx` | Added import (`:12`); `retrieval_complete` assignment and the per-`citation` push branch now deduplicate (`:308-314`). |
| `frontend/app/dashboard/assistants/page.tsx` | Reviewed, no change: `onCitations` replaces citations wholesale (`:296-302`); it does not accumulate across events. |
| `frontend/app/dashboard/assistants/AssistantCreationWizard.tsx` | Reviewed, no change: `retrieval_complete` replaces citations wholesale (`:179-191`). |
| `docs/m10/M10_STAGE_6_FINAL_REPORT.md` | **New.** This report. |

No backend runtime behavior was changed. No dependencies were added. No git mutations were performed. `npm run build` was intentionally not run (reserved for Stage 9).

---

## 7. Tests executed

### 7.1 Frontend type check

Command (workdir `frontend`):

```text
npx tsc --noEmit
```

Result: **exit code `0`** (no diagnostics emitted).

### 7.2 Targeted backend tests

Command (workdir `backend`):

```text
.\.venv\Scripts\python.exe -m pytest tests/test_m05_citation_highlighting.py tests/test_markdown_normalizer.py -q --tb=short
```

Exact result:

```text
...........                                                              [100%]
11 passed in 0.19s
```

Exit code: `0`. Breakdown: 5 tests in `test_m05_citation_highlighting.py` plus 6 tests in `test_markdown_normalizer.py` = 11 passed; no failures and no skips were reported.

### 7.3 Supplementary normalizer command (not a test suite)

Executed with the backend virtualenv against `markdown_normalizer.py`:

```text
normalize_markdown("Answer text.\n\nSources:\n[1] policy.pdf") -> "Answer text."
normalize_markdown("Intro\n# Heading\n\\*\\*bold\\*\\* and \\[1\\]") -> "Intro\n\n# Heading\n**bold** and [1]"
```

This confirms bibliography removal, header spacing, and escape repair in the canonical module. It does **not** exercise the runtime’s `context.normalize_markdown` path.

### 7.4 Suites not re-run here

The following suites were not re-run for this report, and no counts are claimed for them; they are part of the Stage 9 full-suite regression:

- `backend/tests/test_m10_stage2_assistant_lifecycle.py` — includes `test_11_citation_provenance_and_grounding` (mocked retrieval citation payload in `retrieval_complete`).
- `backend/tests/test_m10_stage3_knowledge_and_retrieval.py` — includes `test_17_cross_tenant_retrieval_denial_adversarial`, `test_19_public_assistant_restricted_knowledge_denial`, and `test_20_citation_provenance_and_path_redaction`.
- `backend/tests/test_retrieval_security.py` — includes `test_cross_tenant_vector_isolation`, `test_cross_tenant_fts_isolation`, `test_department_isolation_blocks_unauthorized_employee`, and `test_hybrid_retrieval_does_not_reintroduce_unauthorized_candidates`.

### 7.5 Frontend test capability

There is no frontend component-test runner: `frontend/package.json` has scripts `dev`, `build`, `start`, `lint` only (no `test` script), and no Jest/Vitest/Testing Library/Playwright/Cypress dependency or configuration. No browser automation was used and no screenshots were inspected. Checks that require rendered-DOM assertions are marked **NOT COVERED — no frontend component test runner configured (no jest/vitest; no test script in package.json)**.

---

## 8. Acceptance-test mapping (12 checks)

| # | Required check | Concrete evidence | Verdict |
|---|---|---|---|
| 1 | H1–H6 headings render as semantic heading elements. | `MarkdownRenderer.tsx:188-195` (parse), `:381-399` (render). | PASS (static). Visual typography is **MANUAL UI VERIFICATION REQUIRED**. |
| 2 | Bold and italic render as `<strong>` / `<em>`. | `MarkdownRenderer.tsx:79-95` (parse), `:303-314` (render). | PASS (static). Visual output is **MANUAL UI VERIFICATION REQUIRED**. |
| 3 | Unordered and ordered lists render, including ordered-list start values. | `MarkdownRenderer.tsx:208-230` (parse), `:401-424` (render, `start` at `:416`). | PASS (static). Visual output is **MANUAL UI VERIFICATION REQUIRED**. |
| 4 | Blockquotes and horizontal rules render. | `MarkdownRenderer.tsx:181-186`, `:197-206`, `:426-448`. | PASS (static). Visual output is **MANUAL UI VERIFICATION REQUIRED**. |
| 5 | Fenced code blocks render as inert, scrollable text with optional language label. | `MarkdownRenderer.tsx:167-179` (parse), `:433-445` (render); code is a React text child, not HTML. | PASS (static). Visual output is **MANUAL UI VERIFICATION REQUIRED**. |
| 6 | GFM tables render with header and body rows. | `MarkdownRenderer.tsx:232-253`, `:450-482`. | PASS (static). Visual output is **MANUAL UI VERIFICATION REQUIRED**. |
| 7 | Links render only for `https:`, `http:`, or `mailto:`; unsafe schemes degrade to text. | `MarkdownRenderer.tsx:56-66` (allowlist), `:106-127` (parse/fallback), `:324-335` (external-link rel). | PASS (static). Click-through is **MANUAL UI VERIFICATION REQUIRED**; **NOT COVERED — no frontend component test runner configured (no jest/vitest; no test script in package.json)**. |
| 8 | Model content cannot execute HTML; no `dangerouslySetInnerHTML`. | No call exists (only the design note at `MarkdownRenderer.tsx:6`); text tokens render as React text nodes (`:300-302`). | PASS (static). Browser XSS behavior was not exercised; **MANUAL UI VERIFICATION REQUIRED** for a real hostile-output drill. |
| 9 | Over-escaped Markdown from models is repaired before display. | `markdown_normalizer.py:42-74`; runtime path `context.py:64-115` + `runtime.py:344`; supplementary command output in §7.3. | PASS (static + supplementary command). **NOT COVERED — no frontend component test runner configured (no jest/vitest; no test script in package.json)**; no unit test asserts escape repair. |
| 10 | Redundant model-generated bibliography/source footer is removed and Tier-1 forbids it. | `markdown_normalizer.py:20-39`; `context.py:43-61`; Tier-1 clause `context.py:199`; supplementary command output in §7.3. | PASS (static + supplementary command). No unit test in `test_markdown_normalizer.py` asserts bibliography stripping; **NOT COVERED** by the 6-test suite. |
| 11 | `[N]` citations render as chips keyed to `citation_num`; clicking invokes the surface handler; unmatched numbers degrade safely. | Parse `MarkdownRenderer.tsx:128-139`; chip/fallback `:336-352`; backend numbering `context.py:175-186`; persistence `runtime.py:356-366`; `test_m10_stage2_assistant_lifecycle.py::test_11_citation_provenance_and_grounding` asserts the citation payload. | PASS (static). Backend coverage exists in the cited Stage 9 suite; click behavior is **MANUAL UI VERIFICATION REQUIRED**. |
| 12 | Streaming partial tokens render without crashing, and repeated citation events do not duplicate sources. | `useMemo` + empty placeholder `MarkdownRenderer.tsx:499-503`; dedupe helper `frontend/lib/citations.ts:3-28`; handlers `p/[publicId]/page.tsx:125-144`, `embed/[publicId]/page.tsx:122-141`, `conversations/page.tsx:308-314`. | PASS (static). Event-timing behavior is **MANUAL UI VERIFICATION REQUIRED**; **NOT COVERED — no frontend component test runner configured (no jest/vitest; no test script in package.json)**. |

---

## 9. Known limitations

1. **No frontend component-level tests.** There is no Jest/Vitest setup and no `test` script. Rendering, click, and event-timing claims above are source-inspection claims, not executed DOM assertions.
2. **Dead SSE branches in the conversations page.** `frontend/app/dashboard/conversations/page.tsx:308` accepts a per-`citation` event and `:315-316` accepts `message_end`; the backend emits neither. The backend contract is `message_start`, `retrieval_start`, `retrieval_complete`, `token`, `usage`, `message_complete`, and `message_error` (`runtime.py:101`, `:162`, `:227`, `:304`, `:392`, `:402`, and error paths). `message_complete` is handled inside `lib/api.ts:1501` but the conversations page’s local parser relies on stream end and a history reload.
3. **First-match citation lookup.** `MarkdownRenderer.tsx:337` uses `.find()`. If a payload contained duplicate `citation_num` values, every `[N]` chip would resolve to the first match. Backend numbering is 1..N so this is currently cosmetic, not a live defect.
4. **Normalizer duplication (D1/D2).** The runtime imports `normalize_markdown` from `context.py`, not from `markdown_normalizer.py`. The 6 passing `test_markdown_normalizer.py` tests therefore validate a module that is not the runtime import. `context.py` lacks the spacing/CRLF passes that `markdown_normalizer.py` has. Wiring the two is outside this closeout’s allowed backend changes.
5. **Streaming tokens are not normalized.** `runtime.py:304` emits raw provider deltas; normalization is applied only to the final persisted content at `runtime.py:344`. A live stream can temporarily show escaped Markdown or a model bibliography until the persisted message is reloaded.
6. **Inline-code escapes are not protected.** `_unescape_markdown` protects fenced code blocks only (`markdown_normalizer.py:49-60`); backslash escapes inside single-backtick inline code are unescaped. This is a minor fidelity issue.
7. **Dedupe scope.** Dedupe applies only where citations accumulate. The assistants page and creation wizard replace the citation array on `retrieval_complete`, so they do not need it and were not changed. If those surfaces later switch to append semantics, they must adopt the helper.

---

## 10. Residual risk

- The frontend fix is type-checked but not runtime-tested. A regression in the dedupe key precedence or handler wiring would not be caught until manual UI verification or a future component-test harness.
- The 11 passing backend tests do not prove the runtime normalizer behavior, because the tested module and the runtime import are different implementations (limitation 4).
- Citation payload contract changes (for example, omitting all of `citation_num`, `chunk_id`, and `id`) would preserve duplicates rather than collapse them; the helper deliberately keeps unidentifiable entries instead of dropping data.
- Cross-surface visual consistency (five surfaces, different bubbles/trays) remains unverified without browser inspection.
- The working tree contains concurrent uncommitted M09/M10 work; the test run and line references are a snapshot of this tree on 2026-11-12, not a committed revision.

---

## 11. Status

```text
M10_STAGE_6_STATUS = CONDITIONAL_PASS
```

Implementation and integration are verified by source inspection and type checking; targeted backend tests pass (`11 passed in 0.19s`); automated frontend component coverage is absent; manual UI acceptance for rendering, citation clicks, and streaming remains pending.