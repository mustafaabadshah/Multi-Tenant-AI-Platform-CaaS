# Platform Technical Roadmap — Milestones M01 through M10

**Status Reference:** Milestone M08 Active Execution  

---

## Milestone Execution Summary

```
[M01-M03] Core Monolith & RBAC & Ingestion ────────► COMPLETE (Commit 448431c)
[M04] Conversational RAG Engine ───────────────────► COMPLETE (Commit 448431c)
[M05] Enterprise Verification & Deployment ────────► CONDITIONAL_PASS (Commit 4f75f68)
[M06] Assistant Studio & 12 Templates ─────────────► COMPLETE (Commit 9595339)
[M07] Knowledge Studio & BYOK Key Vault ───────────► COMPLETE (Commit ad46a44)
[M08] Public Publishing, Embeds & Developer API ──► IN PROGRESS (Current)
[M09] Evaluations, Tracing & Durable Queues ───────► FUTURE (Post-M08)
[M10] Enterprise Fleet Management & White-Label ───► FUTURE
```

---

## Detailed Milestone Scope

### M08: Public Assistant Publishing, Embed Widgets, Developer API & SDKs (Current)
- Feature A: Assistant Publishing Lifecycle (Private, Workspace, Public)
- Feature B: Secure Public Assistant Web Page (`/p/{public_id}`)
- Feature C: Website Embed Widget (Iframe isolation, domain whitelist, brand customization)
- Feature D: Public Access Security (IP rate limiting, publication quotas, immediate revocation)
- Feature E: Developer API Keys (Cryptographic generation, SHA-256 hashing, scoped permissions)
- Feature F: Developer REST API (`/api/v1/developer/*`)
- Feature G: Official Lightweight SDKs (TypeScript `@mmaip/client` & Python `mmaip`)
- Feature H: Usage Accounting Extension (`traffic_type` & `credential_source`)
- Feature I: Public Session Privacy & Isolation
- Feature J: Assistant Studio Integration (Publish Tab, Embed snippet generator)
- Feature K: RBAC Permissions (`ASSISTANT_PUBLISH`, `API_KEY_MANAGE`)

### M09: Evaluations, Quality Observability & Durable Ingestion (Deferred Future Scope)
- Automated RAG quality evaluation harness (faithfulness, hallucination, answer relevance)
- Human feedback review workflows (thumbs up/down, user comments)
- Distributed Celery/Redis queue for high-volume document ingestion jobs
- OpenTelemetry distributed tracing and latency profiling
- Live disaster recovery drills (PostgreSQL restore and Qdrant index rebuild)

### M10: Enterprise Fleet Management & White-Labeling (Future Scope)
- Custom domain mapping (`cname.customer.com`)
- White-label branding removal
- Enterprise SAML/SSO (Okta, Azure AD) integration
- Multi-region active-active database clustering
