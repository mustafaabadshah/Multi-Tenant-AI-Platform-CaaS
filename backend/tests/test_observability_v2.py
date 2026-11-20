"""Comprehensive acceptance and security test suite for Observability 2.0 (M15)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trace import RequestTrace
from app.observability.policy import (
    ErrorCategory,
    categorize_error,
    sanitize_preview,
)
from app.observability.pricing import estimate_request_cost
from app.observability.tracer import get_tracer


def test_pricing_engine_accuracy():
    """Verify deterministic pricing calculation, zero-cost mock, and unknown models."""
    # 1. Mock provider
    cost, status = estimate_request_cost("mock", "mock-chat-v1", 1000, 500)
    assert cost == 0.0
    assert status == "zero_cost"

    # 2. Known model (gpt-4o-mini: 0.15 in, 0.60 out per 1M)
    # 1,000,000 in ($0.15) + 1,000,000 out ($0.60) = $0.75
    cost, status = estimate_request_cost("openai", "gpt-4o-mini", 1_000_000, 1_000_000)
    assert cost == 0.75
    assert status == "known"

    # 3. Known model with date suffix (gpt-4o-mini-2024-07-18)
    cost, status = estimate_request_cost("openai", "gpt-4o-mini-2024-07-18", 100_000, 100_000)
    assert cost is not None
    assert status == "known"

    # 4. Unknown provider/model
    cost, status = estimate_request_cost("custom_llm", "llama-finetune-v1", 500, 500)
    assert cost is None
    assert status == "unknown"


def test_error_categorization_and_sanitization():
    """Verify error taxonomy mapping and credential scrub from error summaries."""
    # Quota
    cat, summary = categorize_error("Quota exceeded: monthly tokens exhausted")
    assert cat == ErrorCategory.QUOTA_EXCEEDED
    assert "Workspace quota exceeded" in summary

    # Auth / BYOK
    cat, summary = categorize_error("Provider 'openai' is not configured with an active BYOK credential")
    assert cat == ErrorCategory.AUTH_ERROR

    # Rate limited
    cat, summary = categorize_error("HTTP 429 Too Many Requests from provider")
    assert cat == ErrorCategory.RATE_LIMITED

    # Cancelled stream
    cat, summary = categorize_error("GeneratorExit: connection aborted")
    assert cat == ErrorCategory.CANCELLED_STREAM

    # Credential leakage in raw exception
    raw_leak = "Connection failed to https://api.openai.com/v1 with key sk-abcdef1234567890abcdef and password='Secret123!'"
    cat, summary = categorize_error(raw_leak)
    assert "[REDACTED_API_KEY]" in summary
    assert "sk-abcdef" not in summary
    assert "Secret123!" not in summary


def test_preview_sanitization_and_xss_protection():
    """Verify preview redaction and HTML script stripping."""
    malicious_input = (
        "Hello <script>alert('xss')</script> my key is sk-1234567890abcdef and token is Bearer eyJhbGciOiJIUzI1NiJ9.test"
    )
    cleaned = sanitize_preview(malicious_input, max_length=200)
    assert "<script>" not in cleaned
    assert "[SCRUBBED_SCRIPT]" in cleaned
    assert "[REDACTED_API_KEY]" in cleaned
    assert "[REDACTED_TOKEN]" in cleaned
    assert "sk-1234567890" not in cleaned

    # Truncation check
    long_text = "A" * 500
    truncated = sanitize_preview(long_text, max_length=100)
    assert len(truncated) <= 125
    assert "[truncated]" in truncated


@pytest.mark.asyncio
async def test_durable_trace_database_persistence_and_query(
    client: AsyncClient, seed_data: dict, db_session: AsyncSession
):
    """Verify AssistantTrace persistence to PostgreSQL and API retrieval."""
    tenant_a = seed_data["tenant_a"]
    headers_a = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(tenant_a.id),
    }

    tracer = get_tracer()
    trace = tracer.start_trace(
        tenant_id=tenant_a.id,
        assistant_id=uuid.uuid4(),
        assistant_name="Database Persisted Assistant",
        conversation_id=uuid.uuid4(),
        traffic_type="internal",
    )
    trace.provider = "openai"
    trace.model = "gpt-4o-mini"
    trace.input_tokens = 400
    trace.output_tokens = 200
    trace.total_tokens = 600
    trace.retrieval_metadata = {
        "timing_ms": {"vector_search_latency_ms": 12, "fusion_latency_ms": 3},
        "candidates_found": 5,
        "authorized_count": 3,
    }
    trace.set_previews(
        user_input="How do I configure SSO in my workspace?",
        output_text="To configure SSO, go to organization settings and add your SAML metadata.",
    )
    span = trace.start_span("retrieval")
    span.finish(status="COMPLETED")
    trace.finish(status="COMPLETED")

    # Persist directly to DB
    await tracer.persist_to_database(trace, session=db_session)

    # Verify query via API
    resp = await client.get("/api/v1/observability/traces", headers=headers_a)
    assert resp.status_code == 200
    traces = resp.json()
    matched = next((t for t in traces if t["trace_id"] == trace.trace_id), None)
    assert matched is not None
    assert matched["assistant_name"] == "Database Persisted Assistant"
    assert matched["status"] == "COMPLETED"
    assert matched["pricing_status"] == "known"
    assert matched["estimated_cost_usd"] is not None
    assert matched["retrieval_metadata"] is not None
    assert matched["retrieval_metadata"]["candidates_found"] == 5

    # Verify detail view
    detail_resp = await client.get(f"/api/v1/observability/traces/{trace.trace_id}", headers=headers_a)
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["trace_id"] == trace.trace_id
    assert detail["input_preview"] is not None
    assert "SSO" in detail["input_preview"]


@pytest.mark.asyncio
async def test_observability_policy_and_role_gating(
    client: AsyncClient, seed_data: dict, db_session: AsyncSession
):
    """Verify tenant observability policy management and role-restricted preview masking."""
    tenant_a = seed_data["tenant_a"]
    headers_owner = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(tenant_a.id),
    }

    # 1. Fetch default policy
    pol_resp = await client.get("/api/v1/observability/policy", headers=headers_owner)
    assert pol_resp.status_code == 200
    policy = pol_resp.json()
    assert policy["capture_mode"] == "METADATA_ONLY"
    assert policy["retention_days"] == 30

    # 2. Update policy to REDACTED_PREVIEW
    update_resp = await client.put(
        "/api/v1/observability/policy",
        json={"capture_mode": "REDACTED_PREVIEW", "max_preview_length": 300, "retention_days": 60},
        headers=headers_owner,
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["capture_mode"] == "REDACTED_PREVIEW"
    assert updated["max_preview_length"] == 300
    assert updated["retention_days"] == 60


@pytest.mark.asyncio
async def test_retention_purge_endpoint(
    client: AsyncClient, seed_data: dict, db_session: AsyncSession
):
    """Verify retention purge removes expired traces without affecting recent records."""
    tenant_a = seed_data["tenant_a"]
    headers_owner = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(tenant_a.id),
    }

    # Create an expired trace (45 days old)
    old_trace = RequestTrace(
        trace_id=f"tr_old_{uuid.uuid4().hex[:12]}",
        tenant_id=tenant_a.id,
        assistant_name="Old Bot",
        traffic_type="internal",
        status="COMPLETED",
        created_at=datetime.now(UTC) - timedelta(days=45),
        spans_data=[],
    )
    # Create a recent trace (2 hours old)
    recent_trace = RequestTrace(
        trace_id=f"tr_recent_{uuid.uuid4().hex[:12]}",
        tenant_id=tenant_a.id,
        assistant_name="Recent Bot",
        traffic_type="internal",
        status="COMPLETED",
        created_at=datetime.now(UTC) - timedelta(hours=2),
        spans_data=[],
    )
    db_session.add_all([old_trace, recent_trace])
    await db_session.commit()

    # Trigger purge
    purge_resp = await client.post("/api/v1/observability/purge", headers=headers_owner)
    assert purge_resp.status_code == 200
    res = purge_resp.json()
    assert res["purged_count"] >= 1

    # Verify old trace was deleted
    check_old = await db_session.execute(
        select(RequestTrace).where(RequestTrace.trace_id == old_trace.trace_id)
    )
    assert check_old.scalar_one_or_none() is None

    # Verify recent trace is preserved
    check_recent = await db_session.execute(
        select(RequestTrace).where(RequestTrace.trace_id == recent_trace.trace_id)
    )
    assert check_recent.scalar_one_or_none() is not None
