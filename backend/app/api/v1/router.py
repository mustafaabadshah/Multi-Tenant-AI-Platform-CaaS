from fastapi import APIRouter

from app.api.v1.assistants import router as assistant_router
from app.api.v1.audit import router as audit_router
from app.api.v1.auth import router as auth_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.departments import router as departments_router
from app.api.v1.documents import router as documents_router
from app.api.v1.embedding_providers import router as embedding_providers_router
from app.api.v1.groups import router as groups_router
from app.api.v1.ingestion import router as ingestion_router
from app.api.v1.knowledge import router as knowledge_router
from app.api.v1.members import router as members_router
from app.api.v1.organizations import router as organizations_router
from app.api.v1.providers import router as providers_router
from app.api.v1.retrieval import router as retrieval_router
from app.api.v1.roles import router as roles_router
from app.api.v1.templates import router as templates_router
from app.api.v1.tenants import router as tenants_router
from app.api.v1.vector_stores import router as vector_stores_router

from app.api.v1.developer import router as developer_router
from app.api.v1.public_chat import router as public_chat_router
from app.api.v1.publishing import router as publishing_router

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(auth_router)
api_v1_router.include_router(tenants_router)
api_v1_router.include_router(organizations_router)
api_v1_router.include_router(members_router)
api_v1_router.include_router(departments_router)
api_v1_router.include_router(groups_router)
api_v1_router.include_router(roles_router)
api_v1_router.include_router(templates_router)
api_v1_router.include_router(assistant_router)
api_v1_router.include_router(publishing_router)
api_v1_router.include_router(developer_router)
api_v1_router.include_router(public_chat_router)
api_v1_router.include_router(conversations_router)
api_v1_router.include_router(knowledge_router)
api_v1_router.include_router(documents_router)
api_v1_router.include_router(ingestion_router)
api_v1_router.include_router(retrieval_router)
api_v1_router.include_router(embedding_providers_router)
api_v1_router.include_router(vector_stores_router)
api_v1_router.include_router(providers_router)
api_v1_router.include_router(audit_router)


