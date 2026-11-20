---
name: caas-product-ux
description: Audits and improves the Multi-Tenant AI Platform Next.js workspace with accessible, minimal, task-oriented UX. Use for dashboard, chat, assistant, knowledge, settings, responsive design, component reuse and frontend interaction reviews.
---

# Multi-Tenant AI Platform (CaaS) Product UX & UI Guidelines

This skill codifies the product design philosophy, interaction patterns, accessibility standards, and component architecture for the Multi-Tenant AI Platform frontend.

## 1. Prime Principles

1. **Unify Workflows, Not Database Models:**
   - Chat, Assistants, Knowledge, and Overview must feel interconnected.
   - Preserve existing backend entities (`Assistant`, `Conversation`, `KnowledgeBase`, `Document`, `Tool`). Do not merge them merely to simplify UI navigation.
   - Enable direct cross-route flows (e.g. Chat from Assistant, Ask questions using Knowledge, Save source to Knowledge Base).

2. **Task-Oriented Home:**
   - The first screen (`/dashboard`) must answer: *"What can I do here?"* and *"How do I start?"*.
   - Always provide one dominant next action (e.g. **Start Chat** or **Create Assistant**).
   - Never clutter Home with large zero-value KPI cards or fabricated activity.

3. **Progressive Disclosure:**
   - Keep default views simple for beginners (Name, Purpose/Instructions, Knowledge Base).
   - Progressively disclose advanced technical settings (LLM temperature, top-k, tool steps, MCP configs, raw chunk IDs) in collapsible panels or dedicated advanced tabs.

4. **Clarity of Ephemeral vs. Permanent:**
   - Make temporary chat context (file attachment, web URL fetch) and permanent knowledge (Knowledge Base vector indexing) clearly distinguishable.
   - Explain what each action does in plain English.

5. **Linear × Apple Notes Design Language:**
   - Neutral light surfaces (`#f9fafb`, `#ffffff`).
   - One restrained accent (Enterprise Blue `#2563eb`).
   - Crisp, soft borders (`#e5e7eb` / `#e2e8f0`) with minimal shadows (`shadow-xs`).
   - Apple-style typography hierarchy with comfortable line heights.
   - No aggressive marketing gradients, oversized decorative banners, or neon badges.

---

## 2. Information Architecture & Navigation

The workspace shell must use a unified 4-destination core with organized management and collapsible advanced areas:

```
[Workspace Shell]
├── Core Destinations
│   ├── Overview (/dashboard)
│   ├── Chat (/dashboard/conversations)
│   ├── Assistants (/dashboard/assistants)
│   └── Knowledge (/dashboard/knowledge)
├── Management
│   ├── Team & Roles (/dashboard/employees)
│   └── Usage & Settings (/dashboard/settings)
└── Advanced (Collapsible)
    ├── Tools & MCP (/dashboard/integrations)
    ├── Evaluations (/dashboard/evaluations)
    ├── Beta Quality (/dashboard/beta)
    ├── Observability (/dashboard/observability)
    ├── Providers & Keys (/dashboard/providers)
    └── Audit Logs (/dashboard/audit)
```

Rules:
- Concise, clear labels in the sidebar navigation.
- No nested duplicate sidebars.
- Workspace switcher always visible and scoped to current tenant.
- Mobile drawer must be full-height, accessible, and responsive (up to 390px).

---

## 3. Route Workflows & Interconnections

### 3.1 Overview ↔ Chat
- For existing users: Quick assistant selector + prompt composer that hands off draft directly to `/dashboard/conversations?assistantId=...&draft=...`.
- For new users: Clear "Create Assistant" primary button.

### 3.2 Assistants ↔ Chat
- Every assistant item provides a primary "Open Chat" action.
- "Open Chat" navigates to `/dashboard/conversations?assistantId={id}` without generating duplicate conversation rows until the first message is sent.

### 3.3 Knowledge ↔ Assistants
- Display associated assistants on Knowledge Base detail view.
- Provide "Ask questions with this Knowledge" action that routes into chat with the connected assistant.

### 3.4 Chat ↔ Knowledge
- Composer must feature:
  - Text input (with keyboard Enter/Shift+Enter support).
  - Attach file (`Paperclip`).
  - Add Webpage (`Globe`) with public URL validation and quick example chips.
  - Microphone (`Mic`) for voice dictation.
  - Send button.
- Citations must display source URL, document name, snippet, and a one-click "Save to Knowledge Base" action.

---

## 4. Assistant Management Hybrid Pattern

- **Desktop:** Clean, searchable list with key attributes (Name, Description, Connected KBs, Status) and an expandable/contextual detail panel.
- **Mobile (< 768px):** Responsive compact cards with full-width drawer/modal for settings.
- **Creation Wizard:**
  - Fast, compact first screen: Name (Required) + Purpose (Required).
  - Optional progressive fields: Knowledge Base selection, Template, Model.
  - Immediate handoff to Chat upon creation.

---

## 5. Accessibility (a11y) & Usability Checklist

Every new or refactored component must verify:
- [ ] Keyboard navigation: All interactive buttons and inputs are reachable via `Tab` and activatable via `Enter`/`Space`.
- [ ] Dialog focus management: Modals trap focus, support `Esc` to close, and restore focus on dismiss.
- [ ] WCAG AA color contrast: Minimum 4.5:1 ratio for text against backgrounds.
- [ ] Screen-reader labels: Non-text icon buttons have explicit `aria-label` or `title` attributes.
- [ ] Plain-English errors: Zero raw exception strings or unhandled error traces in user views.
- [ ] Responsive layouts: No horizontal page overflow at 390px, 768px, 1024px, 1366px.
