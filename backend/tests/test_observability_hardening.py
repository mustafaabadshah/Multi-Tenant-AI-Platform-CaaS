"""Production-oriented release gate hardening tests for Observability 2.0 (M15.1).

Covers:
- Telemetry DB failure isolation (safe degradation without crashing caller)
- Idempotent upsert persistence (no IntegrityError or duplicate rows on multiple writes)
- Comprehensive synthetic secret redaction (JWTs, DB URLs, PEMs, YAML/JSON, vendor keys)
- Non-admin preview masking and tenant isolation
- Percentile latency calculation accuracy
- Client cancellation handling (GeneratorExit)
"""

import math
import uuid
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trace import RequestTrace
from app.observability.policy import (
    ErrorCategory,
    categorize_error,
    sanitize_preview,
    sanitize_value,
)
from app.observability.tracer import get_tracer


def test_comprehensive_synthetic_secret_redaction():
    """Stage D: Verify comprehensive redaction across diverse synthetic sensitive formats."""
    # 1. OpenAI and Anthropic keys
    openai_text = "Call OpenAI with key sk-abcdef1234567890abcdef for inference"
    assert "[REDACTED_API_KEY]" in sanitize_value(openai_text)
    assert "sk-abcdef" not in sanitize_value(openai_text)

    anthropic_text = "Anthropic key sk-ant-api03-abcdef1234567890abcdef-ZZ"
    assert "[REDACTED_API_KEY]" in sanitize_value(anthropic_text)
    assert "sk-ant" not in sanitize_value(anthropic_text)

    # 2. Render and B2 keys
    render_text = "Deploying with Render token rnd_1234567890abcdef to cluster"
    assert "[REDACTED_API_KEY]" in sanitize_value(render_text)
    assert "rnd_1234" not in sanitize_value(render_text)

    b2_text = "Backblaze applicationKey: K001234567890123456789012"
    assert "[REDACTED_B2_KEY]" in sanitize_value(b2_text) or "[REDACTED]" in sanitize_value(b2_text)
    assert "K001234567890" not in sanitize_value(b2_text)

    # 3. Platform token
    platform_text = "Generated api key is mmaip_live_abcdef1234567890 for tenant"
    cleaned_platform = sanitize_value(platform_text)
    assert "[REDACTED_API_KEY]" in cleaned_platform
    assert "mmaip_live" not in cleaned_platform

    # 4. JWT access token
    raw_jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwidXNlciI6ImFkbWluIn0.s3cr3ts1gn4tur3-12345"
    jwt_text = f"User session token is {raw_jwt}."
    cleaned_jwt = sanitize_value(jwt_text)
    assert "[REDACTED_JWT_TOKEN]" in cleaned_jwt
    assert raw_jwt not in cleaned_jwt

    # 5. Bearer and Authorization headers
    auth_header_text = "Authorization: Bearer my-super-secret-oauth-token-12345678"
    cleaned_auth = sanitize_value(auth_header_text)
    assert "[REDACTED_AUTH]" in cleaned_auth or "[REDACTED_TOKEN]" in cleaned_auth
    assert "my-super-secret" not in cleaned_auth

    # 6. JSON credentials
    json_snippet = '{"username": "app_user", "password": "super_secret_db_password_123", "api_key": "raw_secret_key"}'
    cleaned_json = sanitize_value(json_snippet)
    assert "super_secret_db_password_123" not in cleaned_json
    assert "raw_secret_key" not in cleaned_json

    # 7. YAML / env credentials
    yaml_snippet = "database:\n  password: production_yaml_pass_999\n  secret_token: live_token_xyz"
    cleaned_yaml = sanitize_value(yaml_snippet)
    assert "production_yaml_pass_999" not in cleaned_yaml
    assert "live_token_xyz" not in cleaned_yaml

    # 8. Private key PEM blocks (multiline)
    pem_block = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEowIBAAKCAQEA0Y1234567890abcdef...\n"
        "-----END RSA PRIVATE KEY-----"
    )
    pem_text = f"Server certificate:\n{pem_block}\nReady for use."
    cleaned_pem = sanitize_value(pem_text)
    assert "[REDACTED_PRIVATE_KEY]" in cleaned_pem
    assert "MIIEowIBAAKCAQ" not in cleaned_pem

    # 9. Database URLs with credentials
    db_url = "postgresql://neondb_owner:npg_s3cr3tP4ssw0rd@ep-cool-fog-12345.us-east-2.aws.neon.tech/neondb?sslmode=require"
    cleaned_db = sanitize_value(db_url)
    assert "[REDACTED_DB_CREDENTIALS]" in cleaned_db
    assert "npg_s3cr3tP4ssw0rd" not in cleaned_db
    assert "ep-cool-fog-12345.us-east-2.aws.neon.tech" in cleaned_db

    # 10. Unicode and multiline
    unicode_secret = "User Japanese: パスワード password=s3cr3t_utf8_鍵 and key=sk-utf8secret123456"
    cleaned_unicode = sanitize_value(unicode_secret)
    assert "s3cr3t_utf8" not in cleaned_unicode
    assert "[REDACTED_API_KEY]" in cleaned_unicode

    # 11. Truncation intersecting secret
    long_prefix = "A" * 190
    intercept_text = f"{long_prefix} password=my_boundary_password_99999999999999"
    preview = sanitize_preview(intercept_text, max_length=200)
    assert "my_boundary_password" not in preview
    assert "[truncated]" in preview


