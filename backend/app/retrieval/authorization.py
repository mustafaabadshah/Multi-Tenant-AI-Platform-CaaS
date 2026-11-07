"""Retrieval authorization and candidate filtering enforcing tenant, department, and document boundaries."""

import logging
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import Document, KnowledgeBase
from app.models.membership import TenantMembership
from app.vectorstores.base import VectorSearchResult

logger = logging.getLogger("mmaip.retrieval.authorization")


class RetrievalAuthorizer:
    """Security engine enforcing strict multi-tenant and department-level access control over search candidates."""

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID):
        self.session = session
        self.tenant_id = tenant_id

    async def get_user_department_and_role(
        self, user_id: uuid.UUID
    ) -> tuple[Optional[uuid.UUID], Optional[str]]:
        """Resolve user's active membership, role, and department within this tenant."""
        stmt = select(TenantMembership).where(
            TenantMembership.tenant_id == self.tenant_id,
            TenantMembership.user_id == user_id,
            TenantMembership.status == "ACTIVE",
        )
        membership = (await self.session.execute(stmt)).scalar_one_or_none()
        if not membership:
            return None, None
        return membership.department_id, None

    async def validate_knowledge_bases(
        self,
        kb_ids: list[uuid.UUID],
        user_department_id: Optional[uuid.UUID],
        is_admin: bool,
    ) -> list[KnowledgeBase]:
        """Validate that all requested knowledge bases belong strictly to this tenant and are accessible."""
        stmt = select(KnowledgeBase).where(
            KnowledgeBase.tenant_id == self.tenant_id,
            KnowledgeBase.id.in_(kb_ids),
            KnowledgeBase.status == "ACTIVE",
        )
        kbs = (await self.session.execute(stmt)).scalars().all()
        if len(kbs) != len(kb_ids):
            found_ids = {k.id for k in kbs}
            missing = set(kb_ids) - found_ids
            raise PermissionError(f"Unauthorized or non-existent knowledge bases: {missing}")

        # Enforce department restriction on knowledge bases
        if not is_admin and user_department_id:
            for kb in kbs:
                if kb.department_id and kb.department_id != user_department_id:
                    raise PermissionError(
                        f"Access denied to Knowledge Base '{kb.name}'. Belongs to another department."
                    )

        return list(kbs)

    async def filter_authorized_candidates(
        self,
        candidates: list[VectorSearchResult],
        user_department_id: Optional[uuid.UUID],
        is_admin: bool,
    ) -> list[VectorSearchResult]:
        """Authoritative secondary defense: verify all candidates against authoritative DB records.

        Discards deleted documents, superseded versions, and unauthorized department documents.
        """
        if not candidates:
            return []

        doc_ids = list({c.document_id for c in candidates})
        stmt = select(Document).where(
            Document.tenant_id == self.tenant_id,
            Document.id.in_(doc_ids),
        )
        docs = (await self.session.execute(stmt)).scalars().all()
        doc_map = {d.id: d for d in docs}

        authorized: list[VectorSearchResult] = []
        for c in candidates:
            doc = doc_map.get(c.document_id)
            if not doc:
                logger.warning(f"Candidate {c.chunk_id} rejected: document {c.document_id} not found in tenant {self.tenant_id}")
                continue

            # 1. Filter out deleted documents
            if doc.status == "DELETED":
                logger.debug(f"Candidate {c.chunk_id} rejected: document is DELETED")
                continue

            # 2. Filter out unauthorized department documents
            if not is_admin and user_department_id:
                if doc.department_id and doc.department_id != user_department_id:
                    logger.debug(f"Candidate {c.chunk_id} rejected: department mismatch")
                    continue

            # 3. Restricted access check
            if doc.access_level == "restricted" and not is_admin:
                continue

            authorized.append(c)

        # Re-number ranks 1..N
        for idx, item in enumerate(authorized, start=1):
            item.rank = idx

        return authorized
