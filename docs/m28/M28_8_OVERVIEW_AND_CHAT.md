# M28.8 Overview & Chat Redesign — Multi-Tenant AI Platform (CaaS)

**Milestone:** M28.8  
**Date:** November 19, 2026  
**Primary Focus:** Task-Oriented Overview and Primary Chat Studio

---

## 1. Overview (`/dashboard`) Redesign

The `/dashboard` route now functions as a true task-oriented product home:

### 1.1 First-Time User Experience (Zero Assistants)
When a new user logs in:
- A welcoming card guides them to **Step 1: Create an Assistant**.
- The primary action button opens the simplified 1-screen creation wizard.
- The interface does not display empty zero-value metrics or pretend an assistant is ready.

### 1.2 Established User Experience
When assistants exist in the workspace:
- **Interactive Prompt Composer:**
  - Assistant Selector: Switch between workspace assistants inline.
  - Textarea: Type questions, paste URLs, or outline prompts.
  - Quick Suggestion Chips: `🌐 Read webpage`, `📚 Search knowledge`.
  - **Start Chat Button:** Submits the prompt and navigates directly to `/dashboard/conversations?assistantId=...&draft=...`.
- **Recent Conversations:** Top 4 actual conversations with 1-click resumption links.
- **Configured Assistants:** Compact cards with model provider, KB count, and a direct **Chat** button.
- **Connected Knowledge:** Overview of existing KBs with document counts.
- **Non-Sensitive Release Identity:** Status strip showing `Release M28.8 · Unified AI Workspace · Staging`.

---

## 2. Chat Studio (`/dashboard/conversations`) Refactor

### 2.1 Layout & Visual Canvas
- **Conversation Sidebar:** Collapsible, searchable list of threads filtered by assistant.
- **Message Canvas:** Responsive, readable typography with full Markdown rendering:
  - Code blocks with syntax highlighting and copy button.
  - Formatted tables with horizontal scroll wrappers.
  - Inline verified citations with document and web source indicators.
- **Header:** Shows active assistant name, provider badge, and conversation controls.

### 2.2 Sticky Responsive Composer
Located at the bottom of the canvas with 5 essential actions:
1. **Textarea:** Enter to send, Shift+Enter for new line.
2. **Attach Document (`Paperclip`):** Upload temporary files (PDF, DOCX, TXT, CSV, HTML).
3. **Add Webpage (`Globe`):** Clean modal to paste documentation or tutorial URLs (e.g. W3Schools, Python Docs) with quick chips.
4. **Microphone (`Mic`):** Real-time browser speech dictation.
5. **Send Button:** Primary action with streaming cancellation (`Stop` button).

### 2.3 URL Parameter Hydration
`ConversationsContent` inspects search parameters on mount:
- `assistantId`: Automatically selects the target assistant and opens/creates a conversation.
- `conversationId`: Activates the selected conversation from Overview.
- `draft`: Prefills the composer textarea with the draft message from Overview.
Wrapped in `<React.Suspense>` for Next.js 16 partial prerendering compliance.
