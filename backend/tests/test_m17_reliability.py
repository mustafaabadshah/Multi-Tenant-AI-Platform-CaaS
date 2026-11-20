"""Comprehensive acceptance and regression test suite for M17 — Reliability, Durable Quotas & Operations."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import client_identity, scoped_identity
from app.models.administration import QuotaReservation
from app.models.trace import RequestTrace
from app.services.quota_service import QuotaService
from app.storage.local import LocalStorageProvider
from app.storage.s3 import S3StorageProvider


@pytest.mark.asyncio
async def test_durable_quota_reservation_lifecycle(seed_data: dict, db_session: AsyncSession):
    """Verify QuotaReservation lifecycle: creation, active accounting, consumption, and release."""
    tenant = seed_data["tenant_a"]
    quota_svc = QuotaService(db_session, tenant.id)

    quota = await quota_svc.get_or_create_quota()
    quota.monthly_token_limit = 10_000
    await db_session.commit()

    # 1. Reserve 4,000 tokens
    res_1 = await quota_svc.reserve_quota(estimated_tokens=4_000)
    assert res_1.startswith("res_")

    # Verify reservation row in DB
    clean_id_1 = uuid.UUID(res_1.removeprefix("res_"))
    stmt = select(QuotaReservation).where(QuotaReservation.id == clean_id_1)
    db_res = (await db_session.execute(stmt)).scalar_one()
    assert db_res.status == "ACTIVE"
    assert db_res.tokens_reserved == 4_000

    # 2. Reserve another 4,000 tokens (total in-flight: 8,000 <= 10,000)
    res_2 = await quota_svc.reserve_quota(estimated_tokens=4_000)
    assert res_2.startswith("res_")

    # 3. Third reservation for 3,000 tokens should fail (8,000 + 3,000 = 11,000 > 10,000)
    with pytest.raises(HTTPException) as exc_info:
        await quota_svc.reserve_quota(estimated_tokens=3_000)
    assert exc_info.value.status_code == 429
    assert "Monthly token limit exceeded" in exc_info.value.detail

    # 4. Release res_2 asynchronously
    await quota_svc.release_reservation_async(res_2)
    clean_id_2 = uuid.UUID(res_2.removeprefix("res_"))
    db_res_2 = (await db_session.execute(select(QuotaReservation).where(QuotaReservation.id == clean_id_2))).scalar_one()
    assert db_res_2.status == "RELEASED"

    # Now the 3,000 reservation succeeds (4,000 + 3,000 = 7,000 <= 10,000)
    res_3 = await quota_svc.reserve_quota(estimated_tokens=3_000)
    assert res_3.startswith("res_")

    # 5. Consume res_1 into ProviderUsageLog
    usage = await quota_svc.record_usage(
        provider="omniroute",
        model="auto",
        prompt_tokens=2_500,
        completion_tokens=1_000,
        reservation_id=res_1,
    )
    assert usage.total_tokens == 3_500

    # Verify res_1 is now CONSUMED in DB
    await db_session.refresh(db_res)
    assert db_res.status == "CONSUMED"

    # Clean up res_3
    await quota_svc.release_reservation_async(res_3)


@pytest.mark.asyncio
async def test_stale_reservation_expiration(seed_data: dict, db_session: AsyncSession):
    """Verify expired reservations (>300s old) are ignored in quota capacity and marked EXPIRED."""
    tenant = seed_data["tenant_b"]
    quota_svc = QuotaService(db_session, tenant.id)

    quota = await quota_svc.get_or_create_quota()
    quota.monthly_token_limit = 1_000
    await db_session.commit()

    # Manually inject a stale active reservation created 10 minutes ago
    stale_uuid = uuid.uuid4()
    stale_res = QuotaReservation(
        id=stale_uuid,
        tenant_id=tenant.id,
        tokens_reserved=900,
        status="ACTIVE",
        expires_at=datetime.now(UTC) - timedelta(minutes=5),
        created_at=datetime.now(UTC) - timedelta(minutes=10),
    )
    db_session.add(stale_res)
    await db_session.commit()

    # Reserving 500 tokens should succeed because the 900 token reservation has expired
    res_fresh = await quota_svc.reserve_quota(estimated_tokens=500)
    assert res_fresh.startswith("res_")

    # Check that stale reservation was updated to EXPIRED
    await db_session.refresh(stale_res)
    assert stale_res.status == "EXPIRED"

    # Clean up
    await quota_svc.release_reservation_async(res_fresh)


@pytest.mark.asyncio
async def test_observability_postgresql_authoritative_no_fallback(
    client: AsyncClient, seed_data: dict, db_session: AsyncSession
):
    """Verify observability endpoints are PostgreSQL-authoritative and never resurrect memory traces."""
    tenant_a = seed_data["tenant_a"]
    headers_owner = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(tenant_a.id),
    }

    # 1. Empty traces list returns 200 with empty list []
    resp = await client.get("/api/v1/observability/traces", headers=headers_owner)
    assert resp.status_code == 200
    assert resp.json() == []

    # 2. Detail for non-existent trace returns 404
    detail_resp = await client.get("/api/v1/observability/traces/tr_nonexistent_12345", headers=headers_owner)
    assert detail_resp.status_code == 404
    assert "Trace not found" in detail_resp.json()["detail"]

    # 3. Metrics for empty tenant returns zeroed stats
    metrics_resp = await client.get("/api/v1/observability/metrics?period=24h", headers=headers_owner)
    assert metrics_resp.status_code == 200
    metrics = metrics_resp.json()
    assert metrics["total_requests"] == 0
    assert metrics["error_rate"] == 0.0
    assert metrics["total_tokens"] == 0
    assert metrics["estimated_cost_usd"] == 0.0


@pytest.mark.asyncio
async def test_observability_cancellation_separation_and_metrics_aggregation(
    client: AsyncClient, seed_data: dict, db_session: AsyncSession
):
    """Verify CANCELLED traces do NOT count as server errors, and aggregations sum all rows."""
    tenant_a = seed_data["tenant_a"]
    headers_owner = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(tenant_a.id),
    }

    # Create 1 COMPLETED trace
    t1 = RequestTrace(
        trace_id=f"tr_comp_{uuid.uuid4().hex[:12]}",
        tenant_id=tenant_a.id,
        status="COMPLETED",
        traffic_type="internal",
        total_tokens=1_000,
        estimated_cost_usd=0.015,
        total_duration_ms=400.0,
        ttft_ms=120.0,
        spans_data=[],
    )
    # Create 1 CANCELLED trace (client aborted stream)
    t2 = RequestTrace(
        trace_id=f"tr_canc_{uuid.uuid4().hex[:12]}",
        tenant_id=tenant_a.id,
        status="CANCELLED",
        traffic_type="internal",
        total_tokens=200,
        estimated_cost_usd=0.003,
        total_duration_ms=150.0,
        ttft_ms=100.0,
        spans_data=[],
    )
    # Create 1 FAILED trace (actual server/provider error)
    t3 = RequestTrace(
        trace_id=f"tr_fail_{uuid.uuid4().hex[:12]}",
        tenant_id=tenant_a.id,
        status="FAILED",
        error_category="PROVIDER_UNAVAILABLE",
        traffic_type="internal",
        total_tokens=0,
        estimated_cost_usd=0.0,
        total_duration_ms=80.0,
        spans_data=[],
    )
    db_session.add_all([t1, t2, t3])
    await db_session.commit()

    # Query metrics
    metrics_resp = await client.get("/api/v1/observability/metrics?period=24h", headers=headers_owner)
    assert metrics_resp.status_code == 200
    m = metrics_resp.json()
    assert m["total_requests"] == 3
    # 1 FAILED out of 3 total requests = 0.3333 error_rate. CANCELLED is NOT counted in error_rate!
    assert m["error_rate"] == round(1 / 3, 4)
    assert m["by_status"]["COMPLETED"] == 1
    assert m["by_status"]["CANCELLED"] == 1
    assert m["by_status"]["FAILED"] == 1
    assert m["total_tokens"] == 1_200
    assert m["estimated_cost_usd"] == 0.018

    # Test pagination parameters (limit, offset)
    traces_page1 = await client.get("/api/v1/observability/traces?limit=2&offset=0", headers=headers_owner)
    assert traces_page1.status_code == 200
    assert len(traces_page1.json()) == 2

    traces_page2 = await client.get("/api/v1/observability/traces?limit=2&offset=2", headers=headers_owner)
    assert traces_page2.status_code == 200
    assert len(traces_page2.json()) == 1


def test_rate_limit_client_identity_and_scoping():
    """Verify safe proxy handling and composite identity isolation."""
    # 1. Untrusted peer with spoofed X-Forwarded-For is ignored
    req_untrusted = MagicMock()
    req_untrusted.client.host = "198.51.100.25"  # Public untrusted IP
    req_untrusted.headers = {"x-forwarded-for": "203.0.113.195"}
    assert client_identity(req_untrusted) == "198.51.100.25"

    # 2. Local test client peer trusts forwarded header
    req_trusted = MagicMock()
    req_trusted.client.host = "127.0.0.1"
    req_trusted.headers = {"x-forwarded-for": "203.0.113.50, 10.0.0.1"}
    assert client_identity(req_trusted) == "203.0.113.50"

    # 3. Composite scoped identity prevents enterprise NAT sharing
    u1_id = uuid.uuid4()
    u2_id = uuid.uuid4()
    tid = uuid.uuid4()

    key_u1 = scoped_identity(req_untrusted, tenant_id=tid, user_id=u1_id)
    key_u2 = scoped_identity(req_untrusted, tenant_id=tid, user_id=u2_id)
    assert key_u1 != key_u2
    assert f"uid:{u1_id}" in key_u1
    assert f"uid:{u2_id}" in key_u2


def test_storage_key_duplicate_tenant_prefix_handling(tmp_path):
    """Verify S3 and local storage strip repeated tenant prefixes idempotently."""
    tid = "11111111-2222-3333-4444-555555555555"

    # S3 provider key generation
    s3_provider = S3StorageProvider(bucket_name="test-bucket")

    # Clean relative key
    assert s3_provider._get_full_key(tid, "doc1.pdf") == f"{tid}/doc1.pdf"
    # Repeated {tenant_id}/ prefix
    assert s3_provider._get_full_key(tid, f"{tid}/doc1.pdf") == f"{tid}/doc1.pdf"
    # Repeated tenants/{tenant_id}/ prefix
    assert s3_provider._get_full_key(tid, f"tenants/{tid}/doc1.pdf") == f"{tid}/doc1.pdf"

    # Local provider path resolution
    local_provider = LocalStorageProvider(base_dir=str(tmp_path))
    p1 = local_provider._resolve_tenant_path(tid, "doc1.pdf")
    p2 = local_provider._resolve_tenant_path(tid, f"{tid}/doc1.pdf")
    p3 = local_provider._resolve_tenant_path(tid, f"tenants/{tid}/doc1.pdf")
    assert p1 == p2 == p3
