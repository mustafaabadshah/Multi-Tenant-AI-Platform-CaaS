# M28.2 Git Baseline and Working-Tree Preservation

## 1. Identity & Baseline Verification

- **Workspace:** `E:\MM Office\Multi-Tanant-CaaS`
- **Git Branch:** `main`
- **Remote Git HEAD:** `e1d82d8def8a8d79cdd215731ab701960b00d528` (verified identical to local HEAD `e1d82d8def8a8d79cdd215731ab701960b00d528`)
- **Remote Repository:** `https://github.com/mustafaabadshah/Multi-Tenant-AI-Platform-CaaS`

## 2. Working Tree Inventory

### Modified Files (Core Milestone Enhancements)
- `backend/app/api/v1/conversations.py`: Message feedback endpoints and rating aggregation.
- `backend/app/api/v1/router.py`: Registered feedback and beta routers.
- `backend/app/assistant_runtime/context.py`: Citation serialization with accurate page/url provenance.
- `backend/app/assistant_runtime/runtime.py`: Source-aware intent grounding, Markdown code-block/quote filtering for preflight URLs.
- `backend/app/models/__init__.py`: Registered `MessageFeedback` model.
- `backend/app/models/conversation.py`: `MessageFeedback` entity with tenant scoping, composite indexes, and unique constraints.
- `backend/app/parsers/__init__.py`: HTML parser registration in parser registry.
- `backend/app/parsers/csv_parser.py`: Safe parsing delimiter sniffing.
- `backend/app/parsers/registry.py`: Typed `UnsupportedFormatError` raising instead of generic retryable errors.
- `backend/app/schemas/provider.py`: Extended provider schemas.
- `backend/app/services/ingestion/limits.py`: Added `UnsupportedFormatError` and `UnparseableDocumentError` to `PERMANENT_INGESTION_ERRORS`.
- `backend/app/services/ingestion/service.py`: Classified format errors as permanent, preserving retryability for transient exceptions.
- `backend/app/services/quota_service.py`: Quota calculations and token tracking.
- `backend/app/services/web/kb_saver.py`: Streamlined Save-to-Knowledge Base workflow.
- `backend/app/services/web/reader.py`: SSRFSafeAsyncTransport integration and chunked 2 MiB streaming limit.
- `backend/app/services/web/ssrf.py`: Connection-level socket peer IP verification via `SSRFSafeNetworkBackend`.
- `frontend/app/dashboard/assistants/page.tsx`: Simplified assistant creation wizard with sensible defaults.
- `frontend/app/dashboard/conversations/page.tsx`: Conversation Studio UI with feedback thumbs, starter chips, and accurate citations.
- `frontend/app/dashboard/layout.tsx`: 3-tier navigation (Core, Management, Advanced).
- `frontend/app/dashboard/page.tsx`: Welcome banner and quick-action cards for first-time users.
- `frontend/app/dashboard/settings/page.tsx`: Settings reorganization.
- `frontend/lib/api.ts`: API clients for message feedback and beta operations.

### Untracked Additions
- `backend/alembic/versions/0018_m28_message_feedback.py`: Alembic revision for message feedback table.
- `backend/app/api/v1/beta.py`: Beta cohort and tester management router.
- `backend/app/parsers/html.py`: HTML Parser extracting semantic tags, code blocks, and headings without script/style tags.
- `backend/app/schemas/feedback.py`: Pydantic models for rating submissions and triage status.
- `backend/app/services/feedback_service.py`: Service managing tenant-isolated feedback upserts and aggregates.
- `backend/tests/test_m28_1_html_and_web_repair.py`: 11 targeted tests covering HTML parsing, SSRF connection defense, and source-aware grounding.
- `backend/tests/test_m28_beta_and_quota.py`: Tests for beta cohorts and quota accounting.
- `backend/tests/test_m28_message_feedback.py`: Tests for feedback upsert, cross-tenant isolation, and telemetry.
- `frontend/app/dashboard/beta/page.tsx`: Beta console view.
- `frontend/app/dashboard/evaluations/page.tsx`: Evaluation Studio view.

## 3. Preservation Status
All milestones M01 through M28.1 functionality, security invariants, and test suites are fully preserved. No files were deleted or overwritten destructively.
