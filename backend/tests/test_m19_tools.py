"""Comprehensive acceptance test suite for M19 — Organization Collaboration & Custom Tool Foundations."""

import socket
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.group_repository import GroupRepository
from app.repositories.member_repository import MemberRepository
from app.services.tools.builtin import (
    CalculatorSecurityError,
    safe_calculate,
    synthetic_weather_lookup,
)
from app.services.tools.registry import ToolRegistryService
from app.services.tools.ssrf import SSRFSecurityError, validate_outbound_url


def _mock_dns_resolver(host, port=None, *args, **kwargs):
    """Simulate DNS resolution: local/private IPs return themselves, synthetic domains return public IP."""
    h = str(host).lower().strip()
    if h in ("127.0.0.1", "localhost", "127.0.0.2", "0.0.0.0", "10.0.0.1", "172.16.0.1", "192.168.1.1", "169.254.169.254"):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (h, port or 0))]
    # Public IP for example.com
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port or 0))]


def test_ssrf_security_boundary_blocks_dangerous_targets():
    """Verify SSRF validator blocks loopback, RFC1918 private IPs, link-local, cloud metadata, and URL creds."""
    dangerous_urls = [
        "http://localhost:8000/api",
        "http://127.0.0.1:3000/internal",
        "http://127.0.0.2:8080",
        "http://0.0.0.0/",
        "http://10.0.0.1/admin",
        "http://172.16.0.1/metrics",
        "http://192.168.1.1/router",
        "http://169.254.169.254/latest/meta-data/",  # Cloud metadata
        "http://admin:secret@trusted-api.com/v1",   # Credential in URL
        "ftp://example.com/file",                  # Non-HTTP/HTTPS
        "file:///etc/passwd",                      # File protocol
    ]

    with patch("socket.getaddrinfo", side_effect=_mock_dns_resolver):
        for url in dangerous_urls:
            with pytest.raises(SSRFSecurityError):
                validate_outbound_url(url)


def test_ssrf_validator_allows_valid_public_domain():
    """Verify SSRF validator allows legitimate public hostnames."""
    valid_urls = [
        "https://api.github.com/users",
        "https://httpbin.org/get",
        "https://example.com/test",
    ]
    with patch("socket.getaddrinfo", side_effect=_mock_dns_resolver):
        for url in valid_urls:
            res = validate_outbound_url(url)
            assert res.startswith("https://")


def test_safe_builtin_calculator():
    """Verify safe AST calculator evaluates valid math and rejects malicious/excessive inputs."""
    # Valid evaluations
    assert safe_calculate("2 + 2") == 4
    assert safe_calculate("(10 + 5) * 3 - 5") == 40
    assert safe_calculate("100 / 4") == 25.0
    assert safe_calculate("2 ** 8") == 256
    assert safe_calculate("-5 + 10") == 5

    # Malicious or dangerous expressions
    with pytest.raises(CalculatorSecurityError):
        safe_calculate("__import__('os').system('ls')")

    with pytest.raises(CalculatorSecurityError):
        safe_calculate("open('/etc/passwd').read()")

    with pytest.raises(CalculatorSecurityError):
        safe_calculate("2 ** 1000000000")  # DoS exponentiation

    with pytest.raises(CalculatorSecurityError):
        safe_calculate("eval('1 + 1')")

    with pytest.raises(CalculatorSecurityError):
        safe_calculate("a + b")  # Non-numeric constant/variable


def test_synthetic_weather_lookup():
    """Verify synthetic weather tool returns structured data for supported cities and handles unknown cities."""
    tokyo = synthetic_weather_lookup("Tokyo")
    assert tokyo["city"] == "Tokyo"
    assert "temperature_c" in tokyo
    assert "condition" in tokyo

    sf = synthetic_weather_lookup("San Francisco")
    assert sf["city"] == "San Francisco"
    assert "temperature_c" in sf

    unknown = synthetic_weather_lookup("Atlantis")
    assert unknown["city"] == "Atlantis"
    assert "temperature_c" in unknown


@pytest.mark.asyncio
async def test_group_membership_lifecycle_and_cross_tenant_isolation(
    seed_data: dict, db_session: AsyncSession
):
    """Verify group member addition, listing, deletion, and cross-tenant isolation constraints."""
    tenant_a = seed_data["tenant_a"]
    tenant_b = seed_data["tenant_b"]
    user_a_emp = seed_data["user_a_employee"]
    user_b_emp = seed_data["user_b_employee"]

    member_repo_a = MemberRepository(db_session, tenant_a.id)
    membership_a = await member_repo_a.get_by_user_id(user_a_emp.id)
    assert membership_a is not None

    member_repo_b = MemberRepository(db_session, tenant_b.id)
    membership_b = await member_repo_b.get_by_user_id(user_b_emp.id)
    assert membership_b is not None

    group_repo_a = GroupRepository(db_session, tenant_a.id)
    group_repo_b = GroupRepository(db_session, tenant_b.id)

    # 1. Create a group in Tenant A
    group_a = await group_repo_a.create(name="AI Platform Engineers", description="Engineering team")
    assert group_a.id is not None

    # 2. Add valid Tenant A member to Group A
    enrollment = await group_repo_a.add_member(group_a.id, membership_a.id)
    assert enrollment.group_id == group_a.id
    assert enrollment.membership_id == membership_a.id

    # 3. List members of Group A
    members = await group_repo_a.list_members(group_a.id)
    assert len(members) == 1
    enr, mem, usr = members[0]
    assert enr.id == enrollment.id
    assert mem.id == membership_a.id

    # 4. CROSS-TENANT NEGATIVE: Attempt to add Tenant B member to Tenant A's group
    with pytest.raises(ValueError, match="Membership not found in active workspace"):
        await group_repo_a.add_member(group_a.id, membership_b.id)

    # 5. CROSS-TENANT NEGATIVE: Tenant B repository cannot list or access Tenant A's group
    members_b_view = await group_repo_b.list_members(group_a.id)
    assert len(members_b_view) == 0

    # 6. Remove member from Group A
    removed = await group_repo_a.remove_member(group_a.id, membership_a.id)
    assert removed is True
    members_after = await group_repo_a.list_members(group_a.id)
    assert len(members_after) == 0


