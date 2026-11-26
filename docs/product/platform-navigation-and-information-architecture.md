# Platform Navigation & Information Architecture — Multi-Tenant AI Platform

**Document Purpose:** Define the unified navigation structure, route hierarchy, and information architecture across the platform.  
**UX Direction:** Linear × Apple Notes (content-first, high contrast, clean typography, progressive disclosure).  

---

## 1. Information Architecture Philosophy

The platform avoids a disjointed collection of separate engineering tools. Instead, the **Assistant** is the primary object around which the user experience revolves.

A creator or team member should be able to navigate the platform naturally through two levels of hierarchy:
1. **Global Workspace Level:** High-level overview of resources (Assistants, Knowledge Bases, Model Providers & Keys, Organization Administration, and Usage).
2. **Resource Context Level (Assistant Studio / Knowledge Studio):** Deep, focused workspace dedicated to creating, configuring, testing, publishing, and inspecting a specific entity.

---

## 2. Global Navigation Hierarchy

```
Global Header
├── Workspace Selector (Multi-Tenant Switcher with active tenant indicator)
├── Navigation Links
│   ├── Assistants (/dashboard/assistants) [Core Hub]
│   ├── Knowledge (/dashboard/knowledge) [Document & Ingestion Studio]
│   ├── Providers & Keys (/dashboard/providers) [BYOK Vault & Quota Dashboard]
│   ├── Team & Organization
│   │   ├── Employees (/dashboard/employees)
│   │   ├── Departments (/dashboard/departments)
│   │   └── Groups (/dashboard/groups)
│   ├── Security & Auditing (/dashboard/audit)
│   └── Settings (/dashboard/settings) [Workspace Profile & API Keys]
└── User Profile & Sign Out
```

---

## 3. Assistant Workspace Information Architecture

When an assistant is selected, the interface opens a unified workspace (`/dashboard/assistants` with active drawer or dedicated view):

```
Assistant Workspace
├── Header
│   ├── Assistant Name, Avatar & Status Badge (Draft / Published / Private)
│   ├── Connected Model Indicator (e.g. Groq Llama 3.3 70B)
│   └── Quick Actions: "Test Preview", "Publish", "Delete"
├── Tabs
│   ├── 1. Overview: Metadata, description, readiness checklist, quick stats.
│   ├── 2. Knowledge: Attached Knowledge Bases, public eligibility flag, chunk inspector link.
│   ├── 3. Instructions: System prompt, tone, audience level, uncertainty behavior.
│   ├── 4. Model: Provider selection (Groq, Anthropic, Gemini, OpenAI), temperature, max tokens.
│   ├── 5. Test (Preview Pane): Live interactive chat testing with zero DB persistence.
│   ├── 6. Publish (M08):
│   │   ├── Visibility (Private / Workspace Members / Public Web)
│   │   ├── Public Web Page Link (`/p/{public_id}`)
│   │   ├── Website Embed Widget snippet generator (`<script>` / `<iframe>`)
│   │   ├── Allowed Domains whitelist (`example.com`)
│   │   └── Immediate Unpublish / Revocation switch
│   ├── 7. Versions: Forward-only configuration rollback and version history audit.
│   └── 8. Usage: Per-assistant token consumption and request accounting.
```

---

## 4. Public & Embed Routes (External Facing)

External end-users and integration targets access the platform through lightweight, unauthenticated routes that enforce zero leakage of tenant metadata:

1. **Public Assistant Web Page:**
   - URL: `/p/[publicId]`
   - Clean, standalone chat interface without navigation headers or internal workspace chrome.
   - Mobile-responsive, showing assistant title, greeting, streaming chat, and citation footnotes.
2. **Website Embed Widget Frame:**
   - URL: `/embed/[publicId]`
   - Minimalist iframe payload that mounts cleanly inside host websites without CSS collisions.
   - Respects configured brand accent color and greeting.
3. **Embed Loader Script:**
   - URL: `/embed.js` (or `/api/v1/public/embed.js`)
   - Lightweight standalone script creating an isolated iframe floating bubble on third-party sites.
