# M28.13 Security & Regression Verification

**Milestone:** M28.13 — Critical Knowledge Base Data Integrity, Assistant-KB Routing, Refresh Loop, Back Navigation & End-to-End Reliability  
**Date:** November 19, 2026  
**Status:** ALL TESTS PASSING  

---

## 1. Multi-Tenant Security Guarantees Tested

The backend test suite `backend/tests/test_m28_13_knowledge_integrity_and_routing.py` verifies all mandatory security and multi-tenant isolation gates:

1. **Explicit Destination Selection (`test_promotion_valid_explicit_destination`):**
   - Verified that a user promoting an attachment to an explicit KB succeeds with HTTP 200, returns the correct document ID, and marks `is_promoted=True`.
2. **Duplicate Promotion Blocked (`test_repeated_promotion_is_rejected`):**
   - Verified that attempting to promote the same attachment twice returns HTTP 400 Bad Request, preserving data integrity and preventing duplicate document inflation.
3. **Cross-KB Re-promotion Blocked (`test_promotion_cross_kb_repromotion_blocked`):**
   - Verified that attempting to promote an already-promoted attachment to a different KB returns HTTP 400 Bad Request.
4. **Cross-Tenant KB Promotion Blocked (`test_promotion_cross_tenant_kb_rejected`):**
   - Verified that a user attempting to promote an attachment to a KB belonging to a different tenant is rejected with HTTP 404 (strictly isolating tenant resources).
5. **Conflicting Destination Fields Rejected (`test_promotion_mismatched_duplicate_target_fields_rejected`):**
   - Verified that supplying different IDs in `knowledge_base_id` and `target_knowledge_base_id` returns HTTP 400 Bad Request.
6. **Nonexistent KB Rejected (`test_promotion_nonexistent_kb_rejected`):**
   - Verified that passing a non-existent UUID returns HTTP 404 Not Found.
7. **Archived KB Rejected (`test_promotion_archived_kb_rejected`):**
   - Verified that passing an archived KB returns HTTP 400 Bad Request.
8. **Unauthorized User Blocked (`test_promotion_unauthorized_user_rejected`):**
   - Verified that an unauthenticated request returns HTTP 401 Unauthorized.

**Result: 8/8 tests PASSED in 11.98s.**

---

## 2. Frontend Test Suite

Frontend test suite in `frontend/lib/__tests__/knowledge-navigation-and-promotion.test.ts` covers:
- Destination policy Case A (single connected KB preselected)
- Destination policy Case B (multiple connected KBs force empty placeholder)
- Destination policy Case C (0 connected KBs force empty placeholder)
- Dropdown separation into Connected vs. Other KBs
- URL query parameter sync for `?kbId=`
- Browser Back URL restoration
- Deep linking preserving active KB
- Polling scheduling when documents are pending (`PROCESSING`)
- Polling suppression when documents are terminal (`READY`)

**Result: 9/9 new tests PASSED; 43/43 total frontend tests PASSED.**

---

## 3. Regression Suite Status

- **M28.12 Capabilities Preserved:**
  - Groq tool calling repairs intact.
  - Deterministic research search intact.
  - arXiv integration intact.
  - Markdown code block rendering intact.
- **Frontend Typecheck & Lint:**
  - `npx tsc --noEmit`: 0 errors.
  - `npm run build`: All 24 routes built cleanly with zero compilation errors.
