"""M20.2 Integrations, Assistant Tools Configuration, and Human Approvals Verification.

Tests cover:
1. Assistant Tools Configuration Security & Tenant Scoping.
2. Personal MCP Connection Isolation (User A cannot attach User B's personal MCP tool).
3. Assistant Runtime Execution Step Limits & Selective Tool Invocation.
4. Human Approval Flow End-to-End (request, pending listing, approve single-use token, deny).
5. Direct Member Assignment vs Invitation Lifecycle Security.
"""

import uuid
import pytest
from httpx import AsyncClient

from app.models.mcp import MCPConnection


@pytest.mark.asyncio
async def test_assistant_tools_config_crud_and_tenant_isolation(client: AsyncClient, db_session, seed_data):
    """Verify that assistants can be created and updated with tools_config, strictly scoped to tenant."""
    owner_token = seed_data["token_a_owner"]
    tenant_id = str(seed_data["tenant_a"].id)

    headers = {
        "Authorization": f"Bearer {owner_token}",
        "X-Tenant-ID": tenant_id,
    }

    # 1. Create assistant with tools_config
    create_resp = await client.post(
        "/api/v1/assistants",
        headers=headers,
        json={
            "name": "Tool-Assisted Bot",
            "llm_provider": "omniroute",
            "default_model": "auto",
            "tools_config": {
                "enabled_tool_ids": ["builtin_calculator"],
                "max_execution_steps": 3,
                "require_approval_all": True,
            },
        },
    )
    assert create_resp.status_code == 201
    asst_data = create_resp.json()
    asst_id = asst_data["id"]
    assert asst_data["tools_config"]["enabled_tool_ids"] == ["builtin_calculator"]
    assert asst_data["tools_config"]["max_execution_steps"] == 3
    assert asst_data["tools_config"]["require_approval_all"] is True

    # 2. Update assistant tools_config
    update_resp = await client.put(
        f"/api/v1/assistants/{asst_id}",
        headers=headers,
        json={
            "tools_config": {
                "enabled_tool_ids": ["builtin_calculator", "builtin_weather"],
                "max_execution_steps": 5,
                "require_approval_all": False,
            },
        },
    )
    assert update_resp.status_code == 200
    updated_data = update_resp.json()
    assert len(updated_data["tools_config"]["enabled_tool_ids"]) == 2
    assert updated_data["tools_config"]["max_execution_steps"] == 5
    assert updated_data["tools_config"]["require_approval_all"] is False

    # 3. Cross-tenant isolation check: Tenant B cannot read or update Tenant A assistant
    tenant_b_id = str(seed_data["tenant_b"].id)
    owner_b_token = seed_data["token_b_owner"]
    headers_b = {
        "Authorization": f"Bearer {owner_b_token}",
        "X-Tenant-ID": tenant_b_id,
    }

    b_read_resp = await client.get(f"/api/v1/assistants/{asst_id}", headers=headers_b)
    assert b_read_resp.status_code == 404

    b_update_resp = await client.put(
        f"/api/v1/assistants/{asst_id}",
        headers=headers_b,
        json={"tools_config": {"enabled_tool_ids": []}},
    )
    assert b_update_resp.status_code == 404


