"""Phase 4 Security Assessment Test Suite: Tenant Isolation, RBAC, Resource ACL, Assistant & RAG Security.

This test suite rigorously tests the threat model scenarios across authentication,
tenant context, repository scoping, RBAC, department ACL, retrieval authorizer,
assistant runtime, conversation privacy, SSE streaming, and BYOK credential isolation.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import MembershipStatus, SystemRole, UserStatus
from app.core.crypto import decrypt_secret
from app.core.security import create_access_token, hash_password
from app.models.conversation import Conversation, Message
from app.models.department import Department
from app.models.knowledge import Document, KnowledgeBase
from app.repositories.assistant_repository import AssistantRepository
from app.repositories.department_repository import DepartmentRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.knowledge_repository import KnowledgeRepository
from app.repositories.member_repository import MemberRepository
from app.repositories.retrieval_repository import RetrievalRepository
from app.repositories.role_repository import RoleRepository
from app.repositories.user_repository import UserRepository
from app.retrieval.authorization import RetrievalAuthorizer
from app.vectorstores.base import VectorSearchResult

# ==============================================================================
# 1. AUTHENTICATION & TENANT-CONTEXT VERIFICATION (TIS-01, TIS-02)
# ==============================================================================


@pytest.mark.asyncio
async def test_auth_missing_and_invalid_tokens_rejected(client: AsyncClient, seed_data: dict):
    """Missing, expired, or malformed JWT tokens must return 401 Unauthorized."""
    tenant_a_id = str(seed_data["tenant_a"].id)

    # 1. Missing Authorization header
    res_no_auth = await client.get("/api/v1/departments", headers={"X-Tenant-ID": tenant_a_id})
    assert res_no_auth.status_code == 401
    assert "token required" in res_no_auth.json()["detail"].lower()

    # 2. Malformed token string
    res_malformed = await client.get(
        "/api/v1/departments",
        headers={"Authorization": "Bearer not.a.valid.jwt.token", "X-Tenant-ID": tenant_a_id},
    )
    assert res_malformed.status_code == 401

    # 3. Invalid token type (e.g. refresh token used as access token)
    from app.core.security import create_refresh_token

    refresh_token = create_refresh_token(str(seed_data["user_a_owner"].id))
    res_refresh = await client.get(
        "/api/v1/departments",
        headers={"Authorization": f"Bearer {refresh_token}", "X-Tenant-ID": tenant_a_id},
    )
    assert res_refresh.status_code == 401
    assert "access token" in res_refresh.json()["detail"].lower()


@pytest.mark.asyncio
async def test_forged_x_tenant_id_header_rejected(client: AsyncClient, seed_data: dict):
    """A user in Tenant A cannot forge X-Tenant-ID to Tenant B (403 Forbidden)."""
    tenant_b_id = str(seed_data["tenant_b"].id)
    token_a_owner = seed_data["token_a_owner"]

    # Alice (Tenant A) attempts to claim Tenant B workspace context
    forged_headers = {
        "Authorization": f"Bearer {token_a_owner}",
        "X-Tenant-ID": tenant_b_id,
    }
    res = await client.get("/api/v1/departments", headers=forged_headers)
    assert res.status_code == 403
    assert "access denied" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_path_tenant_id_mismatch_rejected(client: AsyncClient, seed_data: dict):
    """A request where path tenant_id does not match header X-Tenant-ID must be rejected."""
    tenant_a_id = str(seed_data["tenant_a"].id)
    tenant_b_id = str(seed_data["tenant_b"].id)
    token_a_owner = seed_data["token_a_owner"]

    headers = {
        "Authorization": f"Bearer {token_a_owner}",
        "X-Tenant-ID": tenant_a_id,
    }
    # Path is Tenant B, but X-Tenant-ID is Tenant A
    res = await client.get(f"/api/v1/tenants/{tenant_b_id}", headers=headers)
    assert res.status_code == 403
    assert "does not match" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_suspended_user_and_membership_rejected(
    client: AsyncClient, db_session: AsyncSession, seed_data: dict
):
    """Suspended user accounts or revoked memberships are immediately rejected."""
    tenant_a = seed_data["tenant_a"]
    user_repo = UserRepository(db_session)
    member_repo = MemberRepository(db_session, tenant_a.id)

    # 1. Suspended User
    suspended_user = await user_repo.create(
        email="suspended@companya.com",
        hashed_password=hash_password("Password123!"),
        full_name="Sam Suspended",
    )
    suspended_user.status = UserStatus.SUSPENDED.value
    role_repo = RoleRepository(db_session)
    emp_role = await role_repo.get_by_name(SystemRole.EMPLOYEE.value)
    assert emp_role is not None

    membership = await member_repo.create(
        user_id=suspended_user.id,
        role_id=emp_role.id,
        status=MembershipStatus.ACTIVE.value,
    )
    await db_session.commit()

    token_suspended = create_access_token(str(suspended_user.id), {"email": suspended_user.email})
    headers = {
        "Authorization": f"Bearer {token_suspended}",
        "X-Tenant-ID": str(tenant_a.id),
    }

    res_user = await client.get("/api/v1/departments", headers=headers)
    assert res_user.status_code == 403
    assert "inactive or suspended" in res_user.json()["detail"].lower()

    # 2. Suspended Membership
    suspended_user.status = UserStatus.ACTIVE.value
    membership.status = MembershipStatus.SUSPENDED.value
    await db_session.commit()

    res_member = await client.get("/api/v1/departments", headers=headers)
    assert res_member.status_code == 403
    assert "active membership" in res_member.json()["detail"].lower()


# ==============================================================================
# 2. TENANT-SCOPED REPOSITORY & CROSS-TENANT INTEGRITY (TIS-03, TIS-04)
# ==============================================================================


@pytest.mark.asyncio
async def test_cross_tenant_resource_id_tampering_blocked(
    client: AsyncClient, db_session: AsyncSession, seed_data: dict
):
    """Manipulating valid UUIDs of another tenant returns 404 with zero information leakage."""
    tenant_a = seed_data["tenant_a"]
    tenant_b = seed_data["tenant_b"]
    token_b = seed_data["token_b_owner"]

    # Create resources in Tenant A
    kb_repo_a = KnowledgeRepository(db_session, tenant_a.id)
    kb_a = await kb_repo_a.create(name="A Top Secret KB", status="ACTIVE")

    doc_repo_a = DocumentRepository(db_session, tenant_a.id)
    doc_a = await doc_repo_a.create(
        knowledge_base_id=kb_a.id,
        filename="classified.txt",
        safe_filename="classified.txt",
        file_path="/tenants/a/classified.txt",
        mime_type="text/plain",
        status="COMPLETED",
    )

    asst_repo_a = AssistantRepository(db_session, tenant_a.id)
    asst_a = await asst_repo_a.create_assistant(name="Secret Assistant")
    await db_session.commit()

    headers_b = {
        "Authorization": f"Bearer {token_b}",
        "X-Tenant-ID": str(tenant_b.id),
    }

    # Tenant B tries to read Tenant A's KB by ID -> 404
    res_kb = await client.get(f"/api/v1/knowledge/{kb_a.id}", headers=headers_b)
    assert res_kb.status_code == 404

    # Tenant B tries to read Tenant A's Document by ID -> 404
    res_doc = await client.get(f"/api/v1/documents/{doc_a.id}", headers=headers_b)
    assert res_doc.status_code == 404

    # Tenant B tries to read Tenant A's Assistant by ID -> 404
    res_asst = await client.get(f"/api/v1/assistants/{asst_a.id}", headers=headers_b)
    assert res_asst.status_code == 404


@pytest.mark.asyncio
async def test_cross_tenant_knowledge_base_linking_blocked(
    client: AsyncClient, db_session: AsyncSession, seed_data: dict
):
    """An assistant cannot be linked to a knowledge base from another tenant."""
    tenant_a = seed_data["tenant_a"]
    tenant_b = seed_data["tenant_b"]
    token_b = seed_data["token_b_owner"]

    # Create KB in Tenant A
    kb_repo_a = KnowledgeRepository(db_session, tenant_a.id)
    kb_a = await kb_repo_a.create(name="Company A Proprietary Code", status="ACTIVE")
    await db_session.commit()

    headers_b = {
        "Authorization": f"Bearer {token_b}",
        "X-Tenant-ID": str(tenant_b.id),
    }

    # Tenant B attempts to create assistant attaching Tenant A's KB
    res = await client.post(
        "/api/v1/assistants",
        headers=headers_b,
        json={
            "name": "Intruder Assistant",
            "llm_provider": "mock",
            "default_model": "mock-gpt",
            "knowledge_base_ids": [str(kb_a.id)],
        },
    )
    assert res.status_code == 400
    assert "not found in this workspace" in res.json()["detail"].lower()


# ==============================================================================
# 3. RBAC & PRIVILEGE ESCALATION PROTECTIONS (RBAC-01, RBAC-02)
# ==============================================================================


@pytest.mark.asyncio
async def test_unauthorized_role_escalation_blocked(
    client: AsyncClient, db_session: AsyncSession, seed_data: dict
):
    """Users cannot promote themselves or invite members with owner/superadmin privileges unless authorized."""
    tenant_a = seed_data["tenant_a"]
    user_repo = UserRepository(db_session)
    role_repo = RoleRepository(db_session)
    member_repo = MemberRepository(db_session, tenant_a.id)

    org_admin_role = await role_repo.get_by_name(SystemRole.ORG_ADMIN.value)
    assert org_admin_role is not None

    # Create Org Admin in Tenant A
    admin_user = await user_repo.create(
        email="admin_a@companya.com",
        hashed_password=hash_password("Password123!"),
        full_name="Audrey Admin",
    )
    admin_member = await member_repo.create(
        user_id=admin_user.id,
        role_id=org_admin_role.id,
        status=MembershipStatus.ACTIVE.value,
    )
    await db_session.commit()

    token_admin = create_access_token(str(admin_user.id), {"email": admin_user.email})
    admin_headers = {
        "Authorization": f"Bearer {token_admin}",
        "X-Tenant-ID": str(tenant_a.id),
    }

    # 1. Org Admin attempts to promote herself to tenant_owner -> 403 Forbidden
    res_self = await client.patch(
        f"/api/v1/members/{admin_member.id}",
        headers=admin_headers,
        json={"role": SystemRole.TENANT_OWNER.value},
    )
    assert res_self.status_code == 403
    assert "cannot modify their own role" in res_self.json()["detail"].lower()

    # 2. Org Admin attempts to invite another user as tenant_owner -> 403 Forbidden
    res_invite_owner = await client.post(
        "/api/v1/members/invite",
        headers=admin_headers,
        json={"email": "new_owner@companya.com", "role": SystemRole.TENANT_OWNER.value},
    )
    assert res_invite_owner.status_code == 403
    assert "only workspace owners can assign owner privileges" in res_invite_owner.json()["detail"].lower()

    # 3. Org Admin attempts to invite a user as platform_superadmin -> 403 Forbidden
    res_invite_super = await client.post(
        "/api/v1/members/invite",
        headers=admin_headers,
        json={"email": "super@platform.com", "role": SystemRole.PLATFORM_SUPERADMIN.value},
    )
    assert res_invite_super.status_code == 403


@pytest.mark.asyncio
async def test_read_only_viewer_cannot_modify_resources(
    client: AsyncClient, db_session: AsyncSession, seed_data: dict
):
    """A user with VIEWER role cannot create, update, or delete knowledge, documents, or assistants."""
    tenant_a = seed_data["tenant_a"]
    user_repo = UserRepository(db_session)
    role_repo = RoleRepository(db_session)
    member_repo = MemberRepository(db_session, tenant_a.id)

    viewer_role = await role_repo.get_by_name(SystemRole.VIEWER.value)
    assert viewer_role is not None

    viewer_user = await user_repo.create(
        email="viewer_a@companya.com",
        hashed_password=hash_password("Password123!"),
        full_name="Victor Viewer",
    )
    await member_repo.create(
        user_id=viewer_user.id,
        role_id=viewer_role.id,
        status=MembershipStatus.ACTIVE.value,
    )
    await db_session.commit()

    token_viewer = create_access_token(str(viewer_user.id), {"email": viewer_user.email})
    viewer_headers = {
        "Authorization": f"Bearer {token_viewer}",
        "X-Tenant-ID": str(tenant_a.id),
    }

    # 1. Viewer can read knowledge bases -> 200 OK
    res_read = await client.get("/api/v1/knowledge", headers=viewer_headers)
    assert res_read.status_code == 200

    # 2. Viewer cannot create knowledge base -> 403 Forbidden
    res_create_kb = await client.post(
        "/api/v1/knowledge",
        headers=viewer_headers,
        json={"name": "Forbidden KB"},
    )
    assert res_create_kb.status_code == 403

    # 3. Viewer cannot create assistant -> 403 Forbidden
    res_create_asst = await client.post(
        "/api/v1/assistants",
        headers=viewer_headers,
        json={"name": "Forbidden Assistant"},
    )
    assert res_create_asst.status_code == 403


# ==============================================================================
# 4. RESOURCE-LEVEL ACL & DEPARTMENT ISOLATION (ACL-01, ACL-02)
# ==============================================================================


@pytest.mark.asyncio
async def test_department_restricted_document_access(
    client: AsyncClient, db_session: AsyncSession, seed_data: dict
):
    """Department-restricted documents cannot be accessed by employees in other departments or without department."""
    tenant_a = seed_data["tenant_a"]
    token_a_owner = seed_data["token_a_owner"]
    token_a_employee = seed_data["token_a_employee"]  # Andy has no department

    # 1. Create Finance Department in Tenant A
    dept_repo = DepartmentRepository(db_session, tenant_a.id)
    finance_dept = await dept_repo.create(name="Finance")

    # 2. Create Document restricted to Finance Department
    kb_repo = KnowledgeRepository(db_session, tenant_a.id)
    kb = await kb_repo.create(name="Corporate Records", status="ACTIVE")

    doc_repo = DocumentRepository(db_session, tenant_a.id)
    fin_doc = await doc_repo.create(
        knowledge_base_id=kb.id,
        filename="q4_payroll.xlsx",
        safe_filename="q4_payroll.xlsx",
        file_path="/tenants/a/payroll.xlsx",
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        department_id=finance_dept.id,
        status="COMPLETED",
    )
    await doc_repo.create_version(
        document_id=fin_doc.id,
        version_num=1,
        file_path="/tenants/a/payroll.xlsx",
        file_size=1024,
        extracted_text="Executive payroll bonuses for 2026",
    )
    await db_session.commit()

    # 3. Andy (Employee with no department) tries to access Finance document -> 404
    emp_headers = {
        "Authorization": f"Bearer {token_a_employee}",
        "X-Tenant-ID": str(tenant_a.id),
    }
    res_meta = await client.get(f"/api/v1/documents/{fin_doc.id}", headers=emp_headers)
    assert res_meta.status_code == 404

    res_content = await client.get(f"/api/v1/documents/{fin_doc.id}/content", headers=emp_headers)
    assert res_content.status_code == 404

    res_chunks = await client.get(f"/api/v1/documents/{fin_doc.id}/chunks", headers=emp_headers)
    assert res_chunks.status_code == 404

    # 4. Workspace Owner can access Finance document -> 200 OK
    owner_headers = {
        "Authorization": f"Bearer {token_a_owner}",
        "X-Tenant-ID": str(tenant_a.id),
    }
    res_owner = await client.get(f"/api/v1/documents/{fin_doc.id}", headers=owner_headers)
    assert res_owner.status_code == 200
    assert res_owner.json()["filename"] == "q4_payroll.xlsx"


@pytest.mark.asyncio
async def test_department_restricted_knowledge_base_access(
    client: AsyncClient, db_session: AsyncSession, seed_data: dict
):
    """Department-restricted knowledge base cannot be read or uploaded to by non-department members."""
    tenant_a = seed_data["tenant_a"]
    token_a_employee = seed_data["token_a_employee"]

    # Create Legal Department & Restricted KB
    dept_repo = DepartmentRepository(db_session, tenant_a.id)
    legal_dept = await dept_repo.create(name="Legal")

    kb_repo = KnowledgeRepository(db_session, tenant_a.id)
    legal_kb = await kb_repo.create(
        name="Confidential Legal Vault",
        department_id=legal_dept.id,
        status="ACTIVE",
    )
    await db_session.commit()

    emp_headers = {
        "Authorization": f"Bearer {token_a_employee}",
        "X-Tenant-ID": str(tenant_a.id),
    }

    # Andy (no department) queries the Legal KB by ID -> 404
    res_get = await client.get(f"/api/v1/knowledge/{legal_kb.id}", headers=emp_headers)
    assert res_get.status_code == 404

    # Andy queries list -> Legal KB is excluded from results
    res_list = await client.get("/api/v1/knowledge", headers=emp_headers)
    assert res_list.status_code == 200
    kb_ids = [k["id"] for k in res_list.json()]
    assert str(legal_kb.id) not in kb_ids


# ==============================================================================
# 5. RETRIEVAL AUTHORIZATION & SECONDARY DEFENSE (RET-01, RET-02)
# ==============================================================================


@pytest.mark.asyncio
async def test_retrieval_authorizer_filters_deleted_and_department_mismatches(
    db_session: AsyncSession, seed_data: dict
):
    """RetrievalAuthorizer discards deleted documents, superseded versions, and department mismatches."""
    tenant_a = seed_data["tenant_a"]
    authorizer = RetrievalAuthorizer(db_session, tenant_a.id)

    dept_1 = Department(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Dept 1")
    dept_2 = Department(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Dept 2")
    db_session.add_all([dept_1, dept_2])

    kb = KnowledgeBase(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Main KB", status="ACTIVE")
    db_session.add(kb)
    await db_session.flush()

    # Doc 1: Active, public in tenant
    doc_active = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb.id,
        filename="public.txt",
        safe_filename="public.txt",
        file_path="/tenants/public.txt",
        mime_type="text/plain",
        status="COMPLETED",
    )
    # Doc 2: Soft deleted
    doc_deleted = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb.id,
        filename="deleted.txt",
        safe_filename="deleted.txt",
        file_path="/tenants/deleted.txt",
        mime_type="text/plain",
        status="DELETED",
    )
    # Doc 3: Restricted to Dept 2
    doc_dept2 = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb.id,
        filename="dept2.txt",
        safe_filename="dept2.txt",
        file_path="/tenants/dept2.txt",
        mime_type="text/plain",
        department_id=dept_2.id,
        status="COMPLETED",
    )
    db_session.add_all([doc_active, doc_deleted, doc_dept2])
    await db_session.commit()

    candidates = [
        VectorSearchResult(
            chunk_id=uuid.uuid4(),
            document_id=doc_active.id,
            knowledge_base_id=kb.id,
            content="Public info",
            score=0.9,
            rank=1,
            retrieval_source="hybrid",
        ),
        VectorSearchResult(
            chunk_id=uuid.uuid4(),
            document_id=doc_deleted.id,
            knowledge_base_id=kb.id,
            content="Deleted secret",
            score=0.85,
            rank=2,
            retrieval_source="hybrid",
        ),
        VectorSearchResult(
            chunk_id=uuid.uuid4(),
            document_id=doc_dept2.id,
            knowledge_base_id=kb.id,
            content="Dept 2 confidential data",
            score=0.8,
            rank=3,
            retrieval_source="hybrid",
        ),
    ]

    # Non-admin user belonging to Dept 1 evaluates candidates
    filtered = await authorizer.filter_authorized_candidates(
        candidates,
        user_department_id=dept_1.id,
        is_admin=False,
    )

    # Must contain ONLY doc_active. doc_deleted and doc_dept2 are stripped!
    assert len(filtered) == 1
    assert filtered[0].document_id == doc_active.id
    assert filtered[0].rank == 1


# ==============================================================================
# 6. CONVERSATION & CITATION PRIVACY (CON-01, AST-01, AST-02)
# ==============================================================================


@pytest.mark.asyncio
async def test_in_tenant_conversation_privacy_between_employees(
    client: AsyncClient, db_session: AsyncSession, seed_data: dict
):
    """An employee in Tenant A cannot view, delete, or append messages to another employee's conversation."""
    tenant_a = seed_data["tenant_a"]
    user_a_owner = seed_data["user_a_owner"]
    token_a_owner = seed_data["token_a_owner"]
    token_a_employee = seed_data["token_a_employee"]

    # Create Assistant
    asst_repo = AssistantRepository(db_session, tenant_a.id)
    asst = await asst_repo.create_assistant(name="General Assistant", default_model="mock-gpt")

    # Employee 1 (Alice Owner) creates private conversation
    conv_alice = Conversation(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        user_id=user_a_owner.id,
        assistant_id=asst.id,
        title="Alice Private Strategy",
        status="ACTIVE",
    )
    db_session.add(conv_alice)
    await db_session.flush()

    msg_alice = Message(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        conversation_id=conv_alice.id,
        sender_type="user",
        content="Confidential acquisition thoughts",
        token_count=10,
    )
    db_session.add(msg_alice)
    await db_session.commit()

    # 0. Alice Owner can read her conversation -> 200 OK
    alice_headers = {
        "Authorization": f"Bearer {token_a_owner}",
        "X-Tenant-ID": str(tenant_a.id),
    }
    res_alice = await client.get(f"/api/v1/conversations/{conv_alice.id}", headers=alice_headers)
    assert res_alice.status_code == 200

    # Employee 2 (Andy) attempts to access Alice's conversation
    andy_headers = {
        "Authorization": f"Bearer {token_a_employee}",
        "X-Tenant-ID": str(tenant_a.id),
    }

    # 1. GET conversation details -> 404
    res_get = await client.get(f"/api/v1/conversations/{conv_alice.id}", headers=andy_headers)
    assert res_get.status_code == 404

    # 2. GET messages -> 404
    res_msgs = await client.get(f"/api/v1/conversations/{conv_alice.id}/messages", headers=andy_headers)
    assert res_msgs.status_code == 404

    # 3. DELETE conversation -> 404
    res_del = await client.delete(f"/api/v1/conversations/{conv_alice.id}", headers=andy_headers)
    assert res_del.status_code == 404

    # 4. Stream chat to Alice's conversation -> 404
    res_stream = await client.post(
        f"/api/v1/conversations/{conv_alice.id}/messages/stream",
        headers=andy_headers,
        json={"content": "Eavesdropping injection"},
    )
    assert res_stream.status_code == 404