@pytest.mark.asyncio
async def test_tool_registry_builtin_and_custom_tools(
    seed_data: dict, db_session: AsyncSession
):
    """Verify tool discovery, custom HTTP registration, and cross-tenant isolation in ToolRegistryService."""
    tenant_a = seed_data["tenant_a"]
    tenant_b = seed_data["tenant_b"]

    svc_a = ToolRegistryService(db_session, tenant_a.id)
    svc_b = ToolRegistryService(db_session, tenant_b.id)

    # 1. List tools (includes builtins: calculator and weather_lookup)
    tools_a = await svc_a.list_tools()
    tool_names = [t["name"] for t in tools_a]
    assert "calculator" in tool_names
    assert "weather_lookup" in tool_names

    # 2. Execute built-in calculator through registry
    calc_res = await svc_a.execute_tool("builtin_calculator", {"expression": "10 * 5 + 2"})
    assert calc_res["result"] == 52

    # 3. Register custom HTTP tool in Tenant A
    with patch("socket.getaddrinfo", side_effect=_mock_dns_resolver):
        custom_tool = await svc_a.create_custom_tool(
            name="crm_customer_lookup",
            display_name="CRM Customer Lookup",
            endpoint_url="https://api.example.com/customers",
            description="Lookup customer details by ID",
            method="POST",
            input_schema={"type": "object", "properties": {"customer_id": {"type": "string"}}},
            output_schema={"type": "object"},
            risk_level="READ_ONLY",
            requires_approval=False,
        )
    assert custom_tool.id is not None
    assert custom_tool.tenant_id == tenant_a.id

    # 4. CROSS-TENANT NEGATIVE: Tenant B cannot see or get Tenant A's custom tool
    tools_b = await svc_b.list_tools()
    tools_b_names = [t["name"] for t in tools_b]
    assert "crm_customer_lookup" not in tools_b_names

    tool_from_b = await svc_b.get_tool(str(custom_tool.id))
    assert tool_from_b is None

    # 5. Mock HTTP Execution of Custom Tool
    mock_resp = Response(
        status_code=200,
        json={"customer_id": "cust_123", "name": "Acme Corp", "tier": "Enterprise"},
        request=AsyncMock(),
    )
    with patch("socket.getaddrinfo", side_effect=_mock_dns_resolver):
        with patch("httpx.AsyncClient.send", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = mock_resp
            exec_res = await svc_a.execute_tool(str(custom_tool.id), {"customer_id": "cust_123"})
            assert exec_res["status_code"] == 200
            assert exec_res["data"]["tier"] == "Enterprise"



@pytest.mark.asyncio
async def test_tools_api_endpoints_and_cross_tenant_denial(
    client: AsyncClient,
    seed_data: dict,
):
    """Verify HTTP API endpoints for tools with tenant isolation and SSRF block."""
    headers_a = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(seed_data["tenant_a"].id),
    }
    headers_b = {
        "Authorization": f"Bearer {seed_data['token_b_owner']}",
        "X-Tenant-ID": str(seed_data["tenant_b"].id),
    }

    # 1. List tools via API for Tenant A
    resp = await client.get("/api/v1/tools", headers=headers_a)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 2
    assert any(t["name"] == "calculator" for t in items)

    # 2. SSRF Denied on creation: attempt to point to localhost
    with patch("socket.getaddrinfo", side_effect=_mock_dns_resolver):
        bad_payload = {
            "name": "internal_scanner",
            "display_name": "Internal Scanner",
            "endpoint_url": "http://127.0.0.1:8000/internal-secrets",
            "method": "GET",
        }
        bad_resp = await client.post("/api/v1/tools", json=bad_payload, headers=headers_a)
        assert bad_resp.status_code == 400
        assert "Security violation" in bad_resp.json()["detail"]

        # 3. Create valid custom tool in Tenant A
        good_payload = {
            "name": "order_api",
            "display_name": "Order Status API",
            "endpoint_url": "https://orders.example.com/status",
            "method": "POST",
        }
        create_resp = await client.post("/api/v1/tools", json=good_payload, headers=headers_a)
        assert create_resp.status_code == 201
        tool_id = create_resp.json()["id"]

        # 4. CROSS-TENANT NEGATIVE: Tenant B tries to retrieve Tenant A's tool
        cross_resp = await client.get(f"/api/v1/tools/{tool_id}", headers=headers_b)
        assert cross_resp.status_code == 404

        # 5. CROSS-TENANT NEGATIVE: Tenant B tries to delete Tenant A's tool
        cross_del = await client.delete(f"/api/v1/tools/{tool_id}", headers=headers_b)
        assert cross_del.status_code == 404

        # 6. Tenant A executes built-in calculator
        exec_calc = await client.post(
            "/api/v1/tools/builtin_calculator/execute",
            json={"arguments": {"expression": "25 * 4"}},
            headers=headers_a,
        )
        assert exec_calc.status_code == 200
        assert exec_calc.json()["data"]["result"] == 100

        # 7. Tenant A deletes custom tool
        del_resp = await client.delete(f"/api/v1/tools/{tool_id}", headers=headers_a)
        assert del_resp.status_code == 204
