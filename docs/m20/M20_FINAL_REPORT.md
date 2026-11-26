# M20 Final Milestone Report: MCP Integrations, Tool Calling & Agentic Runtime

**Milestone Verdict:** `LOCAL_PASS_STAGING_APPROVAL_REQUIRED`
**Git Branch:** `main`
**Alembic Migration Chain:** `0011` -> `0012` -> `0013` -> `0014` -> `0015_m20_mcp_agentic_runtime`
**Test Suite:** `backend/tests/test_m20_mcp_agentic.py` (6/6 passed in 18.15s)
**Cumulative Regression Suite:** M16 + M17 + M18 + M19 + M20 (31/31 passed in 35.86s)
**Frontend Build:** Next.js 16.4.5 production build passed with all 20 routes static/partial prerendered.

---

## 1. Executive Summary

Milestone M20 delivers a comprehensive agentic tool-execution runtime and Model Context Protocol (MCP) host integration. The platform enables multi-tenant assistants to discover remote tools over Streamable HTTP, dynamically call tools during conversation turns, enforce strict human-in-the-loop approvals for sensitive actions, and observe every step with durable database records and streaming SSE events.

---

## 2. Key Architecture & Security Implementations

### 2.1 Protocol Compliance & MCP Client
- **SDK & Transport:** Pinned `mcp>=2.3.0` in `backend/pyproject.toml`. Standardized on remote Streamable HTTP JSON-RPC 2.0 transport without executing dangerous local shell/stdio subprocesses on Render.
- **SSRF Defense Boundary:** Every MCP endpoint undergoes outbound URL validation (`validate_outbound_url`), blocking loopback, private subnets, link-local addresses, and cloud provider metadata IPs (`169.254.169.254`).
- **Tool Discovery & Schema Fingerprinting:** `MCPClientService.discover_tools()` computes deterministic SHA-256 fingerprints of tool input schemas (`schema_fingerprint`) to pin tool identities and prevent silent remote schema drift or malicious payload modification.
- **Risk Classification Heuristics:** Tools are automatically classified into `READ_ONLY`, `WRITE`, or `HIGH_RISK` based on actions (transfers, deletions, privilege grants, mutations) to automatically trigger human approval requirements.

### 2.2 Human-in-the-Loop Approval Safeguards
- **Service:** `ToolApprovalService` in `backend/app/services/tools/approval_service.py`.
- **Durable Persistence:** Pending actions are stored in PostgreSQL (`tool_approvals` table) with:
  - Cryptographically secure single-use token (`appr_...`).
  - 15-minute expiration policy (`expires_at`).
  - Strict tenant and user isolation: Users from Tenant B or unauthorized actors cannot view or approve pending actions.
- **Replay Protection:** Once approved and consumed, subsequent approval attempts fail with `ValueError("This tool action has already been approved and executed (replay prevented).")`.

### 2.3 Agentic Runtime Orchestration
- **Runtime:** `AssistantRuntime.stream_chat()` in `backend/app/assistant_runtime/runtime.py`.
- **Bounded State Machine:** Caps tool-calling loops to `max_agent_steps = 5` to prevent infinite recursion, uncontrolled token burn, or cyclical calls.
- **SSE Events:** Emits typed, backward-compatible SSE streams:
  - `tool_call_proposed`: Arguments and requested tool name.
  - `tool_approval_required`: Emitted when mutating/high-risk tool is invoked; execution pauses safely until human decision.
  - `tool_call_started`: Dispatched once tool execution commences.
  - `tool_call_completed`: Sanitized output summary incorporated back into LLM context.
  - `tool_call_failed`: Error message handled gracefully without crashing the assistant stream.
- **Observability:** Records every tool invocation in `tool_invocation_logs` with duration in milliseconds, status, arguments summary, and correlated `trace_id`.

---

## 3. Automated Verification Evidence

### 3.1 M20 Acceptance Test Suite (`backend/tests/test_m20_mcp_agentic.py`)
```
backend\tests\test_m20_mcp_agentic.py::test_mcp_connection_ssrf_boundary_and_tenant_isolation PASSED [ 16%]
backend\tests\test_m20_mcp_agentic.py::test_mcp_client_tool_risk_inference_and_schema_fingerprint PASSED [ 33%]
backend\tests\test_m20_mcp_agentic.py::test_mcp_tool_discovery_mock PASSED [ 50%]
backend\tests\test_m20_mcp_agentic.py::test_human_approval_service_lifecycle_and_replay_rejection PASSED [ 66%]
backend\tests\test_m20_mcp_agentic.py::test_agentic_tool_execution_flow_in_assistant_runtime PASSED [ 83%]
backend\tests\test_m20_mcp_agentic.py::test_agentic_approval_gating_pauses_execution PASSED [100%]

============================= 6 passed in 18.15s ==============================
```