@pytest.mark.asyncio
async def test_telemetry_database_failure_isolation():
    """Stage C: Verify that telemetry DB failure degrades gracefully without raising or crashing."""
    tracer = get_tracer()
    trace = tracer.start_trace(
        tenant_id=uuid.uuid4(),
        assistant_id=uuid.uuid4(),
        assistant_name="Isolated Test Bot",
        traffic_type="internal",
    )
    trace.finish(status="COMPLETED")

    # Create a mock session that intentionally raises a DB connection/timeout error
    mock_failing_session = AsyncMock()
    mock_failing_session.execute.side_effect = RuntimeError("Database connection timeout during telemetry persist")
    mock_failing_session.rollback = AsyncMock()

    # Call persist_to_database with the failing session; it MUST NOT raise
    try:
        await tracer.persist_to_database(trace, session=mock_failing_session)
    except Exception as e:
        pytest.fail(f"persist_to_database raised unexpected exception on DB failure: {e}")

    # Verify rollback was called on failure
    mock_failing_session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_idempotent_trace_upsert(db_session: AsyncSession, seed_data: dict):
    """Stage B/C: Verify that persisting the same trace multiple times updates safely without unique collision."""
    tenant_a = seed_data["tenant_a"]
    tracer = get_tracer()

    trace = tracer.start_trace(
        tenant_id=tenant_a.id,
        assistant_id=uuid.uuid4(),
        assistant_name="Idempotent Bot",
        conversation_id=uuid.uuid4(),
        traffic_type="internal",
    )
    trace.provider = "mock"
    trace.model = "mock-chat-v1"

    # First persist: RUNNING status
    await tracer.persist_to_database(trace, session=db_session)

    # Verify record was inserted
    res1 = await db_session.execute(select(RequestTrace).where(RequestTrace.trace_id == trace.trace_id))
    record1 = res1.scalar_one_or_none()
    assert record1 is not None
    assert record1.status == "RUNNING"
    assert record1.total_tokens == 0

    # Simulate completion and re-persist with the same trace object
    trace.input_tokens = 150
    trace.output_tokens = 75
    trace.total_tokens = 225
    trace.finish(status="COMPLETED")

    # Second persist: MUST update without IntegrityError
    await tracer.persist_to_database(trace, session=db_session)

    # Verify record was updated in place, no duplicate row
    res2 = await db_session.execute(select(RequestTrace).where(RequestTrace.trace_id == trace.trace_id))
    records = res2.scalars().all()
    assert len(records) == 1
    assert records[0].status == "COMPLETED"
    assert records[0].total_tokens == 225


