# M10 Stage 4 — First-Class Conversation Experience & Chat UX Specification

**Project:** Multi-Tenant AI Assistant Platform (Chatbot-as-a-Service / CaaS)  
**Workspace:** `E:\MM Office\Multi-Tanant-CaaS`  
**Milestone:** M10 Stage 4 (Stage 4D Focus)  
**Route:** `/dashboard/conversations`  
**Reference Design:** WoiceAI (`AgentChat.tsx`)  
**Date:** 2026-11-10  
**Status:** IMPLEMENTED  

---

## 1. Executive Summary

In M10 Stage 4, the conversational interface was transformed from an embedded sub-view within the assistant settings into a dedicated, first-class top-level workspace (`/dashboard/conversations`). The architecture directly couples real-time Server-Sent Events (SSE) streaming with multi-tenant RAG evidence grounding, providing operators with a high-craft chat workspace that mirrors WoiceAI's visual clarity.

---

## 2. Dual-Pane Workspace Architecture

```
+-----------------------------------------------------------------------------------------------------------------------+
| Topbar: Active Workspace Pill | Tenant Slug | Tenant Isolated Pill | RBAC & BYOK Status                               |
+-----------------------------------------------------------------------------------------------------------------------+
| LEFT PANE: Conversations Sidebar (w-80)             | RIGHT PANE: First-Class Active Chat Canvas                      |
|                                                     |                                                                 |
| • Header: "Conversations" (Icon) + [+ New Chat]     | • Header: Assistant Avatar | Assistant Name | Provider Badge  |
| • Assistant Selector: Filter by persona or "All"    |   Conversation Title | [Trash2 Delete / Clear Chat]           |
| • Search Input: Real-time title query filter        |                                                                 |
|                                                     | • Message Scroll View:                                          |
| • Scrollable Conversation Cards:                    |   - User Bubble: Aligned right, blue-600 background,           |
|   - Active highlight (border-blue-500, ring-1)      |     white text, rounded-2xl rounded-tr-none, timestamp        |
|   - Title display with inline rename input          |                                                                 |
|   - Assistant chip + last updated date              |   - Assistant Card: Aligned left, white surface, subtle       |
|   - Quick hover actions: [Edit2 Rename] [Trash2]    |     gray border, markdown rendering with code blocks & copy,    |
|                                                     |     streaming cursor animation, execution metadata            |
| • Empty State: Helpful guidance to start first chat |                                                                 |
|                                                     |   - References & Citations Tray:                               |
|                                                     |     Clickable source chips: [FileText Doc.pdf (p. 2)]          |
|                                                     |     Clicking opens verified chunk inspector modal             |
|                                                     |                                                                 |
|                                                     | • Bottom Sticky Prompt Bar:                                     |
|                                                     |   - Auto-expanding message textarea                            |
|                                                     |   - Enter to send, Shift+Enter for new line                    |
|                                                     |   - [Square Stop Generation] during active SSE stream          |
|                                                     |   - [Send] button with primary accent                          |
|                                                     |   - Grounding guarantee: "Multi-Tenant RAG Grounded"           |
+-----------------------------------------------------------------------------------------------------------------------+
```

---

## 3. Core Functional Capabilities

### 3.1 Conversation Lifecycle & Management
- **List & Filter:** Loads all tenant conversations via `api.listConversations()`. Operators can filter by specific assistant persona or perform instantaneous case-insensitive client title search.
- **New Chat Creation:** Clicking "New Chat" dispatches `api.createConversation()` targeting the selected or default assistant, immediately focusing the active canvas.
- **Inline Rename:** Hovering over any conversation reveals the `Edit2` trigger, turning the title into an inline input with Enter-to-save and Escape-to-cancel. Dispatches `api.updateConversation(convId, { title })`.
- **Safe Deletion:** Deletion requires explicit confirmation via `ConfirmModal` before calling `api.deleteConversation(convId)`.

### 3.2 Real-Time SSE Streaming & Cancellation
- **Streaming Pipeline:** Dispatches `POST /api/v1/conversations/{id}/messages/stream` with JWT Bearer auth and `X-Tenant-ID`.
- **Incremental Token Delivery:** Listens for `event: token` and appends tokens seamlessly with typing cursor animation.
- **Client Cancellation:** An `AbortController` is attached to every outgoing stream. Clicking the red **"Stop"** button aborts the stream immediately, preserving accumulated tokens without generating orphan database states.
- **Error Visibility:** SSE errors (`event: message_error`) or network disconnects render in a dismissible warning banner with retry instructions.

### 3.3 Knowledge Citations & Provenance Inspection
- **Interactive In-Text Tokens:** Citations like `[1]` in generated markdown are parsed into clickable blue tokens.
- **Sources Tray:** Assistant messages display a clean source chips tray showing file icons, document titles, and page numbers.
- **Citation Modal:** Clicking any source badge opens the `Modal` inspector showing the full verified excerpt, source document name, and exact page number. No synthetic or invented coordinates are shown.

---

## 4. Invariant & Security Verification

1. **Multi-Tenant Scoping:** All conversation queries strictly enforce `tenant_id == ctx.tenant.id` and `user_id == current_user.id`.
2. **BYOK Key Protection:** The runtime verifies tenant BYOK keys before calling commercial LLM providers.
3. **No Paid API Calls in Tests:** Offline execution uses the deterministic `mock` provider and local RAG fusion.
4. **Fail-Closed ACLs:** Chat conversations cannot query knowledge bases outside their tenant or unauthorized departments.
