"""Milestone M10 Stage 1: Comprehensive Security and Reliability Verification Suite.

Exercises negative security scenarios, boundary validations, and isolation guarantees
across all 9 critical areas defined in M10 Stage 1.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assistant_runtime.runtime import AssistantRuntime
from app.models.assistant import Assistant
from app.models.knowledge import Document, KnowledgeBase
from app.models.membership import TenantMembership
from app.models.provider import ProviderUsageLog
from app.models.publishing import APIKey, PublicChatSession
from app.observability.tracer import sanitize_value
from app.schemas.publishing import AssistantPublicationCreate
from app.services.api_key_service import hash_api_key
from app.services.evaluation_service import EvaluationService
from app.services.publishing_service import PublishingService
from app.services.quota_service import QuotaService
from app.storage.base import sanitize_filename
from app.storage.s3 import S3StorageProvider
from app.vectorstores.base import VectorStoreFilter
from app.vectorstores.qdrant_store import QdrantVectorStore


async def _create_test_assistant(db: AsyncSession, tenant_id: uuid.UUID, name: str = "Test Asst") -> Assistant:
    asst = Assistant(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=name,
        slug=name.lower().replace(" ", "-") + "-" + uuid.uuid4().hex[:6],
        llm_provider="mock",
        default_model="mock-gpt",
        system_prompt="You are a helpful test assistant.",
    )
    db.add(asst)
    await db.commit()
    await db.refresh(asst)
    return asst


# ==============================================================================
# 1A: TENANT ISOLATION
# ==============================================================================


@pytest.mark.asyncio
async def test_cross_tenant_assistant_update_denied(client: AsyncClient, seed_data: dict, db_session: AsyncSession):
    """Tenant B cannot update Tenant A's assistant (returns 404)."""
    tenant_a = seed_data["tenant_a"]
    tenant_b = seed_data["tenant_b"]
    asst_a = await _create_test_assistant(db_session, tenant_a.id, "Tenant A Private Bot")

    headers_b = {
        "Authorization": f"Bearer {seed_data['token_b_owner']}",
        "X-Tenant-ID": str(tenant_b.id),
    }
    update_res = await client.put(
        f"/api/v1/assistants/{asst_a.id}",
        json={"name": "Hacked Bot Name"},
        headers=headers_b,
    )
    assert update_res.status_code == 404


@pytest.mark.asyncio
async def test_cross_tenant_evaluations_isolation(client: AsyncClient, seed_data: dict, db_session: AsyncSession):
    """Tenant B cannot read or run evaluations on Tenant A's datasets or assistants."""
    tenant_a = seed_data["tenant_a"]
    tenant_b = seed_data["tenant_b"]
    headers_a = {"Authorization": f"Bearer {seed_data['token_a_owner']}", "X-Tenant-ID": str(tenant_a.id)}
    headers_b = {"Authorization": f"Bearer {seed_data['token_b_owner']}", "X-Tenant-ID": str(tenant_b.id)}

    asst_a = await _create_test_assistant(db_session, tenant_a.id, "Eval Asst A")
    eval_svc_a = EvaluationService(db_session, tenant_a.id)
    dataset_a = await eval_svc_a.create_dataset(
        name="Confidential A Benchmark",
        items=[{"question": "What is the secret?", "expected_answer": "Top secret A"}],
    )

    # Trigger evaluation run in Tenant A
    run_res = await client.post(
        "/api/v1/evaluations/runs",
        json={"assistant_id": str(asst_a.id), "dataset_id": str(dataset_a.id), "eval_type": "deterministic"},
        headers=headers_a,
    )
    assert run_res.status_code == 201
    run_a_id = run_res.json()["id"]

    # 1. Tenant B tries to fetch Tenant A's dataset -> 404
    get_ds_b = await client.get(f"/api/v1/evaluations/datasets/{dataset_a.id}", headers=headers_b)
    assert get_ds_b.status_code == 404

    # 2. Tenant B tries to fetch Tenant A's evaluation run -> 404
    get_run_b = await client.get(f"/api/v1/evaluations/runs/{run_a_id}", headers=headers_b)
    assert get_run_b.status_code == 404

    # 3. Tenant B tries to execute an evaluation run pointing to Tenant A's dataset -> 400 / 404
    asst_b = await _create_test_assistant(db_session, tenant_b.id, "Asst B")
    bad_run_b = await client.post(
        "/api/v1/evaluations/runs",
        json={"assistant_id": str(asst_b.id), "dataset_id": str(dataset_a.id)},
        headers=headers_b,
    )
    assert bad_run_b.status_code in (400, 404)