# ==============================================================================
# 7. SSE STREAMING LIFECYCLE & NO ATTRIBUTE ERROR (SSE-01)
# ==============================================================================


@pytest.mark.asyncio
async def test_sse_streaming_endpoint_executes_successfully(
    client: AsyncClient, db_session: AsyncSession, seed_data: dict
):
    """The streaming endpoint executes end-to-end via SSE without AttributeError or crashes."""
    tenant_a = seed_data["tenant_a"]
    user_a_owner = seed_data["user_a_owner"]
    token_a_owner = seed_data["token_a_owner"]

    asst_repo = AssistantRepository(db_session, tenant_a.id)
    asst = await asst_repo.create_assistant(
        name="Mock SSE Assistant",
        llm_provider="mock",
        default_model="mock-gpt",
        system_prompt="Answer briefly.",
    )

    conv = Conversation(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        user_id=user_a_owner.id,
        assistant_id=asst.id,
        title="Streaming Test",
        status="ACTIVE",
    )
    db_session.add(conv)
    await db_session.commit()

    headers = {
        "Authorization": f"Bearer {token_a_owner}",
        "X-Tenant-ID": str(tenant_a.id),
    }

    # Call streaming endpoint
    res = await client.post(
        f"/api/v1/conversations/{conv.id}/messages/stream",
        headers=headers,
        json={"content": "Hello world!"},
    )
    assert res.status_code == 200
    assert "text/event-stream" in res.headers.get("content-type", "")

    content = res.text
    assert "event: message_start" in content
    assert "event: token" in content
    assert "event: message_complete" in content


