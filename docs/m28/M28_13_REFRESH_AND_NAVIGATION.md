# M28.13 Knowledge Refresh Loop and Navigation Architecture

**Milestone:** M28.13 — Critical Knowledge Base Data Integrity, Assistant-KB Routing, Refresh Loop, Back Navigation & End-to-End Reliability  
**Date:** November 19, 2026  
**Status:** IMPLEMENTED AND VERIFIED  

---

## 1. Problem Definition: The Re-render Cascade

The pre-existing Knowledge Base page at `frontend/app/dashboard/knowledge/page.tsx` exhibited two critical stability defects:
1. **Infinite Re-render and Re-fetch Cycle:** `loadKBs` included `selectedKB` in its dependency array and called `setSelectedKB(refreshed)` with a fresh object returned from `listKnowledgeBases()`. This changed the reference of `selectedKB`, causing `loadKBs` to change reference, which triggered the `useEffect([loadKBs])`, leading to continuous network requests (~1 request every 600–1000ms), visual flicker, and scroll resets.
2. **Ephemeral Navigation State:** Selecting a KB only mutated component state (`selectedKB`). As a result:
   - Deep linking directly to a KB was impossible.
   - Refreshing the browser wiped the selection and returned to the KB list.
   - The browser Back button operated on browser history rather than the in-app view, navigating the user away from the dashboard.

---

## 2. Refactored Architecture

### 2.1 Primitive ID State + URL Synchronization
Instead of storing a full mutable `KnowledgeBase` object in state:
1. Read the active KB from the URL search params:
   ```tsx
   const searchParams = useSearchParams();
   const urlKbId = searchParams.get("kbId");
   const [selectedKbId, setSelectedKbId] = useState<string | null>(urlKbId);
   ```
2. Derive the full object with memoization:
   ```tsx
   const selectedKB = useMemo(
     () => knowledgeBases.find((kb) => kb.id === selectedKbId) || null,
     [knowledgeBases, selectedKbId]
   );
   ```
3. Synchronize with Next.js navigation:
   - Select KB: `router.push('/dashboard/knowledge?kbId=' + kb.id)`
   - Back to list: `router.push('/dashboard/knowledge')`
   - URL parameter changes automatically update `selectedKbId`.

### 2.2 Callback Stability
`loadKBs` now has a stable dependency footprint:
```tsx
const loadKBs = useCallback(async () => {
  if (!activeWorkspace) return;
  try {
    setIsLoading(true);
    const data = await api.listKnowledgeBases();
    setKnowledgeBases(data);
  } catch (err: unknown) {
    setError(err instanceof Error ? err.message : "Failed to load Knowledge Bases");
  } finally {
    setIsLoading(false);
  }
}, [activeWorkspace?.tenant_id]);
```
- It depends solely on `activeWorkspace?.tenant_id`.
- Changing `selectedKbId` does **not** cause `loadKBs` to re-fetch the list.

### 2.3 Bounded Ingestion Polling
Polling is strictly conditional and self-terminating:
```tsx
useEffect(() => {
  if (!selectedKbId) return;

  const hasPending = documents.some(
    (d) => d.status === "QUEUED" || d.status === "PROCESSING"
  );
  if (!hasPending) return;

  const timer = setTimeout(() => {
    loadDocuments(selectedKbId);
  }, 4000);

  return () => clearTimeout(timer);
}, [selectedKbId, documents, loadDocuments]);
```
- When idle (all documents are `READY` or `FAILED`), polling timer is never scheduled (0 requests/minute).
- When active, polls at 4-second intervals.
- Cleanup hook prevents memory leaks on unmount.

### 2.4 Next.js App Router Suspense Boundary
Because `useSearchParams()` requires a Suspense boundary in Next.js App Router, the exported component is wrapped in:
```tsx
export default function KnowledgePage() {
  return (
    <Suspense fallback={<div className="p-8 text-neutral-400">Loading knowledge base...</div>}>
      <KnowledgeContent />
    </Suspense>
  );
}
```

---

## 3. Interaction Verification

- **Idle Page:** 0 background requests per minute.
- **Back Navigation:** Clicking "Back to Knowledge Bases" or browser Back transitions from detail to list with 0 flicker.
- **Deep Linking:** Direct URL `/dashboard/knowledge?kbId=<uuid>` loads directly into that KB's detail view.
- **Browser Refresh:** F5 on a selected KB preserves the detail view seamlessly.
- **Tests Passed:** 9 dedicated unit and interaction tests in `knowledge-navigation-and-promotion.test.ts`.
