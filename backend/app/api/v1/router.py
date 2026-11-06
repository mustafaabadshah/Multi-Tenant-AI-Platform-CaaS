from fastapi import APIRouter

from app.api.v1.assistants import router as assistant_router
from app.api.v1.audit import router as audit_router
from app.api.v1.auth import router as auth_router
from app.api.v1.departments import router as departments_router
from app.api.v1.documents import router as documents_router
from app.api.v1.groups import router as groups_router
from app.api.v1.ingestion import router as ingestion_router
from app.api.v1.knowledge import router as knowledge_router
from app.api.v1.members import router as members_router
from app.api.v1.organizations import router as organizations_router
from app.api.v1.roles import router as roles_router
from app.api.v1.tenants import router as tenants_router

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(auth_router)
api_v1_router.include_router(tenants_router)
api_v1_router.include_router(organizations_router)
api_v1_router.include_router(members_router)
api_v1_router.include_router(departments_router)
api_v1_router.include_router(groups_router)
api_v1_router.include_router(roles_router)
api_v1_router.include_router(assistant_router)
api_v1_router.include_router(knowledge_router)
api_v1_router.include_router(documents_router)
api_v1_router.include_router(ingestion_router)
api_v1_router.include_router(audit_router)
