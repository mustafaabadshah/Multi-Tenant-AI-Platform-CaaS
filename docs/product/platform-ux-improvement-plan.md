# Platform UX Improvement Plan — Linear × Apple Notes Design Standard

**Goal:** Transform the developer-oriented engineering modules into a fluid, cohesive, and premium productivity platform.  
**Aesthetic Philosophy:** Restrained monochrome, subtle borders, high contrast, purposeful whitespace, and zero decorative charts or fake SaaS metrics.  

---

## 1. Identified Usability Friction Points & Remediation

| # | Current Friction Point | Identified Root Cause | Concrete Remediation Plan for M08 |
|---|---|---|---|
| **1** | Disconnected Setup Journey | User creates an assistant, but must separately discover that they need to visit "Providers" to configure keys and "Knowledge" to upload files. | **Assistant Readiness Checklist:** On the Assistant Overview tab, display a live 4-step checklist: 1. Identity, 2. Attached Knowledge, 3. Provider/BYOK Key, 4. Preview Test. Each item contains a 1-click action button. |
| **2** | Overwhelming Technical Terminology | Advanced RAG parameters (RRF Constant, top-K, BM25 vs dense) presented without guidance. | **Progressive Disclosure:** Keep Simple mode as the prominent default (Audience, Response Tone, Uncertainty, Citation preference). Place RAG vector store parameters inside an explicitly collapsible "Advanced Retrieval & Context Budget" section. |
| **3** | Hidden Document Chunks | Users upload PDFs but cannot see why a specific paragraph was or was not retrieved. | **Chunk Inspector Drawer:** In Knowledge Studio, clicking any document opens a side drawer showing all indexed chunks, page numbers, heading paths, and token counts. |
| **4** | Publishing Ambiguity | Creators fear that creating an assistant makes it immediately public to the world. | **Explicit Visibility Stepper:** In the Assistant Publish tab, provide three clear radio options with descriptive security badges: Private (Only creator/admins), Workspace (All authenticated employees), Public (External web link & embed). |
| **5** | Fragile Web Embeds | Embedding a widget on third-party sites often suffers from CSS style bleeding or complex initialization. | **Zero-Dependency Iframe Widget:** Package the embed as an isolated iframe widget loader with strict postMessage communication, preventing host website CSS from breaking the assistant bubble. |

---

## 2. Linear × Apple Notes Design System Tokens

- **Palette:**
  - Background: Neutral light `#f8fafc` / Pure white `#ffffff`
  - Dark Mode Background: Neutral `#09090b` / Elevated `#18181b`
  - Primary Accent: Light Sky Blue `#0284c7` (Tailwind `sky-600`)
  - Border Lines: `#e2e8f0` (Light) / `#27272a` (Dark)
  - Text: Deep Slate `#0f172a` (Primary) / Muted Slate `#64748b` (Secondary)
- **Typography:**
  - Clean sans-serif hierarchy: Inter / system fonts
  - Mono: `font-mono` for API keys, chunk indices, and JSON snippets
- **Interactive Micro-Interactions:**
  - Subtle hover lift on assistant cards (`transition-all duration-150`)
  - Status pills with soft semantic tints (Emerald for Active/Published, Amber for Draft, Rose for Revoked)
  - Copy-to-clipboard buttons with immediate "Copied!" checkmark feedback