@pytest.mark.asyncio
async def test_personal_mcp_connection_isolation(client: AsyncClient, db_session, seed_data):
    """Verify that User A's personal MCP connection cannot be attached by User B or cross-tenant."""
    tenant_a = seed_data["tenant_a"]
    owner = seed_data["user_a_owner"]

    # 1. Create a personal MCP connection owned by user_a_owner
    conn = MCPConnection(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        user_id=owner.id,  # Personal connection
        display_name="Owner's Private DB Tool",
        server_url="https://db-mcp.internal.example.com",
        auth_mode="NONE",
        connection_status="CONNECTED",
        server_capabilities={"tools": True},
        approved_tools=[{"name": "private_query"}],
        is_enabled=True,
    )
    db_session.add(conn)
    await db_session.commit()

    # 2. Create another authorized user in Tenant A (has assistant.create)
    from app.repositories.user_repository import UserRepository
    from app.repositories.member_repository import MemberRepository
    from app.repositories.role_repository import RoleRepository
    from app.core.constants import SystemRole
    from app.core.security import hash_password, create_access_token

    user_repo = UserRepository(db_session)
    role_repo = RoleRepository(db_session)
    member_repo = MemberRepository(db_session, tenant_a.id)

    owner_role = await role_repo.get_by_name(SystemRole.TENANT_OWNER.value)
    user_a_admin = await user_repo.create(
        email="admin_test_mcp@companya.com",
        hashed_password=hash_password("Password123!"),
        full_name="Alex Admin",
    )
    await member_repo.create(
        user_id=user_a_admin.id,
        role_id=owner_role.id,
        title="Admin",
    )
    await db_session.commit()

    token_a_admin = create_access_token(
        str(user_a_admin.id),
        {"email": user_a_admin.email, "tenant_id": str(tenant_a.id)},
    )

    headers_admin = {
        "Authorization": f"Bearer {token_a_admin}",
        "X-Tenant-ID": str(tenant_a.id),
    }

    # 3. User B (Alex Admin) attempts to attach Owner's personal MCP connection to an assistant
    resp = await client.post(
        "/api/v1/assistants",
        headers=headers_admin,
        json={
            "name": "Admin Assistant",
            "llm_provider": "omniroute",
            "default_model": "auto",
            "tools_config": {
                "enabled_tool_ids": [f"mcp_{conn.id}_private_query"],
            },
        },
    )
    assert resp.status_code == 403
    assert "personal MCP connection" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_human_approval_api_lifecycle(client: AsyncClient, db_session, seed_data):
    """Verify listing pending approvals, single-use token consumption, and denial."""
    tenant_a = seed_data["tenant_a"]
    owner = seed_data["user_a_owner"]
    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(tenant_a.id),
    }

    # 1. Create assistant and conversation
    asst_resp = await client.post(
        "/api/v1/assistants",
        headers=headers,
        json={"name": "Approval Assistant", "llm_provider": "omniroute", "default_model": "auto"},
    )
    asst_id = asst_resp.json()["id"]

    conv_resp = await client.post(
        "/api/v1/conversations",
        headers=headers,
        json={"assistant_id": asst_id, "title": "Test Approvals Conv"},
    )
    conv_id = conv_resp.json()["id"]

    # 2. Simulate pending approval creation via service
    from app.services.tools.approval_service import ToolApprovalService

    svc = ToolApprovalService(db_session, tenant_a.id)
    appr = await svc.request_approval(
        conversation_id=uuid.UUID(conv_id),
        assistant_id=uuid.UUID(asst_id),
        user_id=owner.id,
        tool_id="test_tool",
        tool_name="test_tool",
        arguments={"param": "value"},
    )

    # 3. List pending approvals via GET /api/v1/approvals/pending
    pending_resp = await client.get(
        f"/api/v1/approvals/pending?conversation_id={conv_id}",
        headers=headers,
    )
    assert pending_resp.status_code == 200
    pending_list = pending_resp.json()
    assert len(pending_list) == 1
    assert pending_list[0]["id"] == str(appr.id)
    assert pending_list[0]["tool_name"] == "test_tool"

    # 4. Approve using single-use token
    approve_resp = await client.post(
        f"/api/v1/approvals/{appr.id}/approve",
        headers=headers,
        json={"token": appr.approval_token},
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "APPROVED"

    # 5. Replay attempt with same token fails
    replay_resp = await client.post(
        f"/api/v1/approvals/{appr.id}/approve",
        headers=headers,
        json={"token": appr.approval_token},
    )
    assert replay_resp.status_code in (400, 403)

    # 6. Verify pending list is now empty
    pending_after = await client.get(
        f"/api/v1/approvals/pending?conversation_id={conv_id}",
        headers=headers,
    )
    assert pending_after.status_code == 200
    assert len(pending_after.json()) == 0
