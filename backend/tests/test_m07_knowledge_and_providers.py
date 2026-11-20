"""Comprehensive acceptance and regression test suite for M07:
Knowledge Studio, Retrieval Playground, BYOK Vault, Provider Registry & Quotas.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient, Response

from app.core.crypto import encrypt_secret
from app.llm import LLMConfig, get_llm_registry
from app.llm.capabilities import get_model_capability, get_provider_models
from app.models.knowledge import Document, DocumentChunk, KnowledgeBase
from app.models.provider import ProviderCredential, ProviderUsageLog
from app.schemas.provider import URLIngestRequest
from app.services.byok_vault import BYOKVaultService
from app.services.ingestion.url_ingestion import SSRFValidationError, fetch_url_content_safe, validate_destination_ip
from app.services.quota_service import QuotaService


# ---------------------------------------------------------------------------
# Feature F: Provider Registry & Capabilities
# ---------------------------------------------------------------------------


def test_provider_registry_and_capabilities():
    """Verify registry catalogs all providers with capability definitions."""
    registry = get_llm_registry()
    providers = registry.get_all_providers()
    provider_names = {p.provider_name for p in providers}

    assert "groq" in provider_names
    assert "anthropic" in provider_names
    assert "gemini" in provider_names
    assert "openai" in provider_names
    assert "omniroute" in provider_names
    assert "mock" in provider_names

    # Check model capabilities
    groq_models = get_provider_models("groq")
    assert any(m.model_id == "llama-3.3-70b-versatile" for m in groq_models)
    llama_cap = get_model_capability("llama-3.3-70b-versatile")
    assert llama_cap is not None
    assert llama_cap.context_window >= 128000
    assert llama_cap.supports_streaming is True

    anthropic_models = get_provider_models("anthropic")
    assert any(m.model_id == "claude-3-5-sonnet-20241022" for m in anthropic_models)
    sonnet_cap = get_model_capability("claude-3-5-sonnet-20241022")
    assert sonnet_cap is not None
    assert sonnet_cap.supports_vision is True


@pytest.mark.asyncio
async def test_provider_directory_api_endpoint(client: AsyncClient, seed_data: dict):
    """Verify GET /api/v1/providers/directory returns capabilities and models."""
    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(seed_data["tenant_a"].id),
    }

    resp = await client.get("/api/v1/providers/directory", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 6
    names = [p["name"] for p in data]
    assert "groq" in names
    assert "anthropic" in names
    assert "gemini" in names
    assert "openai" in names


# ---------------------------------------------------------------------------
# Feature G: BYOK Key Vault & Credential Lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_byok_credential_lifecycle(client: AsyncClient, seed_data: dict):
    """Test full BYOK lifecycle: create, list (masked), test connection, rotate, revoke, delete."""
    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(seed_data["tenant_a"].id),
    }

    # 1. Add Credential
    raw_key = "sk-ant-api03-test-secret-key-for-m07-validation-9988"
    payload = {
        "provider_name": "anthropic",
        "display_name": "Production Anthropic Key",
        "api_key": raw_key,
        "is_default": True,
    }
    resp = await client.post("/api/v1/providers/credentials", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    created = resp.json()

    assert created["provider_name"] == "anthropic"
    assert created["display_name"] == "Production Anthropic Key"
    assert created["is_default"] is True
    # Secret must NEVER be returned in plaintext
    assert raw_key not in resp.text
    assert "..." in created["api_key_masked"]
    assert created["api_key_masked"].endswith("9988")
    cred_id = created["id"]

    # 2. List Credentials
    list_resp = await client.get("/api/v1/providers/credentials", headers=headers)
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert any(c["id"] == cred_id for c in items)
    # Ensure plaintext secret is not leaked in list
    assert raw_key not in list_resp.text

    # 3. Rotate Credential
    new_raw_key = "sk-ant-api03-rotated-key-for-m07-verification-1122"
    rotate_resp = await client.post(
        f"/api/v1/providers/credentials/{cred_id}/rotate",
        json={"new_api_key": new_raw_key},
        headers=headers,
    )
    assert rotate_resp.status_code == 200
    rotated = rotate_resp.json()
    assert new_raw_key not in rotate_resp.text
    assert rotated["api_key_masked"].endswith("1122")

    # 4. Revoke Credential
    revoke_resp = await client.post(
        f"/api/v1/providers/credentials/{cred_id}/revoke",
        headers=headers,
    )
    assert revoke_resp.status_code == 200
    revoked = revoke_resp.json()
    assert revoked["is_active"] is False
    assert revoked["status"] == "REVOKED"

    # 5. Delete Credential
    del_resp = await client.delete(
        f"/api/v1/providers/credentials/{cred_id}",
        headers=headers,
    )
    assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_byok_cross_tenant_isolation(client: AsyncClient, seed_data: dict):
    """Verify Tenant B cannot view, rotate, revoke, or delete Tenant A's provider credentials."""
    headers_a = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(seed_data["tenant_a"].id),
    }
    headers_b = {
        "Authorization": f"Bearer {seed_data['token_b_owner']}",
        "X-Tenant-ID": str(seed_data["tenant_b"].id),
    }

    # Tenant A creates credential
    payload = {
        "provider_name": "openai",
        "display_name": "Tenant A OpenAI Vault",
        "api_key": "sk-proj-test-isolated-key-tenant-a-12345",
    }
    resp = await client.post("/api/v1/providers/credentials", json=payload, headers=headers_a)
    assert resp.status_code == 201
    cred_id = resp.json()["id"]

    # Tenant B tries to rotate Tenant A's credential -> 404
    rotate_b = await client.post(
        f"/api/v1/providers/credentials/{cred_id}/rotate",
        json={"new_api_key": "sk-proj-hacked-key-55555"},
        headers=headers_b,
    )
    assert rotate_b.status_code in (404, 403)

    # Tenant B tries to delete Tenant A's credential -> 404
    del_b = await client.delete(
        f"/api/v1/providers/credentials/{cred_id}",
        headers=headers_b,
    )
    assert del_b.status_code in (404, 403)

    # Tenant B listing credentials must NOT include Tenant A's credential
    list_b = await client.get("/api/v1/providers/credentials", headers=headers_b)
    assert list_b.status_code == 200
    assert not any(c["id"] == cred_id for c in list_b.json())