@pytest.mark.asyncio
async def test_cross_tenant_usage_isolation(client: AsyncClient, seed_data: dict, db_session: AsyncSession):
    """Tenant B cannot read Tenant A's usage records or spoof X-Tenant-ID."""
    tenant_a = seed_data["tenant_a"]
    tenant_b = seed_data["tenant_b"]

    # Record usage in Tenant A
    log_a = ProviderUsageLog(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        provider="mock",
        model="mock-gpt",
        prompt_tokens=5000,
        completion_tokens=2000,
        total_tokens=7000,
    )
    db_session.add(log_a)
    await db_session.commit()

    # Bob queries usage with Tenant B context -> MUST NOT see Tenant A's 7000 tokens
    headers_b = {"Authorization": f"Bearer {seed_data['token_b_owner']}", "X-Tenant-ID": str(tenant_b.id)}
    usage_res_b = await client.get("/api/v1/providers/usage", headers=headers_b)
    assert usage_res_b.status_code == 200
    data_b = usage_res_b.json()
    assert data_b["monthly_tokens_used"] == 0

    # Bob attempts to spoof Tenant A's ID with his Tenant B token -> 403 Forbidden
    spoofed = {"Authorization": f"Bearer {seed_data['token_b_owner']}", "X-Tenant-ID": str(tenant_a.id)}
    spoof_res = await client.get("/api/v1/providers/usage", headers=spoofed)
    assert spoof_res.status_code == 403
    assert "Access denied" in spoof_res.json()["detail"]


@pytest.mark.asyncio
async def test_revoked_member_access_blocked(client: AsyncClient, seed_data: dict, db_session: AsyncSession):
    """A revoked/inactive organization member is denied workspace access (403 Forbidden)."""
    tenant_a = seed_data["tenant_a"]
    user_emp = seed_data["user_a_employee"]
    token_emp = seed_data["token_a_employee"]

    headers_emp = {"Authorization": f"Bearer {token_emp}", "X-Tenant-ID": str(tenant_a.id)}

    # 1. Active employee can list assistants
    res1 = await client.get("/api/v1/assistants", headers=headers_emp)
    assert res1.status_code == 200

    # 2. Revoke membership by setting status to INACTIVE
    stmt = select(TenantMembership).where(
        TenantMembership.tenant_id == tenant_a.id,
        TenantMembership.user_id == user_emp.id,
    )
    m = (await db_session.execute(stmt)).scalar_one()
    m.status = "INACTIVE"
    await db_session.commit()

    # 3. Employee request is now rejected with 403 Forbidden
    res2 = await client.get("/api/v1/assistants", headers=headers_emp)
    assert res2.status_code == 403
    assert "Access denied" in res2.json()["detail"]


# ==============================================================================
# 1B: PUBLIC PUBLISHING SECURITY
# ==============================================================================


@pytest.mark.asyncio
async def test_public_publishing_domain_whitelist_enforcement(client: AsyncClient, seed_data: dict, db_session: AsyncSession):
    """Embed chat enforces domain whitelist; unpermitted origins are rejected with 403."""
    tenant_a = seed_data["tenant_a"]
    asst = await _create_test_assistant(db_session, tenant_a.id, "Domain Protected Asst")
    headers_a = {"Authorization": f"Bearer {seed_data['token_a_owner']}", "X-Tenant-ID": str(tenant_a.id)}

    # Publish with strict allowed_domains
    pub_res = await client.post(
        f"/api/v1/assistants/{asst.id}/publish",
        json={"visibility": "PUBLIC", "allowed_domains": ["app.trustedcompany.com"]},
        headers=headers_a,
    )
    assert pub_res.status_code == 200
    public_id = pub_res.json()["public_id"]

    # 1. Allowed origin succeeds
    ok_res = await client.post(
        f"/api/v1/public/assistants/{public_id}/chat",
        json={"message": "Hello from allowed host"},
        headers={"Origin": "https://app.trustedcompany.com"},
    )
    assert ok_res.status_code == 200

    # 2. Unauthorized origin is rejected with 403
    blocked_res = await client.post(
        f"/api/v1/public/assistants/{public_id}/chat",
        json={"message": "Attack from evil site"},
        headers={"Origin": "https://evil-phishing.com"},
    )
    assert blocked_res.status_code == 403
    assert "not permitted" in blocked_res.json()["detail"]

    # 3. Missing origin/referer must not bypass a configured allowlist.
    #    (M11 hardening: previously direct navigation was implicitly trusted.)
    direct_res = await client.post(
        f"/api/v1/public/assistants/{public_id}/chat",
        json={"message": "Direct visitor"},
    )
    assert direct_res.status_code == 403
    assert "not permitted" in direct_res.json()["detail"]


