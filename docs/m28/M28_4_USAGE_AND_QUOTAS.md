# M28.4 — Tenant Quota and Usage Dashboard Technical Report

**Milestone:** M28.4  
**Project:** Multi-Tenant AI Platform (CaaS)  
**Workspace:** `E:\MM Office\Multi-Tanant-CaaS`  
**Repository:** `https://github.com/mustafaabadshah/Multi-Tenant-AI-Platform-CaaS`  
**Date:** November 17, 2026  
**Status:** IMPLEMENTED & TESTED (PASS)  

---

## 1. Overview & Architectural Rationale

M28.4 delivers authoritative tenant usage accounting and visual capacity gauges. The goal is to provide operators and workspace admins with real-time insight into resource consumption across tokens, daily API requests, storage allocation, and knowledge base document counts.

### Key Principles:
1. **Authoritative Backend Data:** Metrics are derived directly from the PostgreSQL relational store and active Redis token counters. No expensive whole-bucket S3/B2 file system scans on every page load.
2. **Zero Inaccurate Billing Claims:** Estimated inference usage is never labeled as a finalized billed dollar invoice.
3. **Safe Division & Bounded Percentages:** All progress bars protect against division by zero, NaN states, and negative values. Percentages are clamped between 0% and 100%.

---

## 2. Quota Service Extension

Extended `get_usage_summary()` in `backend/app/services/quota_service.py`:
- Aggregates document count:
  ```python
  doc_count = await self.session.scalar(
      select(func.count(Document.id)).where(Document.tenant_id == self.tenant_id)
  )
  ```
- Aggregates storage bytes from processed documents and attachments:
  ```python
  doc_bytes = await self.session.scalar(
      select(func.coalesce(func.sum(Document.file_size_bytes), 0)).where(Document.tenant_id == self.tenant_id)
  )
  att_bytes = await self.session.scalar(
      select(func.coalesce(func.sum(ConversationAttachment.file_size_bytes), 0)).where(ConversationAttachment.tenant_id == self.tenant_id)
  )
  ```
- Evaluates active assistants and max limits based on tenant type (`ORGANIZATION` vs `INDIVIDUAL`).
- Attaches UTC measurement timestamps and billing reset dates.

### Schema: `ProviderUsageSummaryResponse`
Added fields to `backend/app/schemas/provider.py`:
- `storage_bytes_used: int`
- `storage_bytes_limit: int` (Default: 10 GB = 10,737,418,240 bytes)
- `document_count: int`
- `document_limit: int` (Default: 500 documents)
- `active_assistants: int`
- `max_assistants: int`
- `measurement_timestamp: Optional[str]`
- `reset_timestamp: Optional[str]`

---

## 3. UI Usage Gauge Widgets

Built in `frontend/app/dashboard/settings/page.tsx`:
1. **Monthly Token Budget:** Displays formatted used vs limit tokens, with color-shifting progress bar (Blue → Amber when >70% → Red when >90%).
2. **Daily Request Meter:** Tracks today's API consumption against rate limit windows.
3. **Storage Budget:** Dynamically formats bytes into KB, MB, or GB.
4. **Knowledge Base Documents:** Tracks corpus items loaded into vector and keyword search indices.
5. **Renewal Information:** Shows billing cycle renewal date cleanly formatted.

---

## 4. Verification Evidence

Tested via `backend/tests/test_m28_beta_and_quota.py`:
- `test_quota_service_usage_summary`: Verified accurate calculation of storage bytes, document counts, token usage, and percentage clamping without database errors or cross-tenant leaks.

**Verdict:** `M28_4_USAGE = PASS`
