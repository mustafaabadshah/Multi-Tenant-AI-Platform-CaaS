# M28.5 Live Failure Root Cause Analysis: C___For_Loop.html

## 1. Incident Overview

In the live staging environment (`mmaip_staging`, Render service `srv-dbrk57gn74is73fqo4k0`), a user-uploaded HTML document remained in permanent `FAILED` status across multiple retries:

- **Filename:** `C___For_Loop.html`
- **File Size:** 268,553 bytes
- **SHA-256:** `90685c333c7049b14dc6622e5b20733b2746f8c2a1aea9d558d579786da5907d`
- **Document ID:** `c4959352-28b6-423e-a6b4-16a82ccdb334`
- **Document Version ID:** `f8a7e7e0-3a36-49fa-8430-c288ec4cbeac` (Version 1)
- **Knowledge Base ID:** `faccb980-145c-4606-b6f1-b80f24fa8141`
- **Tenant ID:** `a2a0b1e6-51bc-4f68-a03e-19ce03c79f94`
- **Stored MIME Type:** `application/octet-stream`
- **Object Key in B2 Storage:**
  `tenants/a2a0b1e6-51bc-4f68-a03e-19ce03c79f94/kbs/faccb980-145c-4606-b6f1-b80f24fa8141/docs/c4959352-28b6-423e-a6b4-16a82ccdb334/v1/C___For_Loop.html`

## 2. Direct Forensic Evidence (Live Neon Staging DB Query)

A read-only inspection of `ingestion_jobs` and `document_versions` in `mmaip_staging` revealed the exact failure record:

```json
{
  "id": "6c78451d-0e86-43c8-963d-d7a39b4aadd6",
  "document_id": "c4959352-28b6-423e-a6b4-16a82ccdb334",
  "document_version_id": "f8a7e7e0-3a36-49fa-8430-c288ec4cbeac",
  "status": "FAILED",
  "stage": "FAILED",
  "progress_pct": 20,
  "retry_count": 4,
  "max_retries": 3,
  "error_category": "ValueError",
  "error_message": "Unsupported document format: extension '.html', detected MIME 'application/octet-stream'. Supported extensions: .csv, .ddl, .docx, .json, .jsonl, .log, .markdown, .md, .pdf, .pptx, .sql, .text, .tsv, .txt, .xlsm, .xlsx",
  "duration_ms": 2020
}
```

## 3. Root Cause Decomposition

### 3.1 Unregistered Parser in the Deployed Image
The error message explicitly listed all extensions supported by the worker that processed the file:
`.csv, .ddl, .docx, .json, .jsonl, .log, .markdown, .md, .pdf, .pptx, .sql, .text, .tsv, .txt, .xlsm, .xlsx`

Noticeably absent: `.html` and `.htm`.
The deployed container on Render was running pre-M28 code before `HTMLParser` was added and registered in `ParserRegistry`. When the ingestion job executed `ParserRegistry.resolve_parser("C___For_Loop.html", content, "application/octet-stream")`, the registry rejected `.html` with `UnsupportedFormatError`.

### 3.2 MIME Fallback Defect
When `C___For_Loop.html` was originally uploaded, the browser sent `application/octet-stream` (common for drag-and-drop or Windows curl/PowerShell uploads without explicit MIME negotiation).
Because the old `detect_mime_type` only checked `filetype.guess(content)` (which does not detect text-based HTML) and did not have `.html` mapped in its extension table, the stored MIME remained `application/octet-stream`.

### 3.3 Retry Loop Misclassification
`UnsupportedFormatError` was a subclass of `ValueError`. In the legacy ingestion service, it was not categorized in `PERMANENT_INGESTION_ERRORS`, causing the worker to retry 4 times before hitting the `max_retries` ceiling and marking the job `FAILED`.

### 3.4 Missing Frontend Reprocess Invocation
The frontend `knowledge/page.tsx` contained `handleReprocessDoc`, but the modal overview tab did not pass `doc.filename`, and table rows lacked clear user feedback on which extractor was being applied.

## 4. Remediation Implemented

1. **Parser Registration & Format Sniffing:**
   Updated `ParserRegistry.detect_mime_type` and `resolve_parser` to inspect bounded HTML content signatures (`<!doctype html`, `<html`, `<head`, `<body`, tags) and map `.html`/`.htm` to `HTMLParser`.
2. **Deceptive Binary Protection:**
   Hardened `HTMLParser.validate` to reject files starting with executable headers (`MZ`, `ELF`, Mach-O, `PK\x03\x04`, `%PDF-`, PNG/JPEG magic bytes) even if given an `.html` extension.
3. **MIME Distinction:**
   Preserved historical uploaded `doc.mime_type` (`application/octet-stream`) while recording `doc.metadata_json["detected_format"] = "HTML"` and `doc.metadata_json["detected_mime"] = "text/html"`.
4. **Permanent vs Transient Errors:**
   Explicitly mapped `UnsupportedFormatError` and `UnparseableDocumentError` to `PERMANENT_INGESTION_ERRORS` to eliminate useless retry loops on unparseable files, while allowing `TemporaryStorageError` and `TemporaryDatabaseError` to retry safely.
