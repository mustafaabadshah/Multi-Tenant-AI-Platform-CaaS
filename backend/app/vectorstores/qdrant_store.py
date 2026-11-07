"""Qdrant vector database adapter with strict tenant payload filtering and collection management."""

import logging
import uuid
from typing import Any, Optional

from app.core.config import settings
from app.vectorstores.base import (
    VectorPoint,
    VectorSearchResult,
    VectorStore,
    VectorStoreFilter,
)

logger = logging.getLogger("mmaip.vectorstores.qdrant")

try:
    from qdrant_client import AsyncQdrantClient
    from qdrant_client.http import models as qmodels
    HAVE_QDRANT = True
except ImportError:
    HAVE_QDRANT = False


class QdrantVectorStore(VectorStore):
    """Qdrant adapter enforcing multi-tenant isolation via mandatory filter conditions on all queries."""

    def __init__(
        self,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        collection_name: str = "mmaip_knowledge_chunks",
    ):
        self.url = url or settings.QDRANT_URL
        self.api_key = api_key or settings.QDRANT_API_KEY
        self.collection_name = collection_name
        self._client: Optional[Any] = None

    @property
    def store_name(self) -> str:
        return "qdrant"

    def _get_client(self) -> Any:
        if not HAVE_QDRANT:
            raise RuntimeError("qdrant-client is not installed.")
        if self._client is None:
            self._client = AsyncQdrantClient(url=self.url, api_key=self.api_key, timeout=10)
        return self._client

    def _collection_for_dim(self, dims: int) -> str:
        """Isolate vector spaces by dimensionality to prevent dimension mismatch collisions."""
        return f"{self.collection_name}_{dims}"

    async def _ensure_collection(self, dimensions: int) -> str:
        client = self._get_client()
        col_name = self._collection_for_dim(dimensions)
        collections = await client.get_collections()
        exists = any(c.name == col_name for c in collections.collections)
        if not exists:
            logger.info(f"Creating Qdrant collection '{col_name}' with {dimensions} dimensions")
            await client.create_collection(
                collection_name=col_name,
                vectors_config=qmodels.VectorParams(
                    size=dimensions,
                    distance=qmodels.Distance.COSINE,
                ),
            )
            # Create payload indices for fast tenant & KB lookups
            for field_name, schema_type in [
                ("tenant_id", qmodels.PayloadSchemaType.KEYWORD),
                ("knowledge_base_id", qmodels.PayloadSchemaType.KEYWORD),
                ("embedding_version", qmodels.PayloadSchemaType.INTEGER),
            ]:
                await client.create_payload_index(
                    collection_name=col_name,
                    field_name=field_name,
                    field_schema=schema_type,
                )
        return col_name

    async def upsert(
        self,
        points: list[VectorPoint],
        tenant_id: uuid.UUID,
        knowledge_base_id: uuid.UUID,
    ) -> int:
        if not points:
            return 0
        client = self._get_client()
        dims = len(points[0].vector)
        for p in points:
            if len(p.vector) != dims:
                raise ValueError(
                    f"Inconsistent vector dimensions in batch: expected {dims}, got {len(p.vector)}"
                )
        col_name = await self._ensure_collection(dims)

        qpoints = []
        for p in points:
            # Ensure tenant_id and knowledge_base_id are always strictly enforced in payload
            payload = dict(p.payload)
            payload["tenant_id"] = str(tenant_id)
            payload["knowledge_base_id"] = str(knowledge_base_id)
            if "chunk_id" not in payload:
                payload["chunk_id"] = str(p.id)

            qpoints.append(
                qmodels.PointStruct(
                    id=str(p.id),
                    vector=p.vector,
                    payload=payload,
                )
            )

        await client.upsert(collection_name=col_name, points=qpoints)
        return len(qpoints)

    async def search(
        self,
        query_vector: list[float],
        filter_criteria: VectorStoreFilter,
        top_k: int = 8,
    ) -> list[VectorSearchResult]:
        client = self._get_client()
        dims = len(query_vector)
        if filter_criteria.expected_dimensions and filter_criteria.expected_dimensions != dims:
            raise ValueError(
                f"Query vector dimension mismatch: expected {filter_criteria.expected_dimensions}, got {dims}"
            )

        col_name = self._collection_for_dim(dims)
        try:
            collections = await client.get_collections()
            if not any(c.name == col_name for c in collections.collections):
                return []
        except Exception as e:
            logger.warning(f"Failed to check Qdrant collections: {e}")
            return []

        # Build strict tenant and knowledge base filters
        must_conditions: list[Any] = [
            qmodels.FieldCondition(
                key="tenant_id",
                match=qmodels.MatchValue(value=str(filter_criteria.tenant_id)),
            ),
            qmodels.FieldCondition(
                key="embedding_version",
                match=qmodels.MatchValue(value=filter_criteria.embedding_version),
            ),
        ]

        if len(filter_criteria.knowledge_base_ids) == 1:
            must_conditions.append(
                qmodels.FieldCondition(
                    key="knowledge_base_id",
                    match=qmodels.MatchValue(value=str(filter_criteria.knowledge_base_ids[0])),
                )
            )
        else:
            must_conditions.append(
                qmodels.FieldCondition(
                    key="knowledge_base_id",
                    match=qmodels.MatchAny(any=[str(k) for k in filter_criteria.knowledge_base_ids]),
                )
            )

        if filter_criteria.document_ids:
            must_conditions.append(
                qmodels.FieldCondition(
                    key="document_id",
                    match=qmodels.MatchAny(any=[str(d) for d in filter_criteria.document_ids]),
                )
            )

        query_filter = qmodels.Filter(must=must_conditions)

        # Execute filtered nearest neighbor search
        scored_points = await client.search(
            collection_name=col_name,
            query_vector=query_vector,
            query_filter=query_filter,
            limit=top_k,
        )

        results: list[VectorSearchResult] = []
        for rank, sp in enumerate(scored_points, start=1):
            p = sp.payload or {}
            # Department access check if restricted
            dept_id = p.get("department_id")
            if not filter_criteria.is_admin and filter_criteria.user_department_id:
                if dept_id and dept_id != str(filter_criteria.user_department_id):
                    continue

            results.append(
                VectorSearchResult(
                    chunk_id=uuid.UUID(str(p.get("chunk_id", sp.id))),
                    document_id=uuid.UUID(str(p.get("document_id"))),
                    knowledge_base_id=uuid.UUID(str(p.get("knowledge_base_id"))),
                    score=float(sp.score),
                    content=str(p.get("content", "")),
                    metadata=p,
                    rank=rank,
                    document_title=p.get("document_title"),
                    page_number=p.get("page_number"),
                    heading_path=p.get("heading_path"),
                    chunk_index=int(p.get("chunk_index", 0)),
                    retrieval_source="semantic",
                )
            )

        return results

    async def delete(self, chunk_ids: list[uuid.UUID], tenant_id: uuid.UUID) -> int:
        client = self._get_client()
        # Delete only where chunk_id matches AND tenant_id matches
        filter_selector = qmodels.FilterSelector(
            filter=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="tenant_id",
                        match=qmodels.MatchValue(value=str(tenant_id)),
                    ),
                    qmodels.HasIdCondition(has_id=[str(cid) for cid in chunk_ids]),
                ]
            )
        )
        try:
            collections = await client.get_collections()
            matching_cols = [c.name for c in collections.collections if c.name.startswith(self.collection_name)]
            for col in matching_cols:
                await client.delete(collection_name=col, points_selector=filter_selector)
        except Exception as e:
            logger.warning(f"Error deleting chunks from Qdrant: {e}")
        return len(chunk_ids)

    async def delete_document(self, document_id: uuid.UUID, tenant_id: uuid.UUID) -> int:
        client = self._get_client()
        filter_selector = qmodels.FilterSelector(
            filter=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="tenant_id",
                        match=qmodels.MatchValue(value=str(tenant_id)),
                    ),
                    qmodels.FieldCondition(
                        key="document_id",
                        match=qmodels.MatchValue(value=str(document_id)),
                    ),
                ]
            )
        )
        try:
            collections = await client.get_collections()
            matching_cols = [c.name for c in collections.collections if c.name.startswith(self.collection_name)]
            for col in matching_cols:
                await client.delete(collection_name=col, points_selector=filter_selector)
        except Exception as e:
            logger.warning(f"Error deleting document from Qdrant: {e}")
        return 1

    async def check_health(self) -> dict[str, Any]:
        if not HAVE_QDRANT:
            return {"status": "unhealthy", "store": "qdrant", "error": "qdrant-client not installed"}
        try:
            client = self._get_client()
            cols = await client.get_collections()
            return {
                "status": "healthy",
                "store": "qdrant",
                "endpoint": self.url,
                "collection_count": len(cols.collections),
            }
        except Exception as err:
            return {
                "status": "unhealthy",
                "store": "qdrant",
                "endpoint": self.url,
                "error": str(err),
            }