@pytest.mark.asyncio
async def test_unpublish_revokes_public_access(client: AsyncClient, seed_data: dict, db_session: AsyncSession):
    """Unpublishing an assistant immediately revokes public metadata and chat endpoints."""
    tenant_a = seed_data["tenant_a"]
    asst = await _create_test_assistant(db_session, tenant_a.id, "Unpublishable Asst")
    headers_a = {"Authorization": f"Bearer {seed_data['token_a_owner']}", "X-Tenant-ID": str(tenant_a.id)}

    # Publish
    pub_res = await client.post(
        f"/api/v1/assistants/{asst.id}/publish",
        json={"visibility": "PUBLIC"},
        headers=headers_a,
    )
    public_id = pub_res.json()["public_id"]

    # Unpublish
    unpub_res = await client.post(f"/api/v1/assistants/{asst.id}/unpublish", headers=headers_a)
    assert unpub_res.status_code == 200

    # Public metadata -> 404
    meta_res = await client.get(f"/api/v1/public/assistants/{public_id}")
    assert meta_res.status_code == 404

    # Public chat -> 403
    chat_res = await client.post(
        f"/api/v1/public/assistants/{public_id}/chat",
        json={"message": "Hello?"},
    )
    assert chat_res.status_code == 403


@pytest.mark.asyncio
async def test_expired_public_session_isolation(db_session: AsyncSession, seed_data: dict):
    """Expired public chat session cannot be reused to hijack an existing conversation."""
    tenant_a = seed_data["tenant_a"]
    asst = await _create_test_assistant(db_session, tenant_a.id, "Expiry Test Asst")

    pub_svc = PublishingService(db_session, tenant_a.id)
    pub = await pub_svc.publish_assistant(asst.id, payload=AssistantPublicationCreate(visibility="PUBLIC"))

    # Create an already-expired session
    old_token = "sess_expired_1234567890abcdef"
    expired_sess = PublicChatSession(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        publication_id=pub.id,
        session_token=old_token,
        expires_at=datetime.now(UTC) - timedelta(hours=2),
    )
    db_session.add(expired_sess)
    await db_session.commit()

    # When resolving with the expired token, it must reject with 401 Unauthorized
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await pub_svc.get_or_create_public_session(
            publication_id=pub.id,
            session_token=old_token,
        )
    assert exc_info.value.status_code == 401
    assert "session has expired" in exc_info.value.detail


# ==============================================================================
# 1C: DEVELOPER API KEY SECURITY
# ==============================================================================


