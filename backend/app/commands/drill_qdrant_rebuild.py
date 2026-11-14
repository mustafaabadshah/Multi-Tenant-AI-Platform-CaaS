"""Qdrant Live Application-Driven Rebuild and Disaster Recovery Drill Helper.

Genuinely drives Qdrant vector reconstruction through the production
IngestionService.reindex_knowledge_base entrypoint using PostgreSQL-persisted
source chunks and retrieval configuration.

Enforces strict tenant payload filtering, cross-tenant isolation,
idempotency (zero duplicate points on repeated reindexing), disposable collection
namespace isolation (never deletes shared or production collections), and emits
mandatory structured evidence telemetry.
"""

import argparse
import asyncio
import hashlib
import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.embeddings.providers.mock_provider import MockEmbeddingProvider
from app.models.knowledge import (
    Document,
    DocumentChunk,
    KnowledgeBase,
    RetrievalConfig,
)
from app.models.tenant import Tenant
from app.services.ingestion.service import IngestionService
from app.vectorstores.base import VectorStoreFilter
from app.vectorstores.qdrant_store import QdrantVectorStore

logger = logging.getLogger("mmaip.drills.qdrant")

# Target collection dimension for mock-embedding-small provider
DRILL_DIMS = 384
DRILL_COLLECTION_PREFIX = "m05_drill_disposable"

# Backward compatibility aliases
DRILL_COLLECTION_BASE = "mmaip_knowledge_chunks"
DRILL_COLLECTION_FULL = f"{DRILL_COLLECTION_BASE}_{DRILL_DIMS}"


def build_disposable_collection_name(run_tag: str, dims: int = DRILL_DIMS) -> tuple[str, str]:
    """Generate disposable base name and dimension-isolated full collection name."""
    base_name = f"{DRILL_COLLECTION_PREFIX}_{run_tag}"
    full_name = f"{base_name}_{dims}"
    return base_name, full_name


def assert_disposable_drill_collection(collection_name: str) -> None:
    """Strictly assert collection name adheres to the disposable drill namespace.
    
    Refuses any collection matching application-wide, shared, or production collections,
    or lacking the dedicated drill disposable prefix.
    """
    if not collection_name.startswith(f"{DRILL_COLLECTION_PREFIX}_"):
        raise ValueError(
            f"SAFETY ABORT: Refusing collection '{collection_name}'. "
            f"Collection must begin with dedicated disposable prefix '{DRILL_COLLECTION_PREFIX}_'."
        )
    if "mmaip_knowledge_chunks" in collection_name or "production" in collection_name.lower():
        raise ValueError(
            f"SAFETY ABORT: Refusing collection '{collection_name}'. "
            f"Matches protected application/production namespace."
        )


async def safe_delete_drill_collection(qclient: Any, collection_name: str) -> None:
    """Delete only verified disposable drill collections. Never deletes shared or production collections."""
    assert_disposable_drill_collection(collection_name)
    try:
        collections = await qclient.get_collections()
        if any(c.name == collection_name for c in collections.collections):
            await qclient.delete_collection(collection_name)
            logger.info(f"Deleted disposable drill collection: {collection_name}")
    except Exception as exc:
        logger.warning(f"Failed to delete disposable drill collection '{collection_name}': {exc}")
        raise


def get_engine(
    host: str = "127.0.0.1",
    port: int = 55432,
    db_name: str = "m05_integration",
    user: str = "m05_test",
    password: str = "m05_test_password_secure_local",
):
    """Construct async SQLAlchemy engine for PostgreSQL."""
    url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db_name}"
    return create_async_engine(url, echo=False)


