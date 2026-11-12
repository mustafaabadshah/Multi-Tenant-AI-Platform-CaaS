"""Tenant-scoped reconciliation between database documents and object storage.

The service is read-only by default. ``fix=True`` only mutates state when the
caller asks for it, and orphan objects are deleted only when both ``fix`` and
``delete_orphans`` are true. It never performs an unscoped delete.
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
from app.storage.base import StorageProvider

logger = logging.getLogger("mmaip.storage.reconciliation")

DEFAULT_BATCH_SIZE = 500
MAX_REPORTED_ITEMS = 1000
MAX_ORPHAN_DELETIONS_PER_RUN = 1000
MISSING_OBJECT_STATE = "OBJECT_MISSING"
MISSING_OBJECT_NOTE = "Stored object is missing; document marked FAILED by reconciliation."


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


async def reconcile_storage(
    session: AsyncSession,
    storage: StorageProvider,
    tenant_id: uuid.UUID | str | None = None,
    fix: bool = False,
    delete_orphans: bool = False,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> dict[str, Any]:
    """Compare documents against stored objects for one tenant or all tenants.

    - Missing objects are reported and, with ``fix=True``, the owning document
      is marked FAILED with a sanitized note in ``metadata_json``. DB rows are
      never deleted by this operation.
    - Objects with no DB reference are reported. They are deleted only when
      both ``fix=True`` and ``delete_orphans=True`` are supplied, and only
      under the tenant prefix being scanned.
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
        "tenants_scanned": len(tenant_ids),
        "documents_checked": 0,
        "missing_objects_count": 0,
        "orphan_objects_count": 0,
        "missing_objects": [],
        "orphan_objects": [],
        "fixed": {
            "documents_marked_failed": 0,
            "orphan_objects_deleted": 0,
        },
        "tenant_results": [],
        "errors": [],
    }

    for current_tenant_id in tenant_ids:
        tenant_report: dict[str, Any] = {
            "tenant_id": str(current_tenant_id),
            "object_listing": "supported",
            "documents_checked": 0,
            "missing_objects_count": 0,
            "orphan_objects_count": 0,
            "orphan_objects_deleted": 0,
            "errors": [],
        }

        # Collect every referenced path before listing objects so a referenced
        # object can never be classified as an orphan because of batching.
        referenced_result = await session.execute(
            select(Document.file_path).where(Document.tenant_id == current_tenant_id)
        )
        referenced_paths = {
            path for path in referenced_result.scalars().all() if path
        }

        offset = 0
        while True:
            doc_result = await session.execute(
                select(Document)
                .where(Document.tenant_id == current_tenant_id)
                .order_by(Document.created_at.asc(), Document.id.asc())
                .limit(effective_batch_size)
                .offset(offset)
            )
            documents: Sequence[Document] = doc_result.scalars().all()
            if not documents:
                break

            for document in documents:
                tenant_report["documents_checked"] += 1
                report["documents_checked"] += 1
                try:
                    exists = await storage.exists(
                        str(current_tenant_id), document.file_path
                    )
                except Exception as exc:
                    tenant_report["errors"].append(
                        {
                            "scope": "document_exists",
                            "document_id": str(document.id),
                            "error": type(exc).__name__,
                        }
                    )
                    continue

                if exists:
                    continue

                tenant_report["missing_objects_count"] += 1
                report["missing_objects_count"] += 1
                if len(report["missing_objects"]) < MAX_REPORTED_ITEMS:
                    report["missing_objects"].append(
                        {
                            "tenant_id": str(current_tenant_id),
                            "document_id": str(document.id),
                            "file_path": document.file_path,
                        }
                    )
                if fix:
                    changed = await _mark_document_failed(document)
                    if changed:
                        report["fixed"]["documents_marked_failed"] += 1

            if len(documents) < effective_batch_size:
                break
            offset += effective_batch_size

        try:
            object_keys = await storage.list_keys(str(current_tenant_id))
        except NotImplementedError:
            object_keys = []
            tenant_report["object_listing"] = "unsupported"
            tenant_report["errors"].append(
                {"scope": "object_listing", "error": "NotImplementedError"}
            )
        except Exception as exc:
            object_keys = []
            tenant_report["object_listing"] = "error"
            tenant_report["errors"].append(
                {"scope": "object_listing", "error": type(exc).__name__}
            )

        tenant_prefix = f"tenants/{current_tenant_id}/"
        orphan_keys = [
            key
            for key in object_keys
            if key and key.startswith(tenant_prefix) and key not in referenced_paths
        ]
        tenant_report["orphan_objects_count"] = len(orphan_keys)
        report["orphan_objects_count"] += len(orphan_keys)

        for key in orphan_keys:
            if len(report["orphan_objects"]) < MAX_REPORTED_ITEMS:
                report["orphan_objects"].append(
                    {"tenant_id": str(current_tenant_id), "key": key}
                )

        if fix and delete_orphans:
            deletion_budget = MAX_ORPHAN_DELETIONS_PER_RUN
            for key in orphan_keys:
                if deletion_budget <= 0:
                    break
                try:
                    deleted = await storage.delete(str(current_tenant_id), key)
                except Exception as exc:
                    tenant_report["errors"].append(
                        {
                            "scope": "orphan_delete",
                            "key": key,
                            "error": type(exc).__name__,
                        }
                    )
                    continue
                if deleted:
                    tenant_report["orphan_objects_deleted"] += 1
                    report["fixed"]["orphan_objects_deleted"] += 1
                deletion_budget -= 1

        report["errors"].extend(tenant_report["errors"])
        report["tenant_results"].append(tenant_report)

    if fix:
        try:
            await session.commit()
        except Exception:
            await session.rollback()
            raise

    logger.info(
        "Storage reconciliation complete: tenant_scope=%s fix=%s delete_orphans=%s "
        "documents_checked=%s missing=%s orphans=%s",
        scope,
        fix,
        delete_orphans,
        report["documents_checked"],
        report["missing_objects_count"],
        report["orphan_objects_count"],
    )
    return report
