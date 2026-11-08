# Remaining Blockers for Unconditional M05 Milestone Release

## 1. Authoritative Status

Milestone 05 remains:
`CONDITIONAL_PASS`

This classification is authoritative and will not be upgraded to unconditional `PASS` until live container infrastructure evidence is captured and validated.

## 2. Pending Live Validation Items (External Execution Required)

The following items cannot be executed locally due to host memory constraints (8 GB total, ~1.2 GB free < 2 GB minimum container threshold) and are pending execution via Snapshot V3 on an external Linux host:

1. **12 PostgreSQL 16 + pgvector Live Integration Tests**:
   - `test_postgres_version_is_16`
   - `test_pgvector_extension_loaded_and_functional`
   - `test_transaction_rollback_and_commit_behavior`
   - `test_migration_head_and_schema_tables`
   - `test_vector_column_data_type_in_postgresql`
   - `test_foreign_key_and_tenant_composite_constraints`
   - `test_native_postgresql_fts_query_and_ranking`
   - `test_native_postgresql_fts_sql_injection_safety`
   - `test_real_pgvector_insert_and_cosine_distance_ranking`
   - `test_pgvector_rejects_dimension_mismatch`
   - `test_cross_tenant_isolation_on_real_postgresql`
   - `test_department_isolation_on_real_postgresql`
2. **5 Qdrant v1.9.0 Live Integration Tests**:
   - `test_qdrant_service_connectivity_and_health`
   - `test_qdrant_collection_creation_and_dimension_isolation`
   - `test_qdrant_upsert_and_filtered_search`
   - `test_qdrant_cross_tenant_payload_isolation`
   - `test_qdrant_scoped_deletion`
3. **Live PostgreSQL Backup & Restore Drill**:
   - Real containerized `pg_dump -Fc` backup and restoration to `m05_restore_drill_disposable`.
   - In-memory BYOK credential decryption verification.
4. **Live Qdrant Application-Driven Rebuild Drill**:
   - Catastrophic disposable collection loss simulation and rebuild from PostgreSQL source chunks via `IngestionService.reindex_knowledge_base`.

## 3. Deployment Boundaries (STRICTLY ENFORCED)

- `STAGING_DEPLOYMENT_AUTHORIZED = false`
- `PRODUCTION_DEPLOYMENT_AUTHORIZED = false`
- `GIT_PUSH_AUTHORIZED = false`
- `PAID_CLOUD_PROVISIONING_AUTHORIZED = false`
- Milestone 06 (M06) development is **NOT STARTED**.
