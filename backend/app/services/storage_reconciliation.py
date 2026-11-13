"""Tenant-scoped reconciliation between database documents and object storage.

The service is read-only by default. ``fix=True`` only mutates state after a
complete storage inventory has been collected. Orphan objects are deleted only
when ``fix``, ``delete_orphans``, and a verified complete inventory are all
present. Uncertain storage responses never mark documents FAILED and never
produce object deletions.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import Document
from app.models.tenant import Tenant
from app.storage.base import (
    StorageError,
    StorageNotFoundError,
    StorageProvider,
)

logger = logging.getLogger("mmaip.storage.reconciliation")

DEFAULT_BATCH_SIZE = 500
MAX_REPORTED_ITEMS = 1000
MAX_ORPHAN_DELETIONS_PER_RUN = 1000
MISSING_OBJECT_STATE = "OBJECT_MISSING"
MISSING_OBJECT_NOTE = "Stored object is missing; document marked FAILED by reconciliation."
INVENTORY_COMPLETE = "complete"
INVENTORY_INCOMPLETE = "incomplete"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _resolve_tenant_ids(
    session: AsyncSession, tenant_id: uuid.UUID | str | None
) -> list[uuid.UUID]:
    if tenant_id is not None:
        return [uuid.UUID(str(tenant_id))]

    tenant_rows = await session.execute(select(Tenant.id).order_by(Tenant.id))
    tenant_ids = set(tenant_rows.scalars().all())

    # Include tenants that still own documents even if the tenant row is gone,
    # so their objects are not silently skipped.
    document_rows = await session.execute(select(Document.tenant_id).distinct())
    tenant_ids.update(document_rows.scalars().all())
    return sorted(tenant_ids)


async def _mark_document_failed(document: Document) -> bool:
    """Mark a document FAILED and record a sanitized reconciliation note.

    Returns ``True`` only when this call changed the persisted state, so repeat
    fix runs remain idempotent in their counters.
    """
    metadata = dict(document.metadata_json or {})
    previous = metadata.get("storage_reconciliation") or {}
    already_marked = (
        document.status == "FAILED"
        and previous.get("state") == MISSING_OBJECT_STATE
    )
    metadata["storage_reconciliation"] = {
        "state": MISSING_OBJECT_STATE,
        "detected_at": previous.get("detected_at") or _utcnow_iso(),
        "note": MISSING_OBJECT_NOTE,
    }
    document.metadata_json = metadata
    if document.status not in ("DELETED", "CANCELLED"):
        document.status = "FAILED"
    return not already_marked


async def _scan_tenant(
    session: AsyncSession,
    storage: StorageProvider,
    tenant_id: uuid.UUID,
    batch_size: int,
    report: dict[str, Any],
) -> dict[str, Any]:
    """Collect document and object state for one tenant without mutating anything."""
    tenant_report: dict[str, Any] = {
        "tenant_id": str(tenant_id),
        "object_listing": "supported",
        "inventory_status": INVENTORY_COMPLETE,
        "inventory_complete": True,
        "orphan_inventory_verified": False,
        "documents_checked": 0,
        "missing_objects_count": 0,
        "unresolved_documents_count": 0,
        "unresolved_documents": [],
        "orphan_objects_count": 0,
        "orphan_objects_deleted": 0,
        "errors": [],
    }
    missing_documents: list[dict[str, str]] = []

    # Collect every referenced path before listing objects so a referenced
    # object can never be classified as an orphan because of batching.
    referenced_result = await session.execute(
        select(Document.file_path).where(Document.tenant_id == tenant_id)
    )
    referenced_paths = {
        path for path in referenced_result.scalars().all() if path
    }

    offset = 0
    while True:
        doc_result = await session.execute(
            select(Document)
            .where(Document.tenant_id == tenant_id)
            .order_by(Document.created_at.asc(), Document.id.asc())
            .limit(batch_size)
            .offset(offset)
        )
        documents: Sequence[Document] = doc_result.scalars().all()
        if not documents:
            break

        for document in documents:
            tenant_report["documents_checked"] += 1
            report["documents_checked"] += 1
            try:
                exists = await storage.exists(str(tenant_id), document.file_path)
            except StorageNotFoundError:
                # A provider may surface a typed not-found instead of returning
                # False. That is still a definitive "object absent" answer.
                exists = False
            except Exception as exc:
                tenant_report["inventory_complete"] = False
                tenant_report["inventory_status"] = INVENTORY_INCOMPLETE
                tenant_report["unresolved_documents_count"] += 1
                tenant_report["errors"].append(
                    {
                        "scope": "document_exists",
                        "document_id": str(document.id),
                        "error": type(exc).__name__,
                    }
                )
                if len(tenant_report["unresolved_documents"]) < MAX_REPORTED_ITEMS:
                    tenant_report["unresolved_documents"].append(
                        {
                            "document_id": str(document.id),
                            "error": type(exc).__name__,
                        }
                    )
                continue

            if exists:
                continue

            tenant_report["missing_objects_count"] += 1
            report["missing_objects_count"] += 1
            missing_documents.append(
                {
                    "document_id": str(document.id),
                    "file_path": document.file_path,
                }
            )
            if len(report["missing_objects"]) < MAX_REPORTED_ITEMS:
                report["missing_objects"].append(
                    {
                        "tenant_id": str(tenant_id),
                        "document_id": str(document.id),
                        "file_path": document.file_path,
                    }
                )

        if len(documents) < batch_size:
            break
        offset += batch_size

    try:
        object_keys = await storage.list_keys(str(tenant_id))
    except NotImplementedError:
        # Missing a listing capability is not the same as an empty bucket.
        object_keys = None
        tenant_report["object_listing"] = "unsupported"
        tenant_report["inventory_complete"] = False
        tenant_report["inventory_status"] = INVENTORY_INCOMPLETE
        tenant_report["errors"].append(
            {"scope": "object_listing", "error": "NotImplementedError"}
        )
    except StorageError:
        # Authentication, authorization, network, throttling, and other
        # provider failures abort the whole run before any mutation.
        raise
    except Exception as exc:
        raise StorageError(
            f"Storage inventory listing failed for tenant {tenant_id} "
            f"({type(exc).__name__}); reconciliation aborted without changes."
        ) from exc

    orphan_keys: list[str] = []
    if object_keys is not None:
        tenant_prefix = f"tenants/{tenant_id}/"
        orphan_keys = [
            key
            for key in object_keys
            if key and key.startswith(tenant_prefix) and key not in referenced_paths
        ]
        tenant_report["orphan_inventory_verified"] = bool(
            tenant_report["inventory_complete"]
        )

    tenant_report["orphan_objects_count"] = len(orphan_keys)
    report["orphan_objects_count"] += len(orphan_keys)

    for key in orphan_keys:
        if len(report["orphan_objects"]) < MAX_REPORTED_ITEMS:
            report["orphan_objects"].append(
                {"tenant_id": str(tenant_id), "key": key}
            )

    report["errors"].extend(tenant_report["errors"])
    report["tenant_results"].append(tenant_report)
    return {
        "tenant_id": tenant_id,
        "report": tenant_report,
        "missing_documents": missing_documents,
        "orphan_keys": orphan_keys,
    }


async def _apply_missing_documents(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    missing_documents: list[dict[str, str]],
    report: dict[str, Any],
) -> None:
    document_ids = [uuid.UUID(item["document_id"]) for item in missing_documents]
    for start in range(0, len(document_ids), DEFAULT_BATCH_SIZE):
        chunk = document_ids[start:start + DEFAULT_BATCH_SIZE]
        result = await session.execute(
            select(Document).where(
                Document.tenant_id == tenant_id,
                Document.id.in_(chunk),
            )
        )
        for document in result.scalars().all():
            changed = await _mark_document_failed(document)
            if changed:
                report["fixed"]["documents_marked_failed"] += 1


def _orphan_cleanup_state(
    fix: bool, delete_orphans: bool, all_inventory_complete: bool
) -> dict[str, Any]:
    if not delete_orphans:
        return {"requested": False, "performed": False, "skipped_reason": None}
    if not fix:
        return {"requested": True, "performed": False, "skipped_reason": "dry_run"}
    if not all_inventory_complete:
        return {
            "requested": True,
            "performed": False,
            "skipped_reason": "inventory_incomplete",
        }
    return {"requested": True, "performed": True, "skipped_reason": None}


async def reconcile_storage(
    session: AsyncSession,
    storage: StorageProvider,
    tenant_id: uuid.UUID | str | None = None,
    fix: bool = False,
    delete_orphans: bool = False,
    batch_size: int = DEFAULT_BATCH_SIZE,
    allow_incomplete_inventory: bool = False,
) -> dict[str, Any]:
    """Compare documents against stored objects for one tenant or all tenants.

    - Dry-run (the default) only reads. It never mutates rows or objects.
    - Missing objects are reported. With ``fix=True`` and a complete per-object
      inventory, the owning document is marked FAILED with a sanitized note in
      ``metadata_json``. DB rows are never deleted by this operation.
    - Objects with no DB reference are reported. They are deleted only when
      ``fix=True``, ``delete_orphans=True``, and the storage inventory is
      verified complete, and only under the tenant prefix being scanned.
    - Per-object storage errors make the inventory incomplete. ``fix`` then
      refuses to run (returns ``fix_refused=True`` with no mutations) unless
      ``allow_incomplete_inventory=True``; even then, only objects with a
      definitive "absent" answer are marked, and orphan deletion is skipped.
    - A failed object listing aborts the run before any mutation.
    """
    effective_batch_size = max(1, int(batch_size))
    scope = str(tenant_id) if tenant_id is not None else None
    tenant_ids = await _resolve_tenant_ids(session, tenant_id)

    report: dict[str, Any] = {
        "generated_at": _utcnow_iso(),
        "tenant_scope": scope,
        "dry_run": not fix,
        "fix": bool(fix),
        "delete_orphans": bool(delete_orphans),
        "allow_incomplete_inventory": bool(allow_incomplete_inventory),
        "tenants_scanned": len(tenant_ids),
        "inventory_complete": True,
        "inventory_status": INVENTORY_COMPLETE,
        "fix_refused": False,
        "refusal_reason": None,
        "documents_checked": 0,
        "missing_objects_count": 0,
        "orphan_objects_count": 0,
        "missing_objects": [],
        "orphan_objects": [],
        "orphan_inventory_verified": False,
        "orphan_cleanup": _orphan_cleanup_state(
            fix=bool(fix),
            delete_orphans=bool(delete_orphans),
            all_inventory_complete=True,
        ),
        "fixed": {
            "documents_marked_failed": 0,
            "orphan_objects_deleted": 0,
        },
        "tenant_results": [],
        "errors": [],
    }

    # Phase 1: inventory every tenant before mutating anything. If a listing
    # fails anywhere, the exception propagates while the database is untouched.
    inventories: list[dict[str, Any]] = []
    for current_tenant_id in tenant_ids:
        inventories.append(
            await _scan_tenant(
                session,
                storage,
                current_tenant_id,
                effective_batch_size,
                report,
            )
        )

    all_inventory_complete = all(
        inventory["report"]["inventory_complete"] for inventory in inventories
    )
    report["inventory_complete"] = all_inventory_complete
    report["inventory_status"] = (
        INVENTORY_COMPLETE if all_inventory_complete else INVENTORY_INCOMPLETE
    )
    report["orphan_inventory_verified"] = all(
        inventory["report"]["orphan_inventory_verified"] for inventory in inventories
    )
    report["orphan_cleanup"] = _orphan_cleanup_state(
        fix=bool(fix),
        delete_orphans=bool(delete_orphans),
        all_inventory_complete=all_inventory_complete,
    )

    if fix and not allow_incomplete_inventory and not all_inventory_complete:
        report["fix_refused"] = True
        report["refusal_reason"] = "inventory_incomplete"
        logger.warning(
            "Storage reconciliation refused: tenant_scope=%s inventory incomplete",
            scope,
        )
        return report

    if not fix:
        logger.info(
            "Storage reconciliation complete: tenant_scope=%s fix=False delete_orphans=%s "
            "documents_checked=%s missing=%s orphans=%s inventory_complete=%s",
            scope,
            delete_orphans,
            report["documents_checked"],
            report["missing_objects_count"],
            report["orphan_objects_count"],
            all_inventory_complete,
        )
        return report

    # Phase 2: apply fixes only from definitive results.
    for inventory in inventories:
        await _apply_missing_documents(
            session,
            inventory["tenant_id"],
            inventory["missing_documents"],
            report,
        )

    if delete_orphans and all_inventory_complete:
        deletion_budget = MAX_ORPHAN_DELETIONS_PER_RUN
        for inventory in inventories:
            tenant_report = inventory["report"]
            for key in inventory["orphan_keys"]:
                if deletion_budget <= 0:
                    break
                try:
                    deleted = await storage.delete(
                        str(inventory["tenant_id"]), key
                    )
                except Exception as exc:
                    tenant_report["errors"].append(
                        {
                            "scope": "orphan_delete",
                            "key": key,
                            "error": type(exc).__name__,
                        }
                    )
                    report["errors"].append(tenant_report["errors"][-1])
                    continue
                if deleted:
                    tenant_report["orphan_objects_deleted"] += 1
                    report["fixed"]["orphan_objects_deleted"] += 1
                deletion_budget -= 1

    try:
        await session.commit()
    except Exception:
        await session.rollback()
        raise

    logger.info(
        "Storage reconciliation complete: tenant_scope=%s fix=%s delete_orphans=%s "
        "documents_checked=%s missing=%s orphans=%s inventory_complete=%s",
        scope,
        fix,
        delete_orphans,
        report["documents_checked"],
        report["missing_objects_count"],
        report["orphan_objects_count"],
        all_inventory_complete,
    )
    return report
