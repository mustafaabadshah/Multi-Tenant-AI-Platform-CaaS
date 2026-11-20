# M28.12 Tool Security & Provider Compatibility Matrix

## 1. Tool Security Hardening

In accordance with Prime Directive 1 (Multi-Tenant Isolation) and security audit requirements:

### A. Rejection of Unknown or Disabled Tools
- **Previous Risk:** If the LLM returned a tool call for an unknown tool name (`tc_name`), the runtime defaulted to `risk_level = "READ_ONLY"` and attempted execution via `tool_svc.execute_tool(tc_name, tc_args)`.
- **Hardened Standard:**
  ```python
  tool_def = next((t for t in raw_tools if t["name"] == tc_name), None)
  if not tool_def:
      logger.warning(f"Rejecting unregistered or unauthorized tool '{tc_name}' for tenant {self.tenant_id}")
      yield format_sse("tool_call_failed", {
          "tool_name": tc_name,
          "error": f"Tool '{tc_name}' is not registered or not permitted.",
      })
      messages.append(LLMMessage(role="tool", content=f"Error: Tool '{tc_name}' is not registered or not permitted.", tool_call_id=tc_id))
      continue
  ```
  Unknown tools are rejected immediately before execution, with zero risk of privilege escalation or bypassing approval.

### B. Mandatory Human Approval on Write / High-Risk Tools
- Any tool definition with `risk_level in ("WRITE", "HIGH_RISK")`, `requires_approval = True`, or when `require_approval_all = True` pauses execution and creates a cryptographic approval token via `ToolApprovalService`.
- Execution halts until approved by authorized tenant personnel.

---

## 2. Multi-Provider Compatibility Matrix

| Provider | Model Family | Native Tool-Calling | Stream Protocol | Tool-Choice Configuration | Fallback Behavior |
|---|---|---|---|---|---|
| **Groq** | `openai/gpt-oss-120b` | Yes | SSE / OpenAI wire format | Explicit `tool_choice="auto"` when tools present | Single-pass safe retry without tools on conflict |
| **Groq** | `llama-3.3-70b-versatile` | Yes | SSE / OpenAI wire format | Explicit `tool_choice="auto"` | Safe retry without tools |
| **Groq** | `mixtral-8x7b-32768` | No | SSE | No tools advertised (`tools=None`) | Deterministic preflight fulfills search |
| **OpenAI** | `gpt-4o`, `gpt-4o-mini` | Yes | OpenAI wire format | `tool_choice="auto"` | Native function calling |
| **Anthropic** | `claude-3-5-sonnet` | Yes | Anthropic tool blocks | Tool schemas mapped to Anthropic specs | Native tool execution |
| **OmniRoute**| Local Gateway | Dynamic (depends on backend model) | OpenAI-compatible stream | Standard `tools` + `tool_choice="auto"` | Graceful fallback on upstream rejection |

---

## 3. Truthful arXiv Integration & Rate Limiting

- **Endpoint:** `https://export.arxiv.org/api/query`
- **Rate Limit Policy:** 3.0s interval enforced via process-level `asyncio.Lock`.
- **User-Agent:**
  - Configurable via `ARXIV_USER_AGENT` or `ARXIV_CONTACT_EMAIL`.
  - Truthful fallback: `MultiTenantAIPlatform/1.0 (academic search; terms-compliant; https://github.com/mustafaabadshah/Multi-Tenant-AI-Platform-CaaS)`.
  - Zero invented email addresses; fully compliant with arXiv API terms.