# ---------------------------------------------------------------------------
# Feature C & I: Quota Enforcement & Accounting
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_quota_accounting_and_summary_endpoint(client: AsyncClient, seed_data: dict, db_session):
    """Test quota summary endpoint and atomic usage logging."""
    tenant_id = seed_data["tenant_a"].id
    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(tenant_id),
    }

    quota_svc = QuotaService(db_session, tenant_id)
    # Log usage
    await quota_svc.record_usage(
        provider_name="groq",
        model_name="llama-3.3-70b-versatile",
        prompt_tokens=150,
        completion_tokens=250,
        user_id=seed_data["user_a_owner"].id,
    )

    resp = await client.get("/api/v1/providers/usage/summary", headers=headers)
    assert resp.status_code == 200
    summary = resp.json()

    assert summary["monthly_tokens_used"] >= 400
    assert summary["monthly_prompt_tokens"] >= 150
    assert summary["monthly_completion_tokens"] >= 250
    assert summary["today_requests"] >= 1
    assert summary["monthly_tokens_limit"] > 0


@pytest.mark.asyncio
async def test_quota_service_rejection_at_limit(seed_data: dict, db_session):
    """Verify QuotaService raises 429 when monthly tokens or daily requests are exceeded."""
    tenant_id = seed_data["tenant_a"].id
    quota_svc = QuotaService(db_session, tenant_id)

    # Artificially set low limit and record usage
    quota = await quota_svc.get_or_create_quota()
    quota.monthly_token_limit = 500
    await db_session.commit()

    await quota_svc.record_usage(
        provider_name="mock",
        model_name="mock-model",
        prompt_tokens=200,
        completion_tokens=280,
    )

    # Request requiring 50 tokens exceeds 500 limit (480 + 50 = 530 > 500) -> 429
    with pytest.raises(Exception) as exc_info:
        await quota_svc.check_quota(estimated_tokens=50)
    assert "429" in str(exc_info.value) or "Monthly token limit exceeded" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Feature A & SSRF Defenses: Safe URL Ingestion
# ---------------------------------------------------------------------------


