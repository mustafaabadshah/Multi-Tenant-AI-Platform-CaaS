"""Comprehensive acceptance and security test suite for M20 — MCP Integrations, Tool Calling & Agentic Runtime."""

import socket
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assistant_runtime.runtime import AssistantRuntime
from app.models.assistant import Assistant
from app.models.conversation import Conversation, Message
from app.models.mcp import MCPConnection, ToolApproval, ToolInvocationLog
from app.services.mcp.client import MCPClientError, MCPClientService
from app.services.tools.approval_service import ToolApprovalService
from app.services.tools.ssrf import SSRFSecurityError


def _mock_dns_resolver(host, port=None, *args, **kwargs):
    """Simulate DNS resolution: local/private IPs return themselves, synthetic domains return public IP."""
    h = str(host).lower().strip()
    if h in ("127.0.0.1", "localhost", "127.0.0.2", "0.0.0.0", "10.0.0.1", "172.16.0.1", "192.168.1.1", "169.254.169.254"):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (h, port or 0))]
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port or 0))]


@pytest.mark.asyncio
async def test_mcp_connection_ssrf_boundary_and_tenant_isolation(
    client: AsyncClient,
    seed_data: dict,
):
    """Verify MCP registration blocks SSRF targets and enforces strict tenant isolation."""
    headers_a = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(seed_data["tenant_a"].id),
    }
    headers_b = {
        "Authorization": f"Bearer {seed_data['token_b_owner']}",
        "X-Tenant-ID": str(seed_data["tenant_b"].id),
    }

    # 1. SSRF Negative: attempt to point to localhost or metadata endpoint
    bad_payloads = [
        {"display_name": "Internal DB", "server_url": "http://127.0.0.1:5432/mcp"},
        {"display_name": "AWS Metadata", "server_url": "http://169.254.169.254/latest/meta-data/"},
        {"display_name": "Docker Host", "server_url": "http://localhost:8080/sse"},
    ]
    with patch("socket.getaddrinfo", side_effect=_mock_dns_resolver):
        for bad_p in bad_payloads:
            resp = await client.post("/api/v1/mcp/connections", json=bad_p, headers=headers_a)
            assert resp.status_code == 400
            assert "Security violation" in resp.json()["detail"]

    # 2. Register legitimate remote HTTPS MCP server in Tenant A
    good_payload = {
        "display_name": "Stripe Payments MCP",
        "server_url": "https://mcp.stripe.example.com/sse",
        "auth_mode": "BEARER_TOKEN",
        "credential": "mcp_sk_live_synthetic_token_12345",
    }
    with patch("socket.getaddrinfo", side_effect=_mock_dns_resolver):
        create_resp = await client.post("/api/v1/mcp/connections", json=good_payload, headers=headers_a)
        assert create_resp.status_code == 201
        conn_data = create_resp.json()
        conn_id = conn_data["id"]
        assert conn_data["display_name"] == "Stripe Payments MCP"
        assert conn_data["server_url"].startswith("https://")

    # 3. CROSS-TENANT NEGATIVE: Tenant B cannot list or get Tenant A's MCP connection
    list_b = await client.get("/api/v1/mcp/connections", headers=headers_b)
    assert list_b.status_code == 200
    assert not any(c["id"] == conn_id for c in list_b.json())

    get_b = await client.get(f"/api/v1/mcp/connections/{conn_id}", headers=headers_b)
    assert get_b.status_code == 404

    # 4. CROSS-TENANT NEGATIVE: Tenant B cannot delete Tenant A's MCP connection
    del_b = await client.delete(f"/api/v1/mcp/connections/{conn_id}", headers=headers_b)
    assert del_b.status_code == 404


def test_mcp_client_tool_risk_inference_and_schema_fingerprint():
    """Verify tool risk classification heuristics and deterministic SHA-256 fingerprinting."""
    schema_1 = {"type": "object", "properties": {"account_id": {"type": "string"}}}
    schema_2 = {"properties": {"account_id": {"type": "string"}}, "type": "object"}

    fp1 = MCPClientService.calculate_schema_fingerprint(schema_1)
    fp2 = MCPClientService.calculate_schema_fingerprint(schema_2)
    assert fp1 == fp2  # Deterministic sorting

    risk_read, appr_read = MCPClientService.infer_tool_risk("get_balance", "Retrieve current balance")
    assert risk_read == "READ_ONLY"
    assert appr_read is False

    risk_write, appr_write = MCPClientService.infer_tool_risk("create_invoice", "Create a new draft invoice")
    assert risk_write == "WRITE"
    assert appr_write is True

    risk_high, appr_high = MCPClientService.infer_tool_risk("execute_wire_transfer", "Transfer funds externally")
    assert risk_high == "HIGH_RISK"
    assert appr_high is True


