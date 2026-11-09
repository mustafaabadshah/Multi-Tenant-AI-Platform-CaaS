"""Retrieval search and preview endpoints with strict multi-tenant authorization."""


from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, get_current_user, get_db, require_permission
from app.core.constants import PermissionName
from app.models.user import User
from app.retrieval.service import RetrievalService, SearchResponse
from app.schemas.provider import (
    PlaygroundChunkResult,
    PlaygroundSearchRequest,
    PlaygroundSearchResponse,
)
from app.schemas.retrieval import (
    CitationItem,
    SearchRequest,
    SearchResponseSchema,
    SearchResultChunk,
)

router = APIRouter(prefix="/retrieval", tags=["Retrieval"])


def _to_schema_response(resp: SearchResponse) -> SearchResponseSchema:
    return SearchResponseSchema(
        query=resp.query,
        retrieval_mode=resp.retrieval_mode,
        vector_store=resp.vector_store,
        embedding_provider=resp.embedding_provider,
        total_results=resp.total_results,
        results=[
            SearchResultChunk(
                chunk_id=r.chunk_id,
                document_id=r.document_id,
                knowledge_base_id=r.knowledge_base_id,
                score=r.score,
                rank=r.rank,
                content=r.content,
                document_title=r.document_title,
                page_number=r.page_number,
                heading_path=r.heading_path,
                chunk_index=r.chunk_index,
                retrieval_source=r.retrieval_source,
                metadata=r.metadata,
            )
            for r in resp.results
        ],
        citations=[
            CitationItem(
                citation_index=c.citation_index,
                label=c.label,
                chunk_id=c.chunk_id,
                document_id=c.document_id,
                document_title=c.document_title,
                page_number=c.page_number,
                heading_path=c.heading_path,
                chunk_index=c.chunk_index,
                snippet=c.snippet,
                retrieval_source=c.retrieval_source,
                score=c.score,
            )
            for c in resp.citations
        ],
        diagnostics=resp.diagnostics,
    )


@router.post(
    "/search",
    response_model=SearchResponseSchema,
)
async def search_knowledge(
    payload: SearchRequest,
    ctx: TenantContext = Depends(require_permission(PermissionName.RETRIEVAL_SEARCH.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Execute authenticated multi-tenant hybrid/semantic/lexical retrieval."""
    try:
        is_admin = ctx.role.name in ("tenant_owner", "org_admin", "platform_superadmin")
        service = RetrievalService(
            session=db,
            tenant_id=ctx.tenant.id,
            user_id=current_user.id,
            is_admin=is_admin,
            user_department_id=ctx.membership.department_id if ctx.membership else None,
        )

        resp = await service.search(
            query=payload.query,
            knowledge_base_ids=payload.knowledge_base_ids,
            mode=payload.mode,
            vector_store_type=payload.vector_store,
            top_k=payload.top_k,
            document_ids=payload.document_ids,
        )
        return _to_schema_response(resp)

    except PermissionError as pe:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(pe),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Retrieval error: {exc}",
        )


@router.post(
    "/preview",
    response_model=SearchResponseSchema,
)
async def preview_retrieval(
    payload: SearchRequest,
    ctx: TenantContext = Depends(require_permission(PermissionName.RETRIEVAL_PREVIEW.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run an interactive retrieval preview showing individual ranks, scores, and diagnostics."""
    return await search_knowledge(payload, ctx, current_user, db)


@router.post(
    "/playground",
    response_model=PlaygroundSearchResponse,
)
async def playground_search(
    payload: PlaygroundSearchRequest,
    ctx: TenantContext = Depends(require_permission(PermissionName.RETRIEVAL_SEARCH.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlaygroundSearchResponse:
    """Execute dedicated Retrieval Playground query returning ranking, latency, and truth-tested scores."""
    import time
    start_time = time.perf_counter()

    is_admin = ctx.role.name in ("tenant_owner", "org_admin", "platform_superadmin")
    service = RetrievalService(
        session=db,
        tenant_id=ctx.tenant.id,
        user_id=current_user.id,
        is_admin=is_admin,
        user_department_id=ctx.membership.department_id if ctx.membership else None,
    )

    try:
        resp = await service.search(
            query=payload.query,
            knowledge_base_ids=[payload.knowledge_base_id],
            mode=payload.mode,
            top_k=payload.top_k,
        )
    except (PermissionError, ValueError) as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(err),
        )

    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

    chunk_results = []
    for r in resp.results:
        # Resolve sparse vs dense score where available
        meta = r.metadata or {}
        sparse = meta.get("sparse_score")
        dense = meta.get("dense_score")
        chunk_results.append(
            PlaygroundChunkResult(
                chunk_id=r.chunk_id,
                document_id=r.document_id,
                document_title=r.document_title or "Untitled Document",
                rank=r.rank,
                sparse_score=float(sparse) if sparse is not None else None,
                dense_score=float(dense) if dense is not None else None,
                score=round(r.score, 4),
                retrieval_source=r.retrieval_source,
                content=r.content,
                page_number=r.page_number,
                heading_path=r.heading_path,
            )
        )

    return PlaygroundSearchResponse(
        query=payload.query,
        knowledge_base_id=payload.knowledge_base_id,
        retrieval_mode=payload.mode,
        vector_store=resp.vector_store,
        latency_ms=elapsed_ms,
        total_results=len(chunk_results),
        results=chunk_results,
    )