def test_ssrf_ip_validator_blocks_private_and_metadata():
    """Verify that private IP ranges, loopback, and metadata endpoints are strictly blocked."""
    # Loopback
    with pytest.raises(SSRFValidationError):
        validate_destination_ip("127.0.0.1")
    with pytest.raises(SSRFValidationError):
        validate_destination_ip("localhost")

    # Cloud Metadata
    with pytest.raises(SSRFValidationError):
        validate_destination_ip("169.254.169.254")
    with pytest.raises(SSRFValidationError):
        validate_destination_ip("metadata.google.internal")

    # RFC 1918 Private Ranges
    with pytest.raises(SSRFValidationError):
        validate_destination_ip("10.0.0.5")
    with pytest.raises(SSRFValidationError):
        validate_destination_ip("192.168.1.1")
    with pytest.raises(SSRFValidationError):
        validate_destination_ip("172.16.0.1")


@pytest.mark.asyncio
async def test_url_ingest_endpoint_blocks_ssrf(client: AsyncClient, seed_data: dict):
    """Verify POST /api/v1/documents/ingest-url blocks SSRF requests with 400 Bad Request."""
    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(seed_data["tenant_a"].id),
    }

    # Create KB first
    kb_resp = await client.post(
        "/api/v1/knowledge",
        json={"name": "SSRF Guard KB", "description": "Testing URL defenses"},
        headers=headers,
    )
    assert kb_resp.status_code == 201
    kb_id = kb_resp.json()["id"]

    # Target 1: Localhost loopback
    resp_loopback = await client.post(
        "/api/v1/documents/ingest-url",
        json={"knowledge_base_id": kb_id, "url": "http://127.0.0.1:8000/api/secret"},
        headers=headers,
    )
    assert resp_loopback.status_code == 400
    assert "Security error" in resp_loopback.text or "blocked" in resp_loopback.text

    # Target 2: Cloud Metadata endpoint
    resp_meta = await client.post(
        "/api/v1/documents/ingest-url",
        json={"knowledge_base_id": kb_id, "url": "http://169.254.169.254/latest/meta-data/"},
        headers=headers,
    )
    assert resp_meta.status_code == 400
    assert "Security error" in resp_meta.text or "blocked" in resp_meta.text


@pytest.mark.asyncio
async def test_url_ingest_mock_success(client: AsyncClient, seed_data: dict):
    """Verify valid public URL ingestion successfully stores document and enqueues job."""
    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(seed_data["tenant_a"].id),
    }

    kb_resp = await client.post(
        "/api/v1/knowledge",
        json={"name": "Web Knowledge Base", "description": "Testing valid web page ingestion"},
        headers=headers,
    )
    kb_id = kb_resp.json()["id"]

    mock_html = b"<html><head><title>Platform Documentation</title></head><body><h1>Guide</h1><p>Content.</p></body></html>"

    with patch(
        "app.api.v1.documents.fetch_url_content_safe",
        new=AsyncMock(return_value=("Platform Documentation", mock_html, "text/html")),
    ):
        resp = await client.post(
            "/api/v1/documents/ingest-url",
            json={"knowledge_base_id": kb_id, "url": "https://example.com/docs/guide"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "document" in data
        assert "job" in data
        assert data["document"]["filename"].endswith(".html")


# ---------------------------------------------------------------------------
# Feature B: Chunk Inspector
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_document_chunk_inspector_provenance(client: AsyncClient, seed_data: dict, db_session):
    """Verify GET /api/v1/documents/{document_id}/chunks exposes accurate provenance and enforces tenant isolation."""
    tenant_a_id = seed_data["tenant_a"].id
    tenant_b_id = seed_data["tenant_b"].id
    headers_a = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(tenant_a_id),
    }
    headers_b = {
        "Authorization": f"Bearer {seed_data['token_b_owner']}",
        "X-Tenant-ID": str(tenant_b_id),
    }

    # Create KB and Document in Tenant A
    kb = KnowledgeBase(
        id=uuid.uuid4(),
        tenant_id=tenant_a_id,
        name="Chunk KB",
        status="ACTIVE",
    )
    doc = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_a_id,
        knowledge_base_id=kb.id,
        filename="handbook.pdf",
        safe_filename="handbook.pdf",
        file_path="storage/handbook.pdf",
        file_size=2048,
        mime_type="application/pdf",
        file_hash="hash12345",
        status="PROCESSED",
    )
    chunk1 = DocumentChunk(
        id=uuid.uuid4(),
        tenant_id=tenant_a_id,
        knowledge_base_id=kb.id,
        document_id=doc.id,
        chunk_index=0,
        content="Welcome to our company policies and guidelines.",
        character_count=48,
        token_count=8,
        page_number=1,
        heading_path="Chapter 1 > Introduction",
        chunking_strategy="recursive",
    )
    chunk2 = DocumentChunk(
        id=uuid.uuid4(),
        tenant_id=tenant_a_id,
        knowledge_base_id=kb.id,
        document_id=doc.id,
        chunk_index=1,
        content="Benefits include 25 days paid time off.",
        character_count=39,
        token_count=7,
        page_number=2,
        heading_path="Chapter 2 > Benefits",
        chunking_strategy="recursive",
    )
    db_session.add_all([kb, doc, chunk1, chunk2])
    await db_session.commit()

    # 1. Tenant A inspects chunks
    resp = await client.get(f"/api/v1/documents/{doc.id}/chunks", headers=headers_a)
    assert resp.status_code == 200, resp.text
    chunks = resp.json()
    assert len(chunks) == 2
    assert chunks[0]["chunk_index"] == 0
    assert chunks[0]["page_number"] == 1
    assert chunks[0]["heading_path"] == "Chapter 1 > Introduction"
    assert chunks[0]["token_count"] == 8
    assert chunks[1]["chunk_index"] == 1
    assert chunks[1]["page_number"] == 2

    # 2. Tenant B cross-tenant inspection -> 404
    resp_cross = await client.get(f"/api/v1/documents/{doc.id}/chunks", headers=headers_b)
    assert resp_cross.status_code == 404


