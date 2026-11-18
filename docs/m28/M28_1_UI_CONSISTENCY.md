# M28.1 — UI Consistency & Design System Alignment

## 1. Aesthetic Standard: Linear × Apple Notes × ChatGPT
- **Theme:** Clean, modern SaaS aesthetic with neutral gray backgrounds (`bg-gray-50`), crisp white card containers (`bg-white border border-gray-200`), and subtle borders.
- **Accents:** Restrained blue accent (`text-blue-600`, `bg-blue-50`), emerald for grounded citations and success telemetry (`text-emerald-600`), and amber for warnings/approvals (`text-amber-600`).
- **Typography:** Modern variable font with clear hierarchy (H1 24px semi-bold, body 14px regular, captions 12px/11px font-medium).
- **Controls & Buttons:** Reusable `Button` components with unified variants (`primary`, `secondary`, `outline`, `danger`), consistent padding, and focus rings.

## 2. Conversation Studio Refinements
- **Composer Toolbar:** Unified attachment icon, microphone toggle, and send button cleanly positioned inside the textarea container.
- **Microphone States:** Clear feedback for Dictation (active animated ring), Voice Chat (continuous turn loop pill), Auto-Read, and Mute.
- **In-App Feedback:** Low-profile thumbs up/down icons nestled cleanly below assistant bubbles; negative feedback expands a compact popover with category chips and optional comment field.
- **Attachment Chips:** Horizontal scrollable drawer above composer showing filename, file size in KB, status badge, and one-click "Save to KB" promotion.
