# Knowledge Studio — Product Specification (M07)

## Overview
The Knowledge Studio transforms document ingestion and knowledge base management into an intuitive, transparent workspace where both non-technical users and domain experts can inspect how documents are ingested, transformed into chunks, and retrieved.

---

## 1. Core User Workflows

1. **Knowledge Base Containers**:
   - Organize domain documents by department, team, or project.
   - Status tracking (`ACTIVE`, `ARCHIVED`, `PROCESSING`).
   - Granular RBAC and department-level access control.

2. **Source Ingestion**:
   - **Supported File Types**: PDF, DOCX, XLSX, PPTX, CSV, TSV, JSON, JSONL, Markdown, TXT, and SQL.
   - **Safe Web Page Ingestion**: Users can provide HTTP/HTTPS documentation URLs. The server applies strict SSRF controls, extracts semantic content and titles, and indexes them seamlessly into the active knowledge base.

3. **Chunk Inspector**:
   - Inspect exact chunk boundaries, token counts, character lengths, heading paths, and page numbers.
   - Preserves source provenance without synthetic or fabricated bounding boxes.
   - Compare chunking strategies (`recursive`, `markdown`, `token`, `structured`).

4. **Retrieval Playground**:
   - Test queries interactively against live index stores.
   - Inspect rank, dense score, sparse score (`ts_rank_cd`), and hybrid reciprocal rank fusion (RRF) scores.
   - View latency in milliseconds and verify citations before linking knowledge bases to production assistants.