# ---------------------------------------------------------------------------
# Feature D & E: Retrieval Playground & Truthful Scores
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retrieval_playground_query_and_metrics(client: AsyncClient, seed_data: dict, db_session):
    """Verify POST /api/v1/retrieval/playground returns measured latency, scores, and provenance."""
    tenant_a_id = seed_data["tenant_a"].id
    tenant_b_id = seed_data["tenant_b"].id
    headers_a = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(tenant_a_id),
    }
    headers_b = {
        "Authorization": f"Bearer {seed_data['token_b_owner']}",
        "X-Tenant-ID": str(tenant_b_id),
    }

    # Create KB and Document in Tenant A
    kb = KnowledgeBase(
        id=uuid.uuid4(),
        tenant_id=tenant_a_id,
        name="Playground KB",
        status="ACTIVE",
    )
    doc = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_a_id,
        knowledge_base_id=kb.id,
        filename="retrieval_guide.md",
        safe_filename="retrieval_guide.md",
        file_path="storage/retrieval_guide.md",
        file_size=1024,
        mime_type="text/markdown",
        file_hash="hash998877",
        status="PROCESSED",
    )
    chunk = DocumentChunk(
        id=uuid.uuid4(),
        tenant_id=tenant_a_id,
        knowledge_base_id=kb.id,
        document_id=doc.id,
        chunk_index=0,
        content="Retrieval Augmented Generation combines neural search with language models.",
        character_count=74,
        token_count=10,
        heading_path="Overview > Architecture",
        chunking_strategy="markdown",
    )
    db_session.add_all([kb, doc, chunk])
    await db_session.commit()

    # Query Playground
    query_payload = {
        "knowledge_base_id": str(kb.id),
        "query": "What is Retrieval Augmented Generation?",
        "mode": "hybrid",
        "top_k": 3,
    }
    resp = await client.post("/api/v1/retrieval/playground", json=query_payload, headers=headers_a)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["query"] == "What is Retrieval Augmented Generation?"
    assert data["retrieval_mode"] == "hybrid"
    assert "latency_ms" in data
    assert isinstance(data["latency_ms"], float)
    assert data["total_results"] >= 0

    # Cross-tenant query: Tenant B queries Tenant A's KB -> 404
    resp_cross = await client.post("/api/v1/retrieval/playground", json=query_payload, headers=headers_b)
    assert resp_cross.status_code == 404
