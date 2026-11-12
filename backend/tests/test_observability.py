"""Acceptance and Security Test Suite for Platform Observability and Tracing."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.observability.tracer import get_tracer, sanitize_value


def test_tracer_span_lifecycle_and_metrics():
    """Verify trace and span timing, first-token marking, and metrics calculation."""
    tracer = get_tracer()
    tenant_id = uuid.uuid4()
    assistant_id = uuid.uuid4()
    conversation_id = uuid.uuid4()

    trace = tracer.start_trace(
        tenant_id=tenant_id,
        assistant_id=assistant_id,
        assistant_name="Support Bot",
        conversation_id=conversation_id,
        traffic_type="internal",
    )
    assert trace.trace_id.startswith("tr_")
    assert trace.status == "RUNNING"

    # 1. Retrieval Span
    s1 = trace.start_span("retrieval")
    s1.set_attribute("candidate_kbs", 2)
    s1.set_attribute("query", "test question")
    s1.finish(status="COMPLETED")
    assert s1.duration_ms is not None
    assert s1.status == "COMPLETED"

    # 2. Mark First Token
    trace.mark_first_token()
    assert trace.ttft_ms is not None

    # 3. Complete trace
    trace.input_tokens = 50
    trace.output_tokens = 25
    trace.total_tokens = 75
    trace.finish(status="COMPLETED")

    assert trace.total_duration_ms is not None
    assert trace.status == "COMPLETED"

    # 4. Verify ring buffer lookup
    fetched = tracer.get_trace(trace.trace_id, tenant_id)
    assert fetched is not None
    assert fetched.trace_id == trace.trace_id

    # 5. Verify aggregated summary
    summary = tracer.get_metrics_summary(tenant_id)
    assert summary["total_requests"] >= 1
    assert summary["total_tokens"] >= 75
    assert summary["error_rate"] == 0.0


def test_tracer_attribute_redaction():
    """Verify that sensitive API keys, passwords, and tokens are rigorously redacted."""
    raw_key = "sk-abcdef1234567890abcdef"
    live_key = "mmaip_live_9876543210fedcba"
    bearer = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz"
    raw_pwd = "password='SuperSecretPassword123!'"

    assert "[REDACTED_API_KEY]" in sanitize_value(raw_key)
    assert "[REDACTED_API_KEY]" in sanitize_value(live_key)
    assert "[REDACTED_TOKEN]" in sanitize_value(bearer)
    assert "[REDACTED]" in sanitize_value(raw_pwd)

    # Dictionary recursion
    payload = {
        "user": "admin",
        "api_key": raw_key,
        "auth_header": bearer,
        "nested": {"token": live_key, "notes": "normal text"},
    }
    cleaned = sanitize_value(payload)
    assert "api_key" not in cleaned  # Stripped sensitive key
    assert "auth_header" not in cleaned
    assert "token" not in cleaned["nested"]
    assert cleaned["nested"]["notes"] == "normal text"


@pytest.mark.asyncio
async def test_observability_api_and_cross_tenant_isolation(
    client: AsyncClient, seed_data: dict, db_session: AsyncSession
):
    """Test observability API endpoints and cross-tenant trace isolation."""
    tenant_a = seed_data["tenant_a"]
    tenant_b = seed_data["tenant_b"]
    headers_a = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(tenant_a.id),
    }
    headers_b = {
        "Authorization": f"Bearer {seed_data['token_b_owner']}",
        "X-Tenant-ID": str(tenant_b.id),
    }

    tracer = get_tracer()
    # Create trace for Tenant A
    trace_a = tracer.start_trace(
        tenant_id=tenant_a.id,
        assistant_id=uuid.uuid4(),
        assistant_name="Tenant A Bot",
        conversation_id=uuid.uuid4(),
        traffic_type="developer",
    )
    trace_a.finish(status="COMPLETED")

    # 1. Tenant A lists traces
    resp = await client.get("/api/v1/observability/traces", headers=headers_a)
    assert resp.status_code == 200
    traces = resp.json()
    assert any(t["trace_id"] == trace_a.trace_id for t in traces)

    # 2. Tenant A gets trace detail
    detail_resp = await client.get(f"/api/v1/observability/traces/{trace_a.trace_id}", headers=headers_a)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["trace_id"] == trace_a.trace_id

    # 3. Tenant A gets metrics summary
    metrics_resp = await client.get("/api/v1/observability/metrics", headers=headers_a)
    assert metrics_resp.status_code == 200
    metrics = metrics_resp.json()
    assert "total_requests" in metrics
    assert "avg_latency_ms" in metrics

    # 4. CROSS-TENANT SECURITY: Tenant B attempts to access Tenant A's trace -> 404
    cross_resp = await client.get(f"/api/v1/observability/traces/{trace_a.trace_id}", headers=headers_b)
    assert cross_resp.status_code == 404
