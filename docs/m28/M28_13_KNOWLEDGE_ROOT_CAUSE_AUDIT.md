# M28.13 Knowledge Root Cause Audit

**Milestone:** M28.13 — Critical Knowledge Base Data Integrity, Assistant-KB Routing, Refresh Loop, Back Navigation & End-to-End Reliability  
**Date:** November 19, 2026  
**Status:** COMPLETE (Local Fixes Verified)  

---

## 1. Executive Summary

This audit establishes the definitive root causes for the critical operator-reported defects in Knowledge Base routing, re-render/refresh instability, and navigation:

1. **Defect A — Silent Wrong Knowledge Base Destination Routing:** Operator chatting with "Notes & Textbook Q&A Assistant" (connected strictly to "PF" KB) uploaded a solar irradiance PDF. Saving/promoting placed the file into "Cricket" KB.
2. **Defect B — Knowledge Base Continuous Refresh/Flicker Loop:** The `/dashboard/knowledge` page re-rendered and re-fetched every 1–2 seconds continuously when idle.
3. **Defect C — Knowledge Base Back Navigation Broken:** Back button inside a selected KB was pure component state (`setSelectedKB(null)`). Browser Back exited the app or behaved inconsistently. Refreshing the browser wiped the active view back to the list.
4. **Defect D — Cross-Field Payload and Duplicate State Inconsistencies:** The API accepted both `knowledge_base_id` and `target_knowledge_base_id` without verifying they matched, allowing potential conflicting target injections.

---

## 2. Root Cause Analysis — Defect A (Wrong KB Destination)

### Symptom
- Assistant: "Notes & Textbook Q&A Assistant"
- Intended KB: "PF"
- Actual Destination: "Cricket"
- File: `Solar_irradiance__TechScience.pdf`

### Mechanism
In `frontend/app/dashboard/conversations/page.tsx`:
```tsx
// PRE-FIX:
const [targetKbId, setTargetKbId] = useState<string>("");
...
useEffect(() => {
  if (knowledgeBases.length > 0 && !targetKbId) {
    setTargetKbId(knowledgeBases[0].id); // <-- BUG: Arbitrary first element fallback!
  }
}, [knowledgeBases, targetKbId]);
```
- When the workspace KBs loaded, the list was returned alphabetically or by insertion order (`[Cricket, PF, ...]`).
- Because `targetKbId` defaulted to `""`, the `useEffect` immediately assigned `knowledgeBases[0].id` ("Cricket") regardless of which assistant was active or what KBs that assistant was linked to.
- The same defect existed in `saveWebCitation`:
```tsx
// PRE-FIX:
useEffect(() => {
  if (knowledgeBases.length > 0 && !saveWebKbId) {
    setSaveWebKbId(knowledgeBases[0].id); // <-- Same arbitrary fallback
  }
}, [knowledgeBases, saveWebKbId]);
```
- The backend endpoint `/api/v1/conversations/{id}/attachments/{att_id}/promote` accepted `target_knowledge_base_id` as supplied by the client. It verified tenant ownership of the target KB, but because Cricket was also owned by the same tenant, the backend accepted it as a valid promotion.

### Resolution
1. **Deterministic Destination Policy:**
   - Detect `activeAssistant.connected_kb_ids`.
   - **Case A (Exactly 1 connected KB):** Pre-select that specific KB by default.
   - **Case B (Multiple connected KBs):** Require explicit user selection (placeholder `""` requiring explicit choice).
   - **Case C (0 connected KBs):** Show clear notice: *"This assistant doesn't have a connected Knowledge Base."*
   - **Case D (User deliberately chooses another KB):** Clearly separate the dropdown into `<optgroup label="Connected to [Assistant]">` and `<optgroup label="Other Workspace Knowledge Bases">`. Show an amber warning if the chosen destination is not connected to the active assistant.
2. **Backend Payload Validation:**
   - Enforce that if both `knowledge_base_id` and `target_knowledge_base_id` are provided in the payload, they must match exactly or return HTTP 400.

---

## 3. Root Cause Analysis — Defect B (Refresh Loop & Polling Cascade)

### Symptom
The Knowledge page at `/dashboard/knowledge` flickered and re-fetched every second, resetting document scroll and causing continuous spinner flashes.

### Mechanism
In `frontend/app/dashboard/knowledge/page.tsx`:
```tsx
// PRE-FIX:
const loadKBs = useCallback(async () => {
  try {
    const data = await api.listKnowledgeBases();
    setKnowledgeBases(data);
    if (selectedKB) {
      const refreshed = data.find(k => k.id === selectedKB.id);
      if (refreshed) setSelectedKB(refreshed); // <-- Creates a brand new object reference!
    }
  } catch (err) { ... }
}, [activeWorkspace, selectedKB]); // <-- selectedKB is in dependencies!

useEffect(() => {
  loadKBs();
}, [activeWorkspace, loadKBs]); // <-- loadKBs reference changes whenever selectedKB changes!
```
1. `selectedKB` is initialized or updated.
2. `setSelectedKB(refreshed)` passes a new object reference.
3. Because `selectedKB` changed, `useCallback(..., [activeWorkspace, selectedKB])` creates a new function reference for `loadKBs`.
4. `useEffect(..., [activeWorkspace, loadKBs])` detects that `loadKBs` changed and executes `loadKBs()`.
5. `loadKBs()` fetches data, finds `refreshed`, calls `setSelectedKB(refreshed)` again.
6. The cycle repeats indefinitely every network roundtrip (~500ms to 1s).
7. Additionally, document polling had an uncontrolled interval that fired even when all documents were `READY`, compounding the network flood.

### Resolution
1. **State Normalization:**
   - Replace mutable object state `selectedKB: KnowledgeBase | null` with primitive `selectedKbId: string | null`.
   - Derive `selectedKB` declaratively using `useMemo`:
     ```tsx
     const selectedKB = useMemo(
       () => knowledgeBases.find((kb) => kb.id === selectedKbId) || null,
       [knowledgeBases, selectedKbId]
     );
     ```
2. **Stable Data Fetching:**
   - `loadKBs` depends only on `activeWorkspace?.tenant_id`. It updates `knowledgeBases` without touching `selectedKbId`.
3. **Bounded Conditional Polling:**
   - Polling only runs if `documents.some(d => d.status === "QUEUED" || d.status === "PROCESSING")`.
   - Idle requests per minute: **0**.
   - Timer is cleanly cleared on component unmount and when documents transition to terminal states (`READY` / `FAILED`).

---

## 4. Root Cause Analysis — Defect C (Back Navigation Failure)

### Symptom
Clicking Back in the KB detail view did not update the URL. Browser Back navigated away from the Knowledge section entirely. Refreshing the browser wiped the user's view back to the KB list.

### Mechanism
- KB selection was stored solely in ephemeral React state (`useState<KnowledgeBase | null>(null)`).
- The route was always `/dashboard/knowledge` regardless of whether a KB was open or which document was being inspected.
- The UI "Back" button simply called `setSelectedKB(null)`, leaving browser history out of sync.

### Resolution
- Adopted Next.js URL query parameter synchronization (`/dashboard/knowledge?kbId=<uuid>`).
- Opening a KB executes `router.push('/dashboard/knowledge?kbId=' + kb.id)`.
- Clicking "Back" executes `router.push('/dashboard/knowledge')`.
- Browser Back and Forward buttons seamlessly navigate between KB list and KB detail.
- Direct linking and page refresh preserve the exact active Knowledge Base.
- Component is wrapped in `React.Suspense` to satisfy Next.js App Router requirements for `useSearchParams()`.
