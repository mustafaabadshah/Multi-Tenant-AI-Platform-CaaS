# M28.13 Assistant-KB Routing Specification

**Milestone:** M28.13 — Critical Knowledge Base Data Integrity, Assistant-KB Routing, Refresh Loop, Back Navigation & End-to-End Reliability  
**Date:** November 19, 2026  
**Status:** IMPLEMENTED AND TESTED  

---

## 1. Principles of Deterministic Destination Routing

Knowledge Base document placement must never depend on array position, network latency, or alphabetical sorting. Document placement must follow strict, predictable business rules based on the active assistant's authorized relationships.

### Rules Matrix
| Scenario | Condition | System Behavior |
|---|---|---|
| **Case A** | Exactly 1 connected KB | Automatically pre-select the connected KB. Display its human-readable name with a green "Connected" badge. Confirm before saving. |
| **Case B** | Multiple connected KBs | Default to empty (`""`). Display placeholder *"Select Knowledge Base..."*. Do not enable Save button until an explicit selection is made. |
| **Case C** | 0 connected KBs | Default to empty (`""`). Display notice: *"This assistant doesn't have a connected Knowledge Base."* Offer direct link to Assistant settings if authorized. |
| **Case D** | User deliberately selects another KB | Permit if user has write permissions in that workspace KB. Show amber warning: *"Not connected to active assistant — assistant won't retrieve this document until connected."* |
| **Case E** | Cross-tenant / unauthorized target | Backend rejects with HTTP 404/403. UI filters out KBs from other tenants. |
| **Case F** | Stale association | When assistant or workspace changes, reset destination selection immediately. |

---

## 2. Frontend Implementation

In `frontend/app/dashboard/conversations/page.tsx`:

```tsx
// 1. Compute canonical relationships
const activeAssistantConnectedKbIds = useMemo(() => {
  if (!activeAssistant) return new Set<string>();
  const ids: string[] = [];
  if (activeAssistant.connected_kb_ids && Array.isArray(activeAssistant.connected_kb_ids)) {
    ids.push(...activeAssistant.connected_kb_ids);
  }
  if (activeAssistant.knowledge_bases && Array.isArray(activeAssistant.knowledge_bases)) {
    ids.push(...activeAssistant.knowledge_bases.map(kb => kb.id));
  }
  return new Set(ids);
}, [activeAssistant]);

const connectedKBs = useMemo(() => {
  return knowledgeBases.filter(kb => activeAssistantConnectedKbIds.has(kb.id));
}, [knowledgeBases, activeAssistantConnectedKbIds]);

const otherKBs = useMemo(() => {
  return knowledgeBases.filter(kb => !activeAssistantConnectedKbIds.has(kb.id));
}, [knowledgeBases, activeAssistantConnectedKbIds]);

// 2. Deterministic default selection
useEffect(() => {
  if (connectedKBs.length === 1) {
    setTargetKbId(connectedKBs[0].id);
  } else {
    setTargetKbId(""); // Force explicit selection
  }
}, [connectedKBs]);
```

### Visual Feedback
The modal displays:
- Document filename.
- Active assistant name.
- Grouped selector:
  - `<optgroup label="Connected to [Assistant]">`
  - `<optgroup label="Other Workspace Knowledge Bases">`
- Status indicators:
  - Green checkmark + *"Connected to [Assistant]"*
  - Amber alert + *"Warning: Not connected to this assistant"*

The exact same policy is applied to `saveWebCitation` (saving web sources and citations into Knowledge Bases).

---

## 3. Backend Verification

In `backend/app/api/v1/conversations.py`:
```python
# Validation: Ensure consistency if both target fields are present
if req.target_knowledge_base_id and req.knowledge_base_id:
    if req.target_knowledge_base_id != req.knowledge_base_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conflicting target knowledge base IDs specified in request payload."
        )
effective_target_kb_id = req.target_knowledge_base_id or req.knowledge_base_id
```

In `backend/app/services/conversation_attachment_service.py`:
- Target KB existence and tenant ownership verified:
  ```python
  target_kb = await kb_repo.get_by_id(db, target_kb_id, tenant_id=current_user.tenant_id)
  if not target_kb or target_kb.status == "archived":
      raise ValueError("Target Knowledge Base does not exist or is archived")
  ```
- Strict duplicate promotion rejection:
  ```python
  if attachment.is_promoted:
      raise ValueError(f"Attachment is already promoted to Knowledge Base {attachment.promoted_document_id}")
  ```
- Correct destination returned in API response.