@pytest.mark.asyncio
async def test_mcp_tool_discovery_mock():
    """Verify MCP tools/list protocol handling and schema fingerprint generation."""
    mock_tools_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "tools": [
                {
                    "name": "lookup_user",
                    "description": "Look up user details by email",
                    "inputSchema": {"type": "object", "properties": {"email": {"type": "string"}}},
                },
                {
                    "name": "delete_account",
                    "description": "Permanently delete user account",
                    "inputSchema": {"type": "object", "properties": {"user_id": {"type": "string"}}},
                },
            ]
        },
    }
    mock_resp = Response(status_code=200, json=mock_tools_payload, request=AsyncMock())

    with patch("socket.getaddrinfo", side_effect=_mock_dns_resolver):
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            tools = await MCPClientService.discover_tools("https://mcp.example.com/sse")
            assert len(tools) == 2

            t1 = next(t for t in tools if t["name"] == "lookup_user")
            assert t1["risk_level"] == "READ_ONLY"
            assert t1["requires_approval"] is False
            assert "schema_fingerprint" in t1

            t2 = next(t for t in tools if t["name"] == "delete_account")
            assert t2["risk_level"] == "HIGH_RISK"
            assert t2["requires_approval"] is True


@pytest.mark.asyncio
async def test_human_approval_service_lifecycle_and_replay_rejection(
    seed_data: dict,
    db_session: AsyncSession,
):
    """Verify human approval creation, single-use token consumption, and replay rejection."""
    tenant_a = seed_data["tenant_a"]
    user_a = seed_data["user_a_owner"]
    user_b = seed_data["user_b_owner"]

    approval_svc_a = ToolApprovalService(db_session, tenant_a.id)

    dummy_conv_id = uuid.uuid4()
    dummy_asst_id = uuid.uuid4()

    # Need DB conversation & assistant records for foreign keys
    asst = Assistant(
        id=dummy_asst_id,
        tenant_id=tenant_a.id,
        name="Agentic Bot",
        slug="agentic-bot-appr",
        llm_provider="mock",
    )
    db_session.add(asst)

    conv = Conversation(
        id=dummy_conv_id,
        tenant_id=tenant_a.id,
        assistant_id=asst.id,
        user_id=user_a.id,
        title="Agentic Test",
    )
    db_session.add(conv)
    await db_session.commit()

    # 1. Request Approval
    appr = await approval_svc_a.request_approval(
        conversation_id=conv.id,
        assistant_id=asst.id,
        user_id=user_a.id,
        tool_id="builtin_transfer",
        tool_name="execute_transfer",
        arguments={"amount": 5000, "recipient": "Acme Inc"},
    )
    assert appr.status == "PENDING"
    assert appr.approval_token.startswith("appr_")

    # 2. CROSS-USER / CROSS-TENANT NEGATIVE: User B cannot approve User A's tool action
    with pytest.raises(PermissionError):
        await approval_svc_a.approve_and_consume(appr.id, user_id=user_b.id)

    # 3. Legitimate Approval by User A
    approved_appr = await approval_svc_a.approve_and_consume(
        appr.id, user_id=user_a.id, token=appr.approval_token
    )
    assert approved_appr.status == "APPROVED"

    # 4. REPLAY ATTACK REJECTION: Attempting to approve again must fail
    with pytest.raises(ValueError, match="already been approved and executed"):
        await approval_svc_a.approve_and_consume(appr.id, user_id=user_a.id)

    # 5. Mark Consumed
    await approval_svc_a.mark_consumed(appr.id)
    reloaded = await approval_svc_a.get_approval(appr.id)
    assert reloaded.status == "CONSUMED"


