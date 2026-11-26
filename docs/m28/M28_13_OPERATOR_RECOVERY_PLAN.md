# M28.13 Operator Recovery Plan for Misrouted Solar Irradiance Document

**Milestone:** M28.13 — Critical Knowledge Base Data Integrity, Assistant-KB Routing, Refresh Loop, Back Navigation & End-to-End Reliability  
**Date:** November 19, 2026  
**Environment:** Neon Staging (`aged-heart-01771250`)  
**Safety Gate:** NO LIVE DATA MUTATIONS EXECUTED WITHOUT EXPLICIT OPERATOR APPROVAL  

---

## 1. Problem Summary & Affected Entities

During testing of the "Notes & Textbook Q&A Assistant", the operator uploaded a solar irradiance paper in Chat Studio and saved it to Knowledge. Due to the frontend index-0 default selection defect, the document was placed into "cricket" instead of the intended "pf" Knowledge Base.

### Canonical Entity Map
| Entity | Canonical UUID | Name / Details |
|---|---|---|
| **Tenant** | `a2a0b1e6-51bc-4f68-a03e-19ce03c79f94` | Active staging workspace |
| **Source KB (Wrong)** | `476d8908-bb6b-44df-b9fb-538c59bc8d53` | `cricket` |
| **Target KB (Intended)**| `faccb980-145c-4606-b6f1-b80f24fa8141` | `pf` (Physics and Fundamentals) |
| **Assistant** | `62a8fcfd-8967-4093-9b3c-ad53982e555b` | `Notes & Textbook Q&A Assistant` |
| **Conversation** | `018760ef-14cd-4d7d-8747-90089d1b9b5d` | Solar Irradiance Q&A |
| **Attachment** | `e3c5423c-ea1b-4bb5-9408-44947ecba8dc` | `Solar_irradiance__TechScience.pdf` |
| **Promoted Document** | `d5df4dde-ba86-4313-b4d8-c66f5f5b8c80` | Status: `READY`, 117 chunks |

---

## 2. Recovery Options Analysis

### Option 1: Clean Move via SQL (Recommended)
Because the document and all 117 chunks already exist and are indexed, we can update the relational pointers transactionally:
```sql
BEGIN;

-- 1. Update the document's knowledge_base_id
UPDATE documents 
SET knowledge_base_id = 'faccb980-145c-4606-b6f1-b80f24fa8141'
WHERE id = 'd5df4dde-ba86-4313-b4d8-c66f5f5b8c80' 
  AND tenant_id = 'a2a0b1e6-51bc-4f68-a03e-19ce03c79f94';

-- 2. Update the document_chunks table
UPDATE document_chunks 
SET knowledge_base_id = 'faccb980-145c-4606-b6f1-b80f24fa8141'
WHERE document_id = 'd5df4dde-ba86-4313-b4d8-c66f5f5b8c80';

-- 3. Update the conversation_attachments audit pointer
UPDATE conversation_attachments
SET promoted_target_kb_id = 'faccb980-145c-4606-b6f1-b80f24fa8141'
WHERE id = 'e3c5423c-ea1b-4bb5-9408-44947ecba8dc'
  AND tenant_id = 'a2a0b1e6-51bc-4f68-a03e-19ce03c79f94';

COMMIT;
```
- **Pros:** Instantaneous (0 reprocessing needed), retains vector embeddings and chunk metadata, 100% reversible.
- **Cons:** Direct SQL modification.
- **Rollback:** Simply swap the UUIDs back to `476d8908-bb6b-44df-b9fb-538c59bc8d53`.

### Option 2: Upload Fresh to PF via UI
- Navigate to `/dashboard/knowledge?kbId=faccb980-145c-4606-b6f1-b80f24fa8141` ("pf").
- Upload `Solar_irradiance__TechScience.pdf`.
- Delete `d5df4dde-ba86-4313-b4d8-c66f5f5b8c80` from "cricket" via the KB document inspector UI.
- **Pros:** Pure UI workflow, runs full standard ingestion pipeline.
- **Cons:** Re-runs embedding generation and parsing.

---

## 3. Recommended Operator Action

Once M28.13 is deployed to staging, the operator can:
1. Verify the new UI routing with a fresh test attachment to confirm the fix.
2. If desired, execute Option 1 SQL script using the Neon dashboard or authorized migration runner to migrate the existing document from Cricket to PF without data loss.
