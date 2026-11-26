# M20 Initial Architecture Audit: Model Context Protocol (MCP) & Agentic Runtime

## 1. Executive Summary

Milestone M20 transforms the platform from a conversational RAG platform into an extensible, tool-using AI agent platform. It introduces Model Context Protocol (MCP) host capability, encrypted credential management for third-party MCP endpoints, human-in-the-loop approvals for mutating operations, and a bounded agentic execution loop within the existing `AssistantRuntime`.

---

## 2. Verified Architectural Findings

### 2.1 Existing Assistant Runtime & Streaming State
- **Inspection Targets:** `backend/app/assistant_runtime/runtime.py`, `backend/app/llm/providers/`, `backend/app/llm/base.py`.
- **Strengths:**
  - Robust SSE streaming pipeline (`message_start`, `token`, `usage`, `message_complete`, `message_error`).
  - Atomic quota checking and reservations.
  - Multi-tenant conversation isolation and message storage.
- **Identified Gaps Before M20:**
  1. Assistant runtime was strictly linear: `Retrieval -> System Prompt -> LLM Stream -> Citations -> Complete`. It lacked capability to interpret model tool calls, pause for human approval, execute external tools, or feed tool observations back into the context.
  2. No entity or mechanism existed for connecting to external Model Context Protocol (MCP) servers.
  3. No human-in-the-loop approval mechanism existed in PostgreSQL to halt and resume mutating or high-risk actions.
  4. Remote MCP URLs represent an extreme SSRF vulnerability surface requiring network validation, payload capping, and schema fingerprinting.

---

## 3. Scope of M20 Implementation

1. **Protocol & Connectivity:**
   - Official Python MCP SDK (`mcp>=2.3.0`) installed and pinned in dependencies.
   - Streamable HTTP client implementation with defense-in-depth SSRF validation.
2. **Database Models & Alembic Migration:**
   - `MCPConnection`: Stores server URL, capabilities, approved tools, encrypted credentials, and tenant/user scopes.
   - `ToolApproval`: PostgreSQL-backed durable human approval records with single-use tokens and 15-minute expirations.
   - `ToolInvocationLog`: Audit and observability log tracking execution time, arguments, and outcomes.
   - Migration `0015_m20_mcp_agentic_runtime.py` (`down_revision = '0014_m19_tool_registry'`).
3. **Agentic Tool Execution State Machine:**
   - Multi-step bounded loop (`max_agent_steps = 5`) in `AssistantRuntime.stream_chat`.
   - Typed SSE events: `tool_call_proposed`, `tool_approval_required`, `tool_call_started`, `tool_call_completed`, `tool_call_failed`.
4. **Human Approval Safeguards:**
   - `ToolApprovalService`: Replay rejection, tenant scoping, single-use token consumption, and expiry enforcement.
5. **API Surface:**
   - `/api/v1/mcp/connections`: Manage MCP connections and discover remote tools.
   - `/api/v1/approvals`: Inspect, approve, and deny pending tool operations.
