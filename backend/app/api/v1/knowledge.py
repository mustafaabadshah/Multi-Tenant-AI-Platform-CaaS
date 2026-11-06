import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, get_current_user, require_permission
from app.core.constants import PermissionName
from app.database.session import get_db
from app.models.user import User
from app.repositories.audit_repository import AuditLogRepository
from app.repositories.knowledge_repository import KnowledgeRepository
from app.schemas.knowledge import KnowledgeBaseCreateRequest, KnowledgeBaseResponse

router = APIRouter(prefix="/knowledge", tags=["Knowledge Base Foundation"])


@router.get("", response_model=list[KnowledgeBaseResponse])
async def list_knowledge_bases(
    ctx: TenantContext = Depends(require_permission(PermissionName.KNOWLEDGE_READ.value)),
    db: AsyncSession = Depends(get_db),
) -> list[KnowledgeBaseResponse]:
    repo = KnowledgeRepository(db, ctx.tenant.id)
    items = await repo.list_with_counts()

    return [
        KnowledgeBaseResponse(
            id=kb.id,
            tenant_id=kb.tenant_id,
            name=kb.name,
            description=kb.description,
            status=kb.status,
            document_count=doc_count,
            created_at=kb.created_at,
            updated_at=kb.updated_at,
        )
        for kb, doc_count in items
    ]


@router.post("", response_model=KnowledgeBaseResponse, status_code=status.HTTP_201_CREATED)
async def create_knowledge_base(
    payload: KnowledgeBaseCreateRequest,
    ctx: TenantContext = Depends(require_permission(PermissionName.KNOWLEDGE_CREATE.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeBaseResponse:
    repo = KnowledgeRepository(db, ctx.tenant.id)
    kb = await repo.create(
        name=payload.name.strip(),
        description=payload.description,
        status="ACTIVE",
    )

    audit_repo = AuditLogRepository(db, ctx.tenant.id)
    await audit_repo.log_event(
        action="knowledge.create",
        resource_type="knowledge_base",
        resource_id=kb.id,
        actor_id=current_user.id,
        details={"name": kb.name},
    )

    return KnowledgeBaseResponse(
        id=kb.id,
        tenant_id=kb.tenant_id,
        name=kb.name,
        description=kb.description,
        status=kb.status,
        document_count=0,
        created_at=kb.created_at,
        updated_at=kb.updated_at,
    )


@router.get("/{kb_id}", response_model=KnowledgeBaseResponse)
async def get_knowledge_base(
    kb_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.KNOWLEDGE_READ.value)),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeBaseResponse:
    repo = KnowledgeRepository(db, ctx.tenant.id)
    kb = await repo.get_by_id(kb_id)
    if not kb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found in active workspace",
        )

    return KnowledgeBaseResponse(
        id=kb.id,
        tenant_id=kb.tenant_id,
        name=kb.name,
        description=kb.description,
        status=kb.status,
        document_count=0,
        created_at=kb.created_at,
        updated_at=kb.updated_at,
    )


@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_base(
    kb_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.KNOWLEDGE_DELETE.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    repo = KnowledgeRepository(db, ctx.tenant.id)
    deleted = await repo.delete(kb_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found in active workspace",
        )

    audit_repo = AuditLogRepository(db, ctx.tenant.id)
    await audit_repo.log_event(
        action="knowledge.delete",
        resource_type="knowledge_base",
        resource_id=kb_id,
        actor_id=current_user.id,
    )
