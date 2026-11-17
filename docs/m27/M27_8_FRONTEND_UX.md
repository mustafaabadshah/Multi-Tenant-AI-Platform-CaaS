# M27.8 — Chat Interface, Citations & User Experience

## 1. Natural URL Detection in Chat

Users do not need a separate web application. Pasting a URL directly into the existing chat composer or speaking it via microphone seamlessly engages the assistant:
- Example: *"Read https://www.w3schools.com/cpp/cpp_for_loop.asp and explain how for loops work."*

---

## 2. Real-Time SSE Feedback

During live streaming:
1. When the assistant invokes `web_read_url`, the interface receives:
   - `event: tool_call_started` (`{"tool_name": "web_read_url"}`)
   - `event: web_source_discovered` (`{"url": "...", "title": "...", "domain": "..."}`)
2. Discovered web sources appear in the live streaming header pill.
3. In-line text renders distinct numeric citation badges (`[1]`, `[2]`).

---

## 3. Web Citations & Source Cards

In [MarkdownRenderer.tsx](file:///E:/MM%20Office/Multi-Tanant-CaaS/frontend/components/chat/MarkdownRenderer.tsx) and [page.tsx](file:///E:/MM%20Office/Multi-Tanant-CaaS/frontend/app/dashboard/conversations/page.tsx):
- **Visual Distinction:** Web citation chips render with an emerald/green tint and a `<Globe />` icon, clearly distinguishing public web sources from internal confidential PDF/DOCX documents (`<FileText />`).
- **No Fake Page Numbers:** Unlike document citations (`p. 3`), web citations display domain names (`w3schools.com`) rather than fabricated page numbers.
- **Interactive Source Tray:** Clicking any citation opens the **Citation Inspection Modal**:
  - Displays the exact extracted excerpt.
  - Shows the canonical website URL with a clickable external link.
  - Provides an **Open Source** action button (`window.open(url, "_blank")`).
  - Provides a **Save to KB** action button.

---

## 4. Save Web Source to Knowledge Base Modal

Clicking **Save to KB** opens a dedicated modal:
1. **Destination Knowledge Base:** Dropdown of active Knowledge Bases in the workspace.
2. **Title:** Pre-filled with the web page title (editable).
3. **Storage Mode Toggle:**
   - **Bookmark Reference:** Lightweight metadata bookmark (default).
   - **Full Content:** Indexes extracted text into searchable chunks for Hybrid RAG.
4. **Notes / Summary:** Optional textarea for user-authored commentary.
5. **Direct API Save:** Dispatches to `/tools/builtin_web_save_to_kb/execute` with instantaneous feedback.

---

## 5. Voice & Speech Integration

Preserves all M26.8 speech fixes:
- Users can speak: *"Read this webpage and explain the syntax."*
- Browser STT populates the composer or executes directly in `VOICE_CONVERSATION` mode.
- Browser TTS reads the generated answer aloud while automatically skipping raw URLs and citation brackets via `cleanTextForSpeech`.
