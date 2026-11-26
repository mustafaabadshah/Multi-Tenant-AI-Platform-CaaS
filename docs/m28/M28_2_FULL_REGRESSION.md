# M28.2 Full Regression & Test Results

## 1. Targeted M28.2 Suite Execution
**Command:**
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_m28_1_html_and_web_repair.py tests/test_m28_message_feedback.py tests/test_m28_beta_and_quota.py tests/test_parsers.py -v --tb=short
```
**Results:**
- Total tests: 28
- Passed: 28
- Failed: 0
- Skipped: 0
- Status: **PASS (100%)**

### Key Tests Verified:
- `test_html_parser_extracts_clean_content_and_code`: PASS
- `test_parser_registry_resolves_html_with_octet_stream_mime`: PASS
- `test_ingestion_permanent_error_classification`: PASS
- `test_empty_html_raises_permanent_value_error`: PASS
- `test_url_extraction_pattern`: PASS
- `test_citation_grounding_prunes_unrelated_pdf_chunks`: PASS
- `test_build_rag_context_anti_refusal_notice`: PASS
- `test_ssrf_blocks_forbidden_destinations`: PASS
- `test_ssrf_connection_level_backend_blocks_private_peer`: PASS
- `test_code_block_url_does_not_trigger_preflight`: PASS
- `test_source_aware_grounding_retains_comparison_only_when_requested`: PASS
- `test_submit_thumbs_up_feedback`: PASS
- `test_update_feedback_idempotent`: PASS
- `test_feedback_on_user_message_rejected`: PASS
- `test_cross_tenant_feedback_denied`: PASS
- `test_feedback_telemetry_accuracy`: PASS
- `test_admin_feedback_stream_and_status_lifecycle`: PASS
- `test_quota_service_usage_summary`: PASS
- `test_beta_cohort_endpoint`: PASS
- `test_pdf_parser_text_and_pages`: PASS
- `test_docx_parser_headings_and_tables`: PASS
- `test_xlsx_parser_sheets_and_rows`: PASS
- `test_pptx_parser_slides_and_titles`: PASS
- `test_csv_parser_delimiter_sniffing`: PASS
- `test_json_parser_paths_and_jsonl`: PASS
- `test_sql_parser_schema_safety`: PASS
- `test_text_and_markdown_parsers`: PASS
- `test_parser_registry_unsupported`: PASS

## 2. Complete Backend Suite Execution
**Command:**
```powershell
.\.venv\Scripts\python.exe -m pytest tests -q --tb=no
```
**Results:**
- Total tests: 738
- Passed: 720
- Skipped: 18 (live external network / mock-free integration tests requiring cloud providers)
- Failed: 0
- Status: **PASS**

## 3. Frontend Regression Execution
### 3.1 Node.js Component & Controller Tests
**Command:** `npm test`
- Total tests: 14 (across 5 test suites)
- Passed: 14
- Failed: 0
- Skipped: 0
- Status: **PASS**

### 3.2 TypeScript Typecheck
**Command:** `npx tsc --noEmit`
- Errors: 0
- Status: **PASS**

### 3.3 Next.js Production Build
**Command:** `npm run build`
- Routes Compiled: 24/24 static & partial prerender pages
- Turbopack compilation: Clean
- Status: **PASS**

## 4. Gate Assessment
**M28_2_FULL_REGRESSION = PASS**
All backend and frontend regression suites are green.