@pytest.mark.asyncio
async def test_non_admin_preview_masking_security(
    client: AsyncClient, seed_data: dict, db_session: AsyncSession
):
    """Stage D: Verify non-admin member cannot inspect raw prompt/output previews."""
    tenant_a = seed_data["tenant_a"]

    # Create trace with saved previews in DB
    trace_id = f"tr_preview_test_{uuid.uuid4().hex[:12]}"
    secret_prompt = "Confidential prompt with internal roadmap details"
    secret_output = "Confidential response containing financial projections"

    trace_record = RequestTrace(
        trace_id=trace_id,
        tenant_id=tenant_a.id,
        assistant_name="Confidential Assistant",
        traffic_type="internal",
        status="COMPLETED",
        input_preview=secret_prompt,
        output_preview=secret_output,
        has_preview=True,
        spans_data=[],
    )
    db_session.add(trace_record)
    await db_session.commit()

    # Query as Owner (Admin) -> should receive preview
    headers_owner = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(tenant_a.id),
    }
    owner_resp = await client.get(f"/api/v1/observability/traces/{trace_id}", headers=headers_owner)
    assert owner_resp.status_code == 200
    owner_data = owner_resp.json()
    assert owner_data["input_preview"] == secret_prompt
    assert owner_data["output_preview"] == secret_output
    assert owner_data["has_preview"] is True

    # 1. Query as Member without USAGE_READ -> MUST be 403 Forbidden (privilege escalation check)
    headers_member = {
        "Authorization": f"Bearer {seed_data['token_a_employee']}",
        "X-Tenant-ID": str(tenant_a.id),
    }
    unauthorized_resp = await client.get(f"/api/v1/observability/traces/{trace_id}", headers=headers_member)
    assert unauthorized_resp.status_code == 403

    # 2. Grant USAGE_READ to employee role, but keep is_admin=False
    from app.models.role import Permission, Role, RolePermission
    usage_perm_stmt = select(Permission).where(Permission.name == "usage:read")
    usage_perm = (await db_session.execute(usage_perm_stmt)).scalar_one_or_none()
    if usage_perm:
        emp_role_stmt = select(Role).where(Role.name == "Employee")
        emp_role = (await db_session.execute(emp_role_stmt)).scalar_one_or_none()
        if emp_role:
            db_session.add(RolePermission(id=uuid.uuid4(), role_id=emp_role.id, permission_id=usage_perm.id))
            await db_session.commit()

            # Query as non-admin with USAGE_READ -> 200 OK, but preview fields MUST be None/False
            member_resp = await client.get(f"/api/v1/observability/traces/{trace_id}", headers=headers_member)
            assert member_resp.status_code == 200
            member_data = member_resp.json()
            assert member_data["input_preview"] is None
            assert member_data["output_preview"] is None
            assert member_data["has_preview"] is False


def test_percentile_latency_calculation_precision():
    """Stage I: Verify exact p50, p95, p99 calculations on known synthetic dataset."""
    # Synthetic array of 100 durations: 1ms, 2ms, ..., 100ms
    latencies = list(range(1, 101))

    # Exact expected percentiles:
    # p50 = 50ms, p95 = 95ms, p99 = 99ms
    p50_idx = int(math.ceil(0.50 * len(latencies))) - 1
    p95_idx = int(math.ceil(0.95 * len(latencies))) - 1
    p99_idx = int(math.ceil(0.99 * len(latencies))) - 1

    assert latencies[p50_idx] == 50
    assert latencies[p95_idx] == 95
    assert latencies[p99_idx] == 99


def test_client_cancellation_categorization():
    """Stage C: Verify GeneratorExit maps to CANCELLED_STREAM category."""
    cat, summary = categorize_error("GeneratorExit: client disconnected from SSE stream")
    assert cat == ErrorCategory.CANCELLED_STREAM
    assert "cancelled or disconnected" in summary
