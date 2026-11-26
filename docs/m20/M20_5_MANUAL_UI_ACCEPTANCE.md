# M20.5 — Operator Manual UI Acceptance Hand-Off

## 1. Hand-Off Routes for Operator Review

The operator should log into the live staging frontend and manually inspect the following views:

| Route | Live URL | Focus Areas for Verification |
|---|---|---|
| **Integrations** | `https://mmaip-frontend.onrender.com/dashboard/integrations` | Add MCP Server modal, URL validation, authentication mode selection, empty state, safe messaging when MCP is disabled. |
| **Tools** | `https://mmaip-frontend.onrender.com/dashboard/tools` | Built-in tools list (`calculator`, `weather_lookup`), Custom Tool Builder, JSON schema preview, risk badge. |
| **Assistants** | `https://mmaip-frontend.onrender.com/dashboard/assistants` | Assistant detail view, Tools & Integrations tab, tool checkboxes, max iterations input, approval policy toggle. |
| **Conversations** | `https://mmaip-frontend.onrender.com/dashboard/conversations` | Assistant chat interface, smooth streaming tokens, in-chat approval cards (when tool approval is required). |
| **Observability** | `https://mmaip-frontend.onrender.com/dashboard/observability` | Traces list, latency/token charts, filter by status, detail drawer with span timeline. |

---

## 2. Operator Checklist

- [ ] Light mode theme renders cleanly without dark artifacts.
- [ ] Navigation sidebar links to `/dashboard/integrations` and `/dashboard/tools` are present and functional.
- [ ] No non-functional or dummy placeholder buttons exist.
- [ ] All forms validate inputs before submission.
- [ ] Sensitive keys/tokens are marked as write-only and never redisplayed in plain text.

---

## 3. Current Acceptance State

**Technical Status:** `M20_5_LIVE_TECHNICAL_PASS_MANUAL_UI_PENDING`

The release candidate is completely validated through automated synthetic API, database, and route testing. Final formal release sign-off will transition to `M20_5_RELEASE_PASS` upon operator manual review.
