# M28.8 Settings & Advanced Disclosure — Multi-Tenant AI Platform (CaaS)

**Milestone:** M28.8  
**Date:** November 19, 2026  
**Focus:** Scoped Configuration and Collapsible Advanced Features

---

## 1. Scoped Settings Hierarchy

Settings are strictly delineated by scope to prevent conflicts:

| Scope | Location | Responsibility | Target Persona |
|---|---|---|---|
| **Workspace Settings** | `/dashboard/settings` | Tenant name, member quotas, storage quotas, default workspace policies | Workspace Owner / Admin |
| **Team & Roles** | `/dashboard/employees` | Role assignment (`OWNER`, `ADMIN`, `MEMBER`, `VIEWER`), invitations | Workspace Admin |
| **Assistant Settings** | `/dashboard/assistants` | System prompt, connected KBs, model temperature, top-k, tool policy | Assistant Creator / Admin |
| **Developer Settings** | `/dashboard/providers`, `/dashboard/integrations` | BYOK API keys, MCP servers, tool definitions | Technical Builder / Admin |

---

## 2. Progressive Disclosure in Advanced Navigation

The sidebar navigation (`frontend/app/dashboard/layout.tsx`) organizes deep technical modules into a collapsible **Advanced** section:

```
[Advanced Section (Collapsible)]
├── Tools & MCP (/dashboard/integrations)
├── Evaluations (/dashboard/evaluations)
├── Beta Quality (/dashboard/beta)
├── Observability (/dashboard/observability)
├── Providers & Keys (/dashboard/providers)
└── Audit Logs (/dashboard/audit)
```

### Behavior
- Everyday users see a clean, compact sidebar without distraction.
- Clicking "Advanced" smoothly expands the items with subtle micro-transitions.
- Visiting an advanced URL directly automatically expands the section.