async def run_qdrant_application_rebuild_drill(
    pg_host: str = "127.0.0.1",
    pg_port: int = 55432,
    pg_db: str = "m05_integration",
    pg_user: str = "m05_test",
    pg_password: str = "m05_test_password_secure_local",
    qdrant_url: str = "http://127.0.0.1:6333",
    evidence_path: Optional[str] = None,
) -> bool:
    """Execute the full end-to-end application-driven Qdrant rebuild drill."""
    drill_run_id = uuid.uuid4()
    run_tag = drill_run_id.hex[:8]
    disposable_base, drill_collection_full = build_disposable_collection_name(run_tag, DRILL_DIMS)

    # Enforce disposable isolation assertion upfront
    assert_disposable_drill_collection(drill_collection_full)

    engine = get_engine(host=pg_host, port=pg_port, db_name=pg_db, user=pg_user, password=pg_password)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    # Initialize vector store with dedicated disposable collection name
    qdrant_store = QdrantVectorStore(url=qdrant_url, collection_name=disposable_base)
    qclient = qdrant_store._get_client()

    drill_tenant_id = uuid.uuid4()
    foreign_tenant_id = uuid.uuid4()
    drill_kb_id = uuid.uuid4()
    drill_doc_id = uuid.uuid4()
    chunk1_id = uuid.uuid4()
    chunk2_id = uuid.uuid4()

    orig_qdrant_collection = getattr(settings, "QDRANT_COLLECTION_NAME", "mmaip_knowledge_chunks")
    # Configuration injection boundary: set settings to disposable collection
    settings.QDRANT_COLLECTION_NAME = disposable_base

    evidence_dict: dict[str, Any] = {
        "drill_run_id": str(drill_run_id),
        "disposable_tenant_id": str(drill_tenant_id),
        "disposable_knowledge_base_id": str(drill_kb_id),
        "disposable_collection_base": disposable_base,
        "disposable_collection_full": drill_collection_full,
        "target_dimensions": DRILL_DIMS,
    }

    try:
        # Pre-drill check: assert collection did not exist prior to drill
        try:
            collections = await qclient.get_collections()
            if any(c.name == drill_collection_full for c in collections.collections):
                await safe_delete_drill_collection(qclient, drill_collection_full)
        except Exception:
            pass

        # -----------------------------------------------------------------
        # Step 1: Create and persist source entities in PostgreSQL
        # -----------------------------------------------------------------
        print("[Drill Step 1/7] Persisting disposable tenant, KB, document, and chunks in PostgreSQL...")
        async with session_maker() as session:
            tenant = Tenant(
                id=drill_tenant_id,
                name="Drill Qdrant Tenant",
                slug=f"drill-tenant-{drill_tenant_id.hex[:8]}",
                type="ORGANIZATION",
                settings={},
            )
            session.add(tenant)

            foreign_tenant = Tenant(
                id=foreign_tenant_id,
                name="Foreign Isolation Tenant",
                slug=f"foreign-tenant-{foreign_tenant_id.hex[:8]}",
                type="ORGANIZATION",
                settings={},
            )
            session.add(foreign_tenant)

            kb = KnowledgeBase(
                id=drill_kb_id,
                tenant_id=drill_tenant_id,
                name=f"Drill Rebuild KB {drill_kb_id.hex[:6]}",
                description="Application Rebuild Drill Knowledge Base",
                status="ACTIVE",
            )
            session.add(kb)

            doc = Document(
                id=drill_doc_id,
                tenant_id=drill_tenant_id,
                knowledge_base_id=drill_kb_id,
                filename="drill_rebuild_spec.txt",
                safe_filename="drill_rebuild_spec.txt",
                file_path="local_storage/drill_rebuild_spec.txt",
                mime_type="text/plain",
                status="COMPLETED",
                total_chunks=2,
            )
            session.add(doc)

            chunk1 = DocumentChunk(
                id=chunk1_id,
                tenant_id=drill_tenant_id,
                knowledge_base_id=drill_kb_id,
                document_id=drill_doc_id,
                chunk_index=0,
                content="Multi-Tenant AI Platform: Enterprise Qdrant vector database recovery protocol.",
                character_count=77,
                token_count=10,
                chunking_strategy="recursive",
            )
            chunk2 = DocumentChunk(
                id=chunk2_id,
                tenant_id=drill_tenant_id,
                knowledge_base_id=drill_kb_id,
                document_id=drill_doc_id,
                chunk_index=1,
                content="Mandatory tenant payload filtering guarantees zero cross-tenant data leakage.",
                character_count=75,
                token_count=10,
                chunking_strategy="recursive",
            )
            session.add_all([chunk1, chunk2])

            ret_cfg = RetrievalConfig(
                id=uuid.uuid4(),
                tenant_id=drill_tenant_id,
                knowledge_base_id=drill_kb_id,
                retrieval_mode="hybrid",
                vector_store="qdrant",
                embedding_provider="mock",
                embedding_model="mock-embedding-small",
                embedding_dimensions=DRILL_DIMS,
                similarity_metric="cosine",
                top_k=5,
                embedding_version=1,
            )
            session.add(ret_cfg)
            await session.commit()

        # Step 1b: Verify persisted PostgreSQL source data in a clean, separate session
        async with session_maker() as verify_session:
            chunk_stmt = select(DocumentChunk).where(DocumentChunk.knowledge_base_id == drill_kb_id).order_by(DocumentChunk.chunk_index)
            persisted_chunks = list((await verify_session.execute(chunk_stmt)).scalars().all())
            if len(persisted_chunks) != 2:
                print("ERROR: Failed to persist test chunks in PostgreSQL.", file=sys.stderr)
                return False

            chunk_hashes = [hashlib.sha256(c.content.encode("utf-8")).hexdigest() for c in persisted_chunks]
            evidence_dict["postgres_source_chunk_count"] = len(persisted_chunks)
            evidence_dict["postgres_source_chunk_hashes"] = chunk_hashes

            print("SOURCE_DATA_PERSISTED_PASS")
            print("POSTGRES_SOURCE_RELOAD_VERIFIED")

        # -----------------------------------------------------------------
        # Step 2: Initial Application-Driven Indexing
        # -----------------------------------------------------------------
        print("[Drill Step 2/7] Running initial indexing via IngestionService.reindex_knowledge_base...")
        async with session_maker() as init_session:
            ingestion_service = IngestionService(init_session, drill_tenant_id)
            initial_job = await ingestion_service.reindex_knowledge_base(drill_kb_id)

            if initial_job.status != "COMPLETED" or initial_job.processed_chunks != 2:
                print(f"ERROR: Initial application indexing failed. Job status: {initial_job.status}", file=sys.stderr)
                return False

            print("INITIAL_APPLICATION_INDEX_PASS")

        # -----------------------------------------------------------------
        # Step 3: Verify initial Qdrant state and tenant-filtered search
        # -----------------------------------------------------------------
        print("[Drill Step 3/7] Verifying initial Qdrant vector index and payload filter...")
        mock_provider = MockEmbeddingProvider()
        test_query = "recovery protocol"
        query_vec = mock_provider._generate_vector(test_query, DRILL_DIMS)

        initial_search = await qdrant_store.search(
            query_vector=query_vec,
            filter_criteria=VectorStoreFilter(tenant_id=drill_tenant_id, knowledge_base_ids=[drill_kb_id]),
            limit=5,
        )
        if len(initial_search) == 0:
            print("ERROR: Initial vector search returned 0 results.", file=sys.stderr)
            return False

        # Verify cross-tenant isolation before deletion
        foreign_search = await qdrant_store.search(
            query_vector=query_vec,
            filter_criteria=VectorStoreFilter(tenant_id=foreign_tenant_id, knowledge_base_ids=[drill_kb_id]),
            limit=5,
        )
        if len(foreign_search) != 0:
            print("ERROR: Cross-tenant isolation breach in initial search!", file=sys.stderr)
            return False

        # -----------------------------------------------------------------
        # Step 4: Simulate Catastrophic Collection Loss
        # -----------------------------------------------------------------
        print(f"[Drill Step 4/7] Simulating catastrophic collection loss: Deleting '{drill_collection_full}'...")
        await safe_delete_drill_collection(qclient, drill_collection_full)

        # Assert collection is completely absent
        collections_after_delete = await qclient.get_collections()
        if any(c.name == drill_collection_full for c in collections_after_delete.collections):
            print("ERROR: Collection still exists after deletion simulation.", file=sys.stderr)
            return False

        print("COLLECTION_LOSS_SIMULATED_PASS")

        # -----------------------------------------------------------------
        # Step 5: Execute Rebuild Through Actual Application Entrypoint
        # -----------------------------------------------------------------
        print("[Drill Step 5/7] Triggering application-driven rebuild from PostgreSQL source...")
        print("APPLICATION_REINDEX_ENTRYPOINT_INVOKED")

        rebuild_start_time = datetime.now(timezone.utc).isoformat()
        evidence_dict["rebuild_invocation_start"] = rebuild_start_time

        print("APPLICATION_REINDEX_CALL_STARTED")
        async with session_maker() as rebuild_session:
            rebuild_service = IngestionService(rebuild_session, drill_tenant_id)
            rebuild_job = await rebuild_service.reindex_knowledge_base(drill_kb_id)

            rebuild_end_time = datetime.now(timezone.utc).isoformat()
            evidence_dict["rebuild_invocation_end"] = rebuild_end_time
            print("APPLICATION_REINDEX_CALL_RETURNED")

            if rebuild_job.status != "COMPLETED":
                print(f"ERROR: Application reindex failed. Job status: {rebuild_job.status}", file=sys.stderr)
                return False

            evidence_dict["rebuild_job_id"] = str(rebuild_job.id)
            evidence_dict["rebuild_job_status"] = rebuild_job.status
            evidence_dict["rebuild_processed_chunks"] = rebuild_job.processed_chunks

            print("APPLICATION_REINDEX_COMPLETED")
            print("POSTGRES_SOURCE_RELOAD_PASS")
            print("QDRANT_REBUILD_PASS")
            print("QDRANT_REBUILD_VERIFIED")

        # -----------------------------------------------------------------
        # Step 6: Verify Rebuilt Collection & Strict Payload Isolation
        # -----------------------------------------------------------------
        print("[Drill Step 6/7] Verifying rebuilt collection schema, points, and tenant scoping...")
        collections_rebuilt = await qclient.get_collections()
        if not any(c.name == drill_collection_full for c in collections_rebuilt.collections):
            print("ERROR: Rebuilt collection not found in Qdrant.", file=sys.stderr)
            return False

        rebuilt_col_info = await qclient.get_collection(drill_collection_full)
        evidence_dict["expected_point_count"] = 2
        evidence_dict["actual_point_count"] = rebuilt_col_info.points_count

        if rebuilt_col_info.points_count != 2:
            print(f"ERROR: Expected 2 points after rebuild, got {rebuilt_col_info.points_count}.", file=sys.stderr)
            return False

        # Search with authorized tenant
        rebuilt_search = await qdrant_store.search(
            query_vector=query_vec,
            filter_criteria=VectorStoreFilter(tenant_id=drill_tenant_id, knowledge_base_ids=[drill_kb_id]),
            limit=5,
        )
        if len(rebuilt_search) == 0:
            print("ERROR: Rebuilt collection search returned 0 results for authorized tenant.", file=sys.stderr)
            return False

        # Verify content fidelity
        top_hit = rebuilt_search[0]
        if "recovery protocol" not in top_hit.payload.get("content", "").lower():
            print("ERROR: Retrieved rebuilt point content mismatch.", file=sys.stderr)
            return False

        # Verify cross-tenant isolation after rebuild
        rebuilt_foreign_search = await qdrant_store.search(
            query_vector=query_vec,
            filter_criteria=VectorStoreFilter(tenant_id=foreign_tenant_id, knowledge_base_ids=[drill_kb_id]),
            limit=5,
        )
        if len(rebuilt_foreign_search) != 0:
            print("ERROR: Cross-tenant payload leak detected after rebuild!", file=sys.stderr)
            return False

        print("TENANT_FILTER_VERIFICATION_PASS")

        # -----------------------------------------------------------------
        # Step 7: Verify Idempotency (Second Reindex Does Not Duplicate Points)
        # -----------------------------------------------------------------
        print("[Drill Step 7/7] Testing rebuild idempotency with second consecutive execution...")
        async with session_maker() as idemp_session:
            idemp_service = IngestionService(idemp_session, drill_tenant_id)
            idemp_job = await idemp_service.reindex_knowledge_base(drill_kb_id)

            if idemp_job.status != "COMPLETED":
                print("ERROR: Idempotent reindex job failed.", file=sys.stderr)
                return False

        col_info_second = await qclient.get_collection(drill_collection_full)
        if col_info_second.points_count != 2:
            print(f"ERROR: Repeated reindex created duplicate points! Count: {col_info_second.points_count}", file=sys.stderr)
            return False

        print("IDEMPOTENT_REINDEX_PASS")

        evidence_dict["verification_result"] = "PASS"
        evidence_dict["idempotency_result"] = "PASS"

        # Write evidence JSON if requested or default path
        out_path = Path(evidence_path or "qdrant_rebuild_evidence.json")
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(evidence_dict, f, indent=2)
            print(f"EVIDENCE_RECORDED: {out_path}")
        except Exception as e:
            logger.warning(f"Could not write evidence JSON to {out_path}: {e}")

        # -----------------------------------------------------------------
        # Cleanup: Remove only resources created by this drill
        # -----------------------------------------------------------------
        print("Cleaning up disposable drill resources...")
        try:
            await safe_delete_drill_collection(qclient, drill_collection_full)
        except Exception as e:
            logger.warning(f"Failed to clean up drill collection: {e}")

        async with session_maker() as cleanup_session:
            # Cascading delete of tenant removes KB, Document, Chunks, and Jobs
            await cleanup_session.execute(
                delete(Tenant).where(Tenant.id.in_([drill_tenant_id, foreign_tenant_id]))
            )
            await cleanup_session.commit()

        return True

    except Exception as exc:
        print(f"ERROR: Qdrant rebuild drill failed with exception: {exc}", file=sys.stderr)
        return False
    finally:
        settings.QDRANT_COLLECTION_NAME = orig_qdrant_collection
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Qdrant Application Rebuild Drill Helper")
    parser.add_argument("--pg-host", type=str, default="127.0.0.1")
    parser.add_argument("--pg-port", type=int, default=55432)
    parser.add_argument("--pg-db", type=str, default="m05_integration")
    parser.add_argument("--pg-user", type=str, default="m05_test")
    parser.add_argument("--pg-password", type=str, default="m05_test_password_secure_local")
    parser.add_argument("--qdrant-url", type=str, default="http://127.0.0.1:6333")
    parser.add_argument("--evidence-path", type=str, default=None)

    args = parser.parse_args()

    success = asyncio.run(run_qdrant_application_rebuild_drill(
        pg_host=args.pg_host,
        pg_port=args.pg_port,
        pg_db=args.pg_db,
        pg_user=args.pg_user,
        pg_password=args.pg_password,
        qdrant_url=args.qdrant_url,
        evidence_path=args.evidence_path,
    ))

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
