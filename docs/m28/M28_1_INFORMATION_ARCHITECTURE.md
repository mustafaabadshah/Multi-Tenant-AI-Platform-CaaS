# M28.1 — Information Architecture & Navigation Design

## 1. Task-Oriented Navigation Model

To eliminate cognitive overload for first-time nontechnical users while preserving all administrative and engineering capabilities, navigation in `DashboardLayout` is organized into three distinct tiers:

### Tier 1: Main (For All Users)
- **Overview (`/dashboard`):** Workspace health, high-level metrics, and contextual first-time getting-started banners.
- **Chat Studio (`/dashboard/conversations`):** Primary conversation workspace with multi-turn chat, attachment management, web source reading, speech dictation/voice chat, and message feedback.
- **AI Assistants (`/dashboard/assistants`):** Guided assistant creation wizard, persona studio, prompt editor, and template library.
- **Knowledge Bases (`/dashboard/knowledge`):** Central document management, ingestion status, vector collections, and web source promotion.

### Tier 2: Manage (For Workspace Admins)
- **Team & Roles (`/dashboard/employees`):** Role-based access control (Owner, Admin, Member, Viewer), member invitations, department associations, and access boundaries.
- **Usage & Quotas (`/dashboard/settings`):** Storage quotas, token consumption gauges, document count limits, and workspace configurations.

### Tier 3: Advanced (For Developers & Quality Engineers)
- **Tools & MCP (`/dashboard/integrations`):** External tool connections, Model Context Protocol servers, and custom function definitions.
- **Evaluations (`/dashboard/evaluations`):** RAG benchmark datasets, precision/recall runs, ground-truth comparison, and evaluation metrics.
- **Beta Quality (`/dashboard/beta`):** Private beta cohorts, operator feedback review, and participant invite management.
- **Observability (`/dashboard/observability`):** Real-time trace spans, latency percentiles, token telemetry, and execution traces.
- **Providers & Keys (`/dashboard/providers`):** Bring-Your-Own-Key (BYOK) provider credentials and OmniRoute gateway configuration.
- **Audit Logs (`/dashboard/audit`):** Tamper-evident compliance event stream.
