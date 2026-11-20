# M28.5 Release Plan & Staging Deployment Gate

## 1. Release Identification

- **Milestone:** M28.5 (Production-Path HTML Ingestion Repair, Existing Document Recovery, and Universal Intelligence)
- **Git Branch:** `main`
- **Target Git Remote:** `https://github.com/mustafaabadshah/Multi-Tenant-AI-Platform-CaaS`
- **Current Remote HEAD:** `822f238263c8029fd3b1e349a48b0a7c97fbf83d`
- **Neon Staging Branch:** `br-tiny-wind-arvfyx75` (`mmaip_staging`)
- **Neon Safety Checkpoint:** `pre-m28-quality-release-20261118` (`br-snowy-pine-ar3d40qx`)
- **Render Backend Service:** `srv-dbrk57gn74is73fqo4k0`
- **Render Frontend Service:** `srv-dbrkthcipgvc739d6oh0`

## 2. File Change Allowlist

The exact set of modified and added files to be included in the release commit:

### Backend Implementation
- `backend/app/assistant_runtime/context.py` (Source provenance and OCR labeling)
- `backend/app/assistant_runtime/runtime.py` (Provenance propagation)
- `backend/app/parsers/__init__.py` (ImageParser export)
- `backend/app/parsers/html.py` (Deceptive binary protection, BOM stripping, HTML detection)
- `backend/app/parsers/image.py` (Raster image parser)
- `backend/app/parsers/pdf.py` (Selective OCR on scanned pages)
- `backend/app/parsers/registry.py` (Format sniffing, octet-stream HTML routing, non-HTML validation)
- `backend/app/schemas/knowledge.py` (metadata_json field on DocumentResponse)
- `backend/app/services/ingestion/limits.py` (Typed errors: TemporaryStorageError, TemporaryDatabaseError, IndexingError)
- `backend/app/services/ingestion/service.py` (detected_format recording, transient error separation)
- `backend/app/services/ocr_service.py` (Tesseract detection, downscaling, bomb guard, graceful degradation)
- `backend/app/services/web/kb_saver.py` (REFERENCE, NOTES, SEARCHABLE_CONTENT modes, page_number=None)
- `backend/app/services/web/reader.py` (Multi-format URL dispatcher)
- `backend/app/api/v1/documents.py` (Reprocess duplicate in-flight guard, storage verification, artifact purge)

### Backend Tests
- `backend/tests/test_m28_4_universal_intelligence_and_ocr.py` (9 tests)
- `backend/tests/test_m28_5_production_html_recovery.py` (5 tests)

### Frontend Implementation
- `frontend/app/dashboard/conversations/page.tsx` (3-way KB save modal)
- `frontend/app/dashboard/knowledge/page.tsx` (accept attribute, READY badge, detected format overview, reprocess message)
- `frontend/lib/api.ts` (DocumentItem metadata_json, saveWebSourceToKB storage modes)

### Documentation Artifacts
- `docs/m28/M28_4_BASELINE_AND_SOURCE_CAPABILITIES.md`
- `docs/m28/M28_4_UNIVERSAL_WEB_READER.md`
- `docs/m28/M28_4_DOCUMENT_AND_OCR_PIPELINE.md`
- `docs/m28/M28_4_SOURCE_PROVENANCE_AND_RAG.md`
- `docs/m28/M28_4_KB_IMPORT_AND_AUTHORIZATION.md`
- `docs/m28/M28_4_VOICE_ACCEPTANCE.md`
- `docs/m28/M28_4_UX_AND_ACCESSIBILITY.md`
- `docs/m28/M28_4_QUALITY_OPERATIONS.md`
- `docs/m28/M28_4_SECURITY_AND_RESOURCE_VALIDATION.md`
- `docs/m28/M28_4_RELEASE_PLAN.md`
- `docs/m28/M28_4_MASTER_FINAL_REPORT.md`
- `docs/m28/M28_5_LIVE_FAILURE_ROOT_CAUSE.md`
- `docs/m28/M28_5_HTML_INGESTION_E2E.md`
- `docs/m28/M28_5_DOCUMENT_RECOVERY.md`
- `docs/m28/M28_5_OCR_DEPLOYMENT_AUDIT.md`
- `docs/m28/M28_5_RELEASE_PLAN.md`
- `docs/m28/M28_5_MASTER_FINAL_REPORT.md`

## 3. Database Migration Gate
- **Database Migrations Required:** **NONE**.
- Current database revision `0018_m28_message_feedback` already includes all required tables and JSON columns (`Document.metadata_json`, `DocumentVersion.structured_data`, `DocumentVersion.extraction_stats`).

## 4. Staging Deployment Execution Sequence (Awaiting Operator Signoff)

1. **Commit Allowlisted Files:**
   ```bash
   git add <allowlist>
   git commit -m "feat(m28.5): production-path HTML ingestion repair, document recovery, and universal intelligence"
   ```
2. **Push to GitHub Origin:**
   ```bash
   git push origin main
   ```
3. **Trigger Render Deployments:**
   - Deploy Backend (`srv-dbrk57gn74is73fqo4k0`).
   - Deploy Frontend (`srv-dbrkthcipgvc739d6oh0`).
4. **Post-Deployment Verification:**
   - Verify deployed commit SHAs on Render match Git HEAD.
   - Execute operator staging acceptance protocol on `C___For_Loop.html`.
