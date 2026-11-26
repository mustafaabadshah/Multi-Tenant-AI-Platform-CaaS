# M26.6 — Private Beta Readiness & Controlled Onboarding Plan

## 1. Executive Summary
Phase M26.6 establishes the operational readiness framework, manual acceptance checklist, and controlled 5-user onboarding protocol for the Private Beta release of the Multi-Tenant AI Platform (CaaS).

---

## 2. Operator Manual Acceptance Handoff Checklist
The operator will manually evaluate the staging environment (`https://mmaip-frontend.onrender.com`) using the following protocol:

- [ ] **1. Authentication & Workspace Selection:** Log in as test operator; confirm workspace selector loads active organization.
- [ ] **2. Assistant Selection:** Select or create an assistant in the Conversation Studio.
- [ ] **3. Multi-Page PDF Attachment:** Upload a 3-page synthetic PDF; verify attachment card appears in `READY` status with page count 3.
- [ ] **4. DOCX Attachment:** Upload a structured DOCX; verify chunk count.
- [ ] **5. Document-Grounded Chat & Citations:** Ask a question regarding Page 2 facts; verify assistant answers correctly and renders a clickable citation marker `[1]` with document title and page number.
- [ ] **6. Follow-Up Questions:** Submit follow-up question; verify context is maintained without re-uploading.
- [ ] **7. Knowledge Base Promotion:** Click "Promote to KB" on the attachment; verify status badge updates to `PROMOTED` and document appears in target Knowledge Base.
- [ ] **8. Attachment Deletion Durability:** Delete the chat attachment; verify the promoted Knowledge Base document remains fully accessible.
- [ ] **9. Speech Dictation (STT):** Select Dictation mode; speak into microphone; verify speech renders into the message input field.
- [ ] **10. Speech Listen (TTS):** Select Listen mode; send message; verify assistant response is read aloud cleanly without markdown syntax or citations.
- [ ] **11. Voice Conversation Mode:** Speak a turn; verify microphone stops while assistant answers, then resumes automatically when speaking ends.
- [ ] **12. Tool Approval Interruption:** Trigger an action requiring approval; verify voice loop pauses and modal displays tool parameters for explicit UI approval.
- [ ] **13. Mobile Responsiveness:** Verify navigation and attachment drawer render smoothly on mobile viewport widths.

---

## 3. Controlled Beta Cohort (5 Users)
- **Cohort Size:** Strictly 5 invited external users.
- **Invitation Method:** Direct workspace invitation via platform email/token. Self-service open registration remains restricted (`REGISTRATION_OPEN=False`).
- **Assigned Role:** `employee` (or `viewer`). No invited beta tester receives `tenant_owner` or `platform_superadmin` privileges.
- **Allowed Capabilities:**
  - Chat with pre-configured assistants.
  - Document attachment upload (PDF, DOCX, TXT, CSV up to 10 MB).
  - Browser STT / TTS in supported browsers.
- **Restricted Capabilities:**
  - Remote MCP external connections remain disabled (`ALLOW_PUBLIC_MCP=False`).
  - Mutating database tools remain behind mandatory manual approval gates.
  - Model provider BYOK keys are managed by workspace admins.

---

## 4. Operational Boundaries & Disclosures for Beta Testers
1. **Free-Tier Cold Starts:** Render Free instances spin down after 15 minutes of inactivity. Initial page or API requests may take 25–45 seconds to wake up.
2. **Browser Voice Compatibility:** Web Speech API is supported natively in Chrome, Edge, and Safari. Firefox users receive automatic fallback to standard text input.
3. **Data Retention Policy:** Chat attachments and conversation transcripts are scoped strictly to the tenant and can be deleted at any time by the user. Promoted documents persist in the workspace Knowledge Base until explicitly removed.
4. **Feedback Mechanism:** In-app feedback button or direct issue reporting channel provided to testers.
