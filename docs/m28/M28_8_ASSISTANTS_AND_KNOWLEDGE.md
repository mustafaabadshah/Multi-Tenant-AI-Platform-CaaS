# M28.8 Assistants & Knowledge — Hybrid Architecture & Progressive Settings

**Milestone:** M28.8  
**Date:** November 19, 2026  
**Routes:** `/dashboard/assistants`, `/dashboard/knowledge`

---

## 1. Assistants Management (`/dashboard/assistants`)

### 1.1 Elimination of Duplicate Chat Drawer
In previous milestones, `/dashboard/assistants` contained an embedded chat drawer that duplicated SSE streaming, citations, and message rendering from `/dashboard/conversations`.
In M28.8, this duplicate implementation was completely eliminated:
- `/dashboard/assistants` is dedicated to assistant configuration, instruction tuning, versioning, and publishing.
- Every assistant item provides a primary **"Chat"** button that routes directly to `/dashboard/conversations?assistantId=${assistant.id}`.

### 1.2 Responsive Hybrid Design
- **Desktop (≥ 1024px):**
  - Left Pane (4 cols): Searchable assistant list with compact cards (Name, Provider, Description, Connected KBs).
  - Right Pane (8 cols): `AssistantWorkspaceView` for the selected assistant.
- **Mobile (< 1024px):**
  - Full-width assistant cards. Clicking an assistant switches to the full-width workspace view with a prominent "Back to all assistants" button.

### 1.3 Simplified 1-Screen Creation Wizard
The previous 5-step wizard in `AssistantCreationWizard.tsx` was replaced with a focused 1-screen modal:
- **Required:** Name and Purpose / Description.
- **Optional:** Knowledge Base selection and Template blueprints.
- **Progressive Disclosure:** "Customize Instructions & Model" toggle expands system prompt, model choice (`auto`, `gpt-4o-mini`, `claude-3-5-sonnet`), and retrieval mode.
- **Immediate Outcome:** Success screen offering **"Start Chatting Now"** or **"Configure Details"**.

---

## 2. Knowledge Library (`/dashboard/knowledge`)

### 2.1 Information Architecture
Knowledge Bases represent the permanent, shared grounding layer for assistants:
- **Card/Grid Overview:** Displays KB name, document count, and status (`READY`).
- **Detail View:**
  - Documents tab with source format icons (PDF, Word, Excel, SQL, HTML).
  - Retrieval & Vectors configuration.
  - Search Sandbox.
  - Index Status.

### 2.2 Ingestion & Recovery
- Unified support for drag-and-drop document upload and public webpage URL ingestion.
- **Safety Guarantee:** Preserves existing recovery flow for legacy failures (such as `C___For_Loop.html`) without executing automatic or unapproved database mutations.

### 2.3 Ephemeral Chat Context vs. Permanent Knowledge Base
The platform clearly distinguishes temporary vs. permanent knowledge:
- **Ephemeral (Chat):** Reading a public web URL or attaching a file in chat provides instant turn context without polluting database storage.
- **Permanent (KB):** Ingesting a source into a Knowledge Base chunks the text and computes vector embeddings for all assistants in the workspace.
