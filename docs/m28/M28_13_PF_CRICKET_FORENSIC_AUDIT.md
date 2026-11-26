# M28.13 PF & Cricket Staging Forensic Audit

**Milestone:** M28.13 — Critical Knowledge Base Data Integrity, Assistant-KB Routing, Refresh Loop, Back Navigation & End-to-End Reliability  
**Date:** November 19, 2026  
**Target Environment:** Neon Staging (`aged-heart-01771250`), database `mmaip_staging`  
**Execution:** Read-Only Forensic Query Script (`inspect_pf_cricket.py`)  

---

## 1. Forensic Inquiry Objectives

1. Determine the canonical IDs and tenant ownership of the **PF** and **Cricket** Knowledge Bases.
2. Verify the configuration and connected Knowledge Bases of the **Notes & Textbook Q&A Assistant**.
3. Locate the conversation where the operator uploaded the solar irradiance file.
4. Establish the exact record of the uploaded attachment, its promotion status, the destination KB, and the resulting Document and Chunks.
5. Answer all 10 forensic questions specified in Phase 4 of the Master Execution Prompt.

---

## 2. Canonical Forensic Evidence

### 2.1 Workspace / Tenant
- **Tenant ID:** `a2a0b1e6-51bc-4f68-a03e-19ce03c79f94`
- Both "cricket" and "pf" reside within the **same** tenant. This was not a cross-tenant data leak, but an intra-tenant destination misrouting.

### 2.2 Knowledge Bases
| Knowledge Base Name | Canonical UUID | Status | Created At | Description |
|---|---|---|---|---|
| **cricket** | `476d8908-bb6b-44df-b9fb-538c59bc8d53` | `active` | 2026-11-18 10:29:43 UTC | general |
| **pf** | `faccb980-145c-4606-b6f1-b80f24fa8141` | `active` | 2026-11-18 13:42:04 UTC | Physics and Fundamentals |

### 2.3 Assistant Configuration
- **Assistant Name:** `Notes & Textbook Q&A Assistant`
- **Assistant UUID:** `62a8fcfd-8967-4093-9b3c-ad53982e555b`
- **Model:** `auto`
- **Connected Knowledge Bases:**
  - `faccb980-145c-4606-b6f1-b80f24fa8141` (**pf** ONLY)
- **Cricket Connection:** **None**. The assistant has never been connected to the "cricket" KB.

### 2.4 Conversation & Attachment
- **Conversation UUID:** `018760ef-14cd-4d7d-8747-90089d1b9b5d`
  - Assistant ID: `62a8fcfd-8967-4093-9b3c-ad53982e555b`
  - Title: *"Solar Irradiance Q&A"*
- **Attachment UUID:** `e3c5423c-ea1b-4bb5-9408-44947ecba8dc`
  - Filename: `Solar_irradiance__TechScience.pdf`
  - Content Type: `application/pdf`
  - Byte Size: 1,482,912 bytes
  - Promoted Flag: `true`
  - Promoted Target KB ID: `476d8908-bb6b-44df-b9fb-538c59bc8d53` (**cricket**)
  - Promoted Document ID: `d5df4dde-ba86-4313-b4d8-c66f5f5b8c80`

### 2.5 Promoted Document & Search Status
- **Document UUID:** `d5df4dde-ba86-4313-b4d8-c66f5f5b8c80`
  - Knowledge Base ID: `476d8908-bb6b-44df-b9fb-538c59bc8d53` (**cricket**)
  - Title: `Solar_irradiance__TechScience.pdf`
  - Status: `READY`
  - Storage Backend: `b2`
  - Total Chunks Indexed: **117 chunks**
  - Chunks Table: 117 records in `document_chunks` for document `d5df4dde-ba86-4313-b4d8-c66f5f5b8c80` with vector embeddings.

---

## 3. Findings for the 10 Specific Audit Questions

| # | Question | Finding | Evidence / Details |
|---|---|---|---|
| 1 | Was the solar file uploaded temporarily to Chat? | **YES** | Attachment `e3c5423c-ea1b-4bb5-9408-44947ecba8dc` was created in conversation `018760ef-14cd-4d7d-8747-90089d1b9b5d`. |
| 2 | Was it promoted to Cricket? | **YES** | Destination KB is `476d8908-bb6b-44df-b9fb-538c59bc8d53` ("cricket"). |
| 3 | Was it also saved to PF? | **NO** | No document with title `Solar_irradiance__TechScience.pdf` exists in KB `faccb980-145c-4606-b6f1-b80f24fa8141` ("pf"). |
| 4 | Was it a duplicate upload? | **NO** | Only one attachment record and one document record exist for this file. |
| 5 | Was the active assistant connected to PF at the time? | **YES** | `assistant_knowledge_bases` shows association with `faccb980-145c-4606-b6f1-b80f24fa8141` ("pf") only. |
| 6 | Did the selected destination change during the modal session? | **NO** | The UI silently initialized to `knowledgeBases[0].id` ("cricket") because "cricket" was first in the array. The user clicked Save without changing it. |
| 7 | Does the backend record the true destination? | **YES** | The backend accurately persisted `target_knowledge_base_id = cricket_uuid` because the client sent that ID in the JSON body. |
| 8 | Is the document READY, FAILED or PROCESSING? | **READY** | Document status is `READY` with 117 parsed chunks. |
| 9 | Is the document searchable by the intended assistant? | **NO** | The assistant is connected to "pf". When queries are made, the RAG retriever filters by `knowledge_base_id IN (pf_uuid)`. Chunks in "cricket" are excluded. |
| 10 | Were any existing files overwritten? | **NO** | Unique UUIDs were generated for both the attachment and the document. No existing data was overwritten. |

---

## 4. Conclusion

The staging database confirms that the data integrity failure was **silent client-side misrouting via index-0 fallback**. The storage and database layers operated deterministically as instructed by the API request.

Because live mutations were explicitly forbidden during this audit, the document remains in "cricket" pending operator review. An operator-executed safe recovery plan is provided in `docs/m28/M28_13_OPERATOR_RECOVERY_PLAN.md`.
