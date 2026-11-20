# M28.2 Feedback, Evaluation & Operations Audit

## 1. Message Feedback Architecture
- **Model:** `MessageFeedback` (`backend/app/models/conversation.py`).
  - Columns: `id` (UUID), `tenant_id` (UUID), `message_id` (UUID), `user_id` (UUID), `rating` (VARCHAR: `up`/`down`), `comment` (TEXT), `tags` (JSONB), `status` (VARCHAR: `new`, `triaged`, `addressed`), `created_at`, `updated_at`.
  - Composite Unique Constraint: `uq_feedback_msg_user (tenant_id, message_id, user_id)` guarantees one user's rating on a message never overwrites another user's rating.
  - Multi-Tenant Scoping: Queries strictly filtered by `tenant_id`. Cross-tenant feedback submissions or queries return 404 or 403.
- **Service:** `FeedbackService` (`backend/app/services/feedback_service.py`).
  - Idempotent upserts.
  - Telemetry computation (net rating score, up/down ratios, response time correlations).
  - Triage lifecycle transitions (`new` -> `triaged` -> `addressed`).

## 2. Evaluation Studio Integrity
- **Metric Computation:**
  - Recall and faithfulness are computed deterministically against benchmark datasets with ground truth annotations.
  - Latency is measured from actual monotonic timestamps (`start_time` to `end_time`), avoiding synthetic or fabricated timings.
  - No hidden paid LLM-as-a-judge calls: when ground truth is absent, status is accurately recorded as `NOT_EVALUATED`.
  - Dataset versioning records assistant configuration, model ID, and parameter snapshots.

## 3. Beta Operations & Quota Accounting
- **Beta Operations:** Cohorts and testers are scoped strictly to the authenticated tenant. Feedback streams allow administrators to review tester commentary with role-based redactions.
- **Quota Accounting:** Authoritative tracking via PostgreSQL aggregations. Storage counters query active, non-deleted files. Tokens match recorded usage logs. No fake or hardcoded percentages.

## 4. Test Verification
- `test_submit_thumbs_up_feedback`: Submits feedback and verifies DB persistence.
- `test_update_feedback_idempotent`: Idempotent rating update without creating duplicate rows.
- `test_feedback_on_user_message_rejected`: Rejects feedback targeting user messages (only assistant responses accept feedback).
- `test_cross_tenant_feedback_denied`: Confirms cross-tenant isolation.
- `test_feedback_telemetry_accuracy`: Confirms percentage calculation and net score math.
- `test_admin_feedback_stream_and_status_lifecycle`: Validates triage status updates.
- `test_quota_service_usage_summary`: Verifies token and storage aggregates.
- `test_beta_cohort_endpoint`: Verifies beta cohort CRUD operations.

## 5. Gate Assessment
**M28_QUALITY_OPERATIONS = PASS**
Feedback, evaluation metrics, beta operations, and quotas function with strict multi-tenant isolation and mathematical accuracy.