@pytest.mark.asyncio
async def test_agentic_tool_execution_flow_in_assistant_runtime(
    seed_data: dict,
    db_session: AsyncSession,
):
    """Verify end-to-end multi-step agent flow: tool call, execution, telemetry logging, and final answer."""
    tenant_a = seed_data["tenant_a"]
    user_a = seed_data["user_a_owner"]

    asst = Assistant(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        name="Tool Using Assistant",
        slug="tool-using-asst",
        llm_provider="mock",
        default_model="mock-gpt",
    )
    db_session.add(asst)

    conv = Conversation(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        assistant_id=asst.id,
        user_id=user_a.id,
        title="Calculator Conversation",
    )
    db_session.add(conv)
    await db_session.commit()

    runtime = AssistantRuntime(
        session=db_session,
        tenant_id=tenant_a.id,
        user_id=user_a.id,
        is_admin=True,
    )

    # Stream chat asking to calculate
    events = []
    async for event_frame in runtime.stream_chat(
        conversation_id=conv.id,
        user_message="Please calculate 25 * 4 for me",
    ):
        events.append(event_frame)

    # Verify SSE Event Lifecycle
    event_str = "".join(events)
    assert "event: tool_call_proposed" in event_str
    assert "event: tool_call_started" in event_str
    assert "event: tool_call_completed" in event_str
    assert "event: token" in event_str
    assert "event: message_complete" in event_str

    # Verify final assistant message was persisted with tool result incorporated
    stmt = (
        select(Message)
        .where(Message.conversation_id == conv.id, Message.sender_type == "assistant")
        .order_by(Message.created_at.desc())
    )
    asst_msg = (await db_session.execute(stmt)).scalar_one()
    assert "The tool execution result is" in asst_msg.content or "100" in asst_msg.content

    # Verify ToolInvocationLog persistence
    log_stmt = (
        select(ToolInvocationLog)
        .where(ToolInvocationLog.conversation_id == conv.id)
    )
    inv_log = (await db_session.execute(log_stmt)).scalar_one_or_none()
    assert inv_log is not None
    assert inv_log.tool_name == "calculator"
    assert inv_log.status == "SUCCESS"
    assert inv_log.duration_ms >= 0


@pytest.mark.asyncio
async def test_agentic_approval_gating_pauses_execution(
    seed_data: dict,
    db_session: AsyncSession,
):
    """Verify that a mutating / high-risk tool call pauses execution and yields tool_approval_required."""
    tenant_a = seed_data["tenant_a"]
    user_a = seed_data["user_a_owner"]

    asst = Assistant(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        name="Action Assistant",
        slug="action-asst",
        llm_provider="mock",
        default_model="mock-gpt",
    )
    db_session.add(asst)

    conv = Conversation(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        assistant_id=asst.id,
        user_id=user_a.id,
        title="Action Approval Conversation",
    )
    db_session.add(conv)

    # Register a high-risk tool requiring approval
    from app.services.tools.registry import ToolRegistryService
    tool_svc = ToolRegistryService(db_session, tenant_a.id)
    with patch("socket.getaddrinfo", side_effect=_mock_dns_resolver):
        high_risk_tool = await tool_svc.create_custom_tool(
            name="transfer_funds",
            display_name="Transfer Funds",
            endpoint_url="https://api.bank.example.com/transfer",
            method="POST",
            risk_level="HIGH_RISK",
            requires_approval=True,
        )
    await db_session.commit()

    runtime = AssistantRuntime(
        session=db_session,
        tenant_id=tenant_a.id,
        user_id=user_a.id,
        is_admin=True,
    )

    events = []
    async for event_frame in runtime.stream_chat(
        conversation_id=conv.id,
        user_message="Please transfer 500 dollars to John",
    ):
        events.append(event_frame)

    event_str = "".join(events)
    # Execution must pause and require human approval
    assert "event: tool_approval_required" in event_str
    assert "tool_call_started" not in event_str  # Must not start before approval!

    # Check pending approval record in PostgreSQL
    approval_svc = ToolApprovalService(db_session, tenant_a.id)
    pending = await approval_svc.list_pending_for_conversation(conv.id)
    assert len(pending) == 1
    assert pending[0].tool_name == "transfer_funds"
    assert pending[0].status == "PENDING"