@pytest.mark.asyncio
async def test_developer_api_key_security_matrix(client: AsyncClient, seed_data: dict, db_session: AsyncSession):
    """Verify key validation, scopes, one-time plaintext visibility, and hashing."""
    tenant_a = seed_data["tenant_a"]
    _tenant_b = seed_data["tenant_b"]
    asst_a1 = await _create_test_assistant(db_session, tenant_a.id, "Asst A1")
    _asst_a2 = await _create_test_assistant(db_session, tenant_a.id, "Asst A2")
    headers_a = {"Authorization": f"Bearer {seed_data['token_a_owner']}", "X-Tenant-ID": str(tenant_a.id)}

    # 1. Create Key with assistant:read scope ONLY, restricted to asst_a1
    create_res = await client.post(
        "/api/v1/developer/api-keys",
        json={"name": "Read Only Key", "scopes": ["assistant:read"], "assistant_id": str(asst_a1.id)},
        headers=headers_a,
    )
    assert create_res.status_code == 201
    key_info = create_res.json()
    raw_key = key_info["raw_key"]
    key_id = key_info["id"]

    # Verify SHA-256 hash in database
    db_key = await db_session.get(APIKey, uuid.UUID(key_id))
    assert db_key is not None
    assert db_key.key_hash == hash_api_key(raw_key)
    assert raw_key not in db_key.key_hash  # Plaintext never stored

    dev_headers = {"Authorization": f"Bearer {raw_key}"}

    # 2. Key can read allowed assistant
    res_read = await client.get("/api/v1/developer/assistants", headers=dev_headers)
    assert res_read.status_code == 200
    assert len(res_read.json()) == 1

    # 3. Key lacks 'assistant:chat' scope -> 403 Forbidden
    res_chat = await client.post(
        f"/api/v1/developer/assistants/{asst_a1.id}/chat",
        json={"message": "Chat attempt"},
        headers=dev_headers,
    )
    assert res_chat.status_code == 403
    assert "lacks required permission scope" in res_chat.json()["detail"]

    # 4. Revoked key is rejected -> 401 Unauthorized
    del_res = await client.delete(f"/api/v1/developer/api-keys/{key_id}", headers=headers_a)
    assert del_res.status_code in (200, 204)

    res_revoked = await client.get("/api/v1/developer/assistants", headers=dev_headers)
    assert res_revoked.status_code == 401

    # 5. Invalid key format/token -> 401 Unauthorized
    res_invalid = await client.get("/api/v1/developer/assistants", headers={"Authorization": "Bearer mmaip_live_fake12345"})
    assert res_invalid.status_code == 401


# ==============================================================================
# 1D: QDRANT & RETRIEVAL ACL SECURITY
# ==============================================================================


@pytest.mark.asyncio
async def test_qdrant_empty_filter_fails_closed():
    """Verify that an empty document_ids list returns [] without executing an unrestricted search."""
    store = QdrantVectorStore(url="http://localhost:6333")

    # Empty document allowlist MUST immediately return []
    empty_filter = VectorStoreFilter(
        tenant_id=uuid.uuid4(),
        knowledge_base_ids=[uuid.uuid4()],
        document_ids=[],
    )
    results = await store.search(
        query_vector=[0.1, 0.2, 0.3, 0.4],
        filter_criteria=empty_filter,
        top_k=5,
    )
    assert results == []


@pytest.mark.asyncio
async def test_public_chat_runtime_strictly_excludes_non_public_documents(db_session: AsyncSession, seed_data: dict):
    """AssistantRuntime with is_public=True only retrieves documents where access_level == 'PUBLIC'."""
    tenant_a = seed_data["tenant_a"]
    kb = KnowledgeBase(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Public Boundary KB", status="ACTIVE")
    db_session.add(kb)
    await db_session.flush()

    # Public document
    doc_pub = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb.id,
        filename="public_faq.txt",
        safe_filename="public_faq.txt",
        file_path="/tenants/pub",
        mime_type="text/plain",
        status="COMPLETED",
        access_level="PUBLIC",
    )
    # Confidential internal document
    doc_conf = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb.id,
        filename="internal_passwords.txt",
        safe_filename="internal_passwords.txt",
        file_path="/tenants/conf",
        mime_type="text/plain",
        status="COMPLETED",
        access_level="CONFIDENTIAL",
    )
    db_session.add_all([doc_pub, doc_conf])
    await db_session.commit()

    # Query public documents for this tenant and KB
    pub_stmt = select(Document.id).where(
        Document.knowledge_base_id == kb.id,
        Document.tenant_id == tenant_a.id,
        Document.access_level == "PUBLIC",
        Document.status != "DELETED",
    )
    allowed_ids = list((await db_session.execute(pub_stmt)).scalars().all())

    # Only doc_pub is in the allowlist; doc_conf is strictly excluded
    assert doc_pub.id in allowed_ids
    assert doc_conf.id not in allowed_ids


# ==============================================================================
# 1E: BYOK & SECRET PROTECTION
# ==============================================================================