### 3.2 Master Regression Suite Across All Milestones (M16 - M20)
```
backend\tests\test_m16_security.py::test_session_creation_and_rotation PASSED [  3%]
backend\tests\test_m16_security.py::test_refresh_token_replay_detection PASSED [  6%]
backend\tests\test_m16_security.py::test_session_logout_and_revocation PASSED [  9%]
backend\tests\test_m16_security.py::test_logout_all_sessions PASSED      [ 12%]
backend\tests\test_m16_security.py::test_invitation_lifecycle_and_tenant_gating PASSED [ 16%]
backend\tests\test_m16_security.py::test_invitation_cancellation PASSED  [ 19%]
backend\tests\test_m16_security.py::test_cross_tenant_invitation_denial PASSED [ 22%]
backend\tests\test_m17_reliability.py::test_durable_quota_reservation_lifecycle PASSED [ 25%]
backend\tests\test_m17_reliability.py::test_stale_reservation_expiration PASSED [ 29%]
backend\tests\test_m17_reliability.py::test_observability_postgresql_authoritative_no_fallback PASSED [ 32%]
backend\tests\test_m17_reliability.py::test_observability_cancellation_separation_and_metrics_aggregation PASSED [ 35%]
backend\tests\test_m17_reliability.py::test_rate_limit_client_identity_and_scoping PASSED [ 38%]
backend\tests\test_m17_reliability.py::test_storage_key_duplicate_tenant_prefix_handling PASSED [ 41%]
backend\tests\test_m18_rag_evaluation.py::test_retrieval_ranking_mathematical_metrics PASSED [ 45%]
backend\tests\test_m18_rag_evaluation.py::test_citation_trust_and_unsupported_claim_detection PASSED [ 48%]
backend\tests\test_m18_rag_evaluation.py::test_abstention_and_completeness_metrics PASSED [ 51%]
backend\tests\test_m18_rag_evaluation.py::test_seed_benchmarks_and_tenant_isolation PASSED [ 54%]
backend\tests\test_m18_rag_evaluation.py::test_end_to_end_evaluation_run_and_comparison PASSED [ 58%]
backend\tests\test_m19_tools.py::test_ssrf_security_boundary_blocks_dangerous_targets PASSED [ 61%]
backend\tests\test_m19_tools.py::test_ssrf_validator_allows_valid_public_domain PASSED [ 64%]
backend\tests\test_m19_tools.py::test_safe_builtin_calculator PASSED     [ 67%]
backend\tests\test_m19_tools.py::test_synthetic_weather_lookup PASSED    [ 70%]
backend\tests\test_m19_tools.py::test_group_membership_lifecycle_and_cross_tenant_isolation PASSED [ 74%]
backend\tests\test_m19_tools.py::test_tool_registry_builtin_and_custom_tools PASSED [ 77%]
backend\tests\test_m19_tools.py::test_tools_api_endpoints_and_cross_tenant_denial PASSED [ 80%]
backend\tests\test_m20_mcp_agentic.py::test_mcp_connection_ssrf_boundary_and_tenant_isolation PASSED [ 83%]
backend\tests\test_m20_mcp_agentic.py::test_mcp_client_tool_risk_inference_and_schema_fingerprint PASSED [ 87%]
backend\tests\test_m20_mcp_agentic.py::test_mcp_tool_discovery_mock PASSED [ 90%]
backend\tests\test_m20_mcp_agentic.py::test_human_approval_service_lifecycle_and_replay_rejection PASSED [ 93%]
backend\tests\test_m20_mcp_agentic.py::test_agentic_tool_execution_flow_in_assistant_runtime PASSED [ 96%]
backend\tests\test_m20_mcp_agentic.py::test_agentic_approval_gating_pauses_execution PASSED [100%]

============================= 31 passed in 35.86s =============================
```

### 3.3 Frontend Production Verification
```
▲ Next.js 16.4.5 (Turbopack)
✓ Compiled successfully in 5.4s
  Running TypeScript ...
  Finished TypeScript in 9.0s ...
✓ Generating static pages using 3 workers (20/20) in 7.5s
```

---

## 4. Staging Release Gate & Verdict

- **Status:** Complete locally.
- **Verdict:** `LOCAL_PASS_STAGING_APPROVAL_REQUIRED`
- **Linear Migration Ready:** `0015_m20_mcp_agentic_runtime.py` (`down_revision = '0014_m19_tool_registry'`).
- **Safety Policy:** All changes remain in local workspace. No unapproved Git pushes, Render deploys, or live database mutations have been executed.