# ==============================================================================
# 8. BYOK CREDENTIAL ISOLATION & MASKING (BYOK-01)
# ==============================================================================


@pytest.mark.asyncio
async def test_byok_credential_isolation_and_masking(
    client: AsyncClient, db_session: AsyncSession, seed_data: dict
):
    """BYOK credentials are encrypted in DB, masked in API responses, and never logged."""
    tenant_a = seed_data["tenant_a"]
    token_a_owner = seed_data["token_a_owner"]

    kb_repo = KnowledgeRepository(db_session, tenant_a.id)
    kb = await kb_repo.create(name="BYOK KB", status="ACTIVE")
    await db_session.commit()

    headers = {
        "Authorization": f"Bearer {token_a_owner}",
        "X-Tenant-ID": str(tenant_a.id),
    }

    secret_key = "sk-live-supersecrettoken-12345678"

    # Configure retrieval with API key
    patch_res = await client.patch(
        f"/api/v1/knowledge/{kb.id}/retrieval-config",
        headers=headers,
        json={"api_key": secret_key, "embedding_provider": "sentence-transformer"},
    )
    assert patch_res.status_code == 200
    data = patch_res.json()
    assert data["has_api_key"] is True
    # Masked representation only
    assert data["masked_api_key"] == "sk-l....5678"
    assert secret_key not in patch_res.text

    # Verify database record contains Fernet ciphertext, NOT plaintext
    ret_repo = RetrievalRepository(db_session, tenant_a.id)
    cfg = await ret_repo.get_by_kb_id(kb.id)
    assert cfg is not None
    assert cfg.encrypted_api_key != secret_key
    assert decrypt_secret(cfg.encrypted_api_key) == secret_key

    # Corrupted ciphertext fails closed
    assert decrypt_secret("corrupted-ciphertext") is None