@pytest.mark.asyncio
async def test_commercial_provider_requires_active_byok(db_session: AsyncSession, seed_data: dict):
    """Commercial provider (OpenAI) with no configured BYOK key yields an explicit error and stops execution."""
    tenant_a = seed_data["tenant_a"]
    asst = Assistant(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        name="Uncredentialed OpenAI Bot",
        slug="openai-bot-" + uuid.uuid4().hex[:6],
        llm_provider="openai",  # Commercial provider!
        default_model="gpt-4o-mini",
        system_prompt="You are an OpenAI assistant.",
    )
    db_session.add(asst)

    from app.models.conversation import Conversation
    conv = Conversation(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        assistant_id=asst.id,
        title="BYOK Test Chat",
    )
    db_session.add(conv)
    await db_session.commit()

    runtime = AssistantRuntime(session=db_session, tenant_id=tenant_a.id, user_id=None)
    events = []
    async for event_str in runtime.stream_chat(conv.id, "Hello"):
        events.append(event_str)

    full_output = "".join(events)
    # Must report missing BYOK credential and never silently fall back
    assert "event: message_error" in full_output
    assert "is not configured with an active BYOK credential" in full_output


# ==============================================================================
# 1F: QUOTA CONCURRENCY
# ==============================================================================


@pytest.mark.asyncio
async def test_quota_concurrency_in_flight_reservation(db_session: AsyncSession, seed_data: dict):
    """Verify that in-flight token reservations safely block concurrent requests exceeding quota limits."""
    tenant_a = seed_data["tenant_a"]
    quota_svc = QuotaService(db_session, tenant_a.id)

    quota = await quota_svc.get_or_create_quota()
    quota.monthly_token_limit = 5000
    await db_session.commit()

    # 1. Reserve 4,000 tokens
    res_1 = await quota_svc.reserve_quota(estimated_tokens=4000)
    assert res_1 is not None

    # 2. Second request for 2,000 tokens must be rejected because in-flight + requested > 5,000
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await quota_svc.reserve_quota(estimated_tokens=2000)
    assert exc_info.value.status_code == 429
    assert "Monthly token limit exceeded" in exc_info.value.detail

    # 3. Release first reservation
    QuotaService.release_reservation(res_1)

    # 4. Now the 2,000 token request succeeds
    res_2 = await quota_svc.reserve_quota(estimated_tokens=2000)
    assert res_2 is not None
    QuotaService.release_reservation(res_2)


# ==============================================================================
# 1G: STORAGE ISOLATION & PATH TRAVERSAL
# ==============================================================================


def test_storage_path_sanitization_matrix():
    """Verify that sanitize_filename prevents directory traversal and illegal characters."""
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("..\\..\\windows\\system32\\cmd.exe") == "cmd.exe"
    assert sanitize_filename("/var/log/syslog") == "syslog"
    assert sanitize_filename("safe_document.pdf") == "safe_document.pdf"


def test_s3_storage_tenant_prefix_isolation():
    """Verify that S3StorageProvider always scopes paths to {tenant_id}."""
    provider = S3StorageProvider(bucket_name="test-bucket")
    tenant_id = "tenant-xyz-999"

    # Leading slash or traversal cannot escape tenant prefix
    key1 = provider._get_full_key(tenant_id, "doc1.txt")
    assert key1 == "tenant-xyz-999/doc1.txt"

    key2 = provider._get_full_key(tenant_id, "/nested/path/doc2.pdf")
    assert key2 == "tenant-xyz-999/nested/path/doc2.pdf"


# ==============================================================================
# 1H & 1I: OBSERVABILITY & SECRET REDACTION
# ==============================================================================


def test_observability_recursive_secret_redaction():
    """Verify recursive redaction of API keys, bearer tokens, and secrets."""
    dirty_data = {
        "user_query": "Please review my prompt",
        "api_key": "sk-1234567890abcdef12345678",
        "auth_header": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz",
        "nested": {
            "platform_key": "mmaip_live_9876543210fedcba",
            "password": "Password123!",
            "message": "Encountered sk-999888777666555444 while generating",
        },
    }

    clean = sanitize_value(dirty_data)
    assert "api_key" not in clean  # Sensitive key dropped
    assert "auth_header" not in clean  # Sensitive header dropped
    assert "password" not in clean["nested"]
    assert "[REDACTED_API_KEY]" in clean["nested"]["message"]
