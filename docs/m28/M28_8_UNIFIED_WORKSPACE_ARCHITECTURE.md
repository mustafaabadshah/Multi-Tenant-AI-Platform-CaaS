# M28.8 Unified Workspace Architecture — Multi-Tenant AI Platform (CaaS)

**Milestone:** M28.8  
**Date:** November 19, 2026  
**Architecture Standard:** Unify Workflows, Not Database Models

---

## 1. Prime Architectural Directive

The central architectural thesis of M28.8 is:
> **"Unify workflows, not database models."**

Chat, Assistants, Knowledge, and Overview are designed to feel like an interconnected, coherent workspace while preserving canonical backend database entities:
- `Assistant`
- `Conversation`
- `Message`
- `KnowledgeBase`
- `Document`
- `DocumentVersion`
- `Tool`
- `Approval`

No entities were merged, flattened, or compromised to simplify navigation.

---

## 2. Information Architecture (IA) Model

The application shell organizes all routes into three logical tiers:

```
[Workspace Shell: LayoutDashboard]
├── 1. Core Workspace Destinations (Primary Daily Work)
│   ├── Overview (/dashboard) — Task-oriented home & quick prompt launcher
│   ├── Chat (/dashboard/conversations) — Primary conversation canvas & web intelligence
│   ├── Assistants (/dashboard/assistants) — Hybrid list & contextual studio configuration
│   └── Knowledge (/dashboard/knowledge) — Reusable document library & search sandbox
│
├── 2. Management (Team & Operational Governance)
│   ├── Team (/dashboard/employees) — Member roles & tenant boundaries
│   └── Settings (/dashboard/settings) — Workspace identity, usage & quotas
│
└── 3. Advanced (Collapsible Engineering & Analytics Suite)
    ├── Tools & MCP (/dashboard/integrations)
    ├── Evaluations (/dashboard/evaluations)
    ├── Beta Quality (/dashboard/beta)
    ├── Observability (/dashboard/observability)
    ├── Providers & Keys (/dashboard/providers)
    └── Audit Logs (/dashboard/audit)
```

### Collapsible Progressive Disclosure
- For everyday users, the sidebar presents only the 4 core destinations and 2 management items.
- The **Advanced** section is collapsible with an intuitive chevron toggle.
- When an administrator navigates to any advanced route, the section automatically expands to maintain contextual awareness.

---

## 3. Cross-Page Workflow Integrations

### 3.1 Overview ↔ Chat Handoff
- **Source:** `/dashboard`
- **Mechanism:** Direct URL search query parameters:
  `router.push('/dashboard/conversations?assistantId=${selectedAssistantId}&draft=${encodeURIComponent(draft)}')`
- **Destination:** `/dashboard/conversations`
- **Behavior:** `ConversationsContent` reads `assistantId` and `draft` on mount:
  - If a conversation already exists for that assistant, it activates it.
  - If no conversation exists, it creates one cleanly (`Chat with ${assistant.name}`).
  - The textarea is immediately prefilled with the draft prompt.

### 3.2 Assistants ↔ Chat Handoff
- **Source:** `/dashboard/assistants`
- **Mechanism:** Every assistant row and card features a prominent **Chat** button:
  `router.push('/dashboard/conversations?assistantId=' + assistant.id)`
- **Behavior:** Opens Chat directly with that assistant without creating duplicate chat drawers inside the Assistants route.

### 3.3 Knowledge ↔ Assistants Integration
- Inside `/dashboard/knowledge`, KBs show connected assistant counts and vice versa.
- Inside `/dashboard/conversations`, users can inspect citations from KBs and bookmark web sources directly into KBs.

---

## 4. State Management & Lifecycle

- **Speech Session Lifecycle:** Speech synthesizers, recognition listeners, and SSE connections are cleanly ended on conversation switch or component unmount to prevent audio leaks or background polling.
- **Suspense Boundary:** `ConversationsWorkspacePage` and `AssistantsChatPage` wrap their content in `<React.Suspense>` to ensure 100% compliance with Next.js 16 static rendering and client query parameter hydration.
