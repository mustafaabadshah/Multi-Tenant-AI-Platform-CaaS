"""Comprehensive Unit, Integration, and Security Tests for Milestone 04: Assistant Runtime & Conversational RAG."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.assistant_runtime.context import build_rag_context
from app.assistant_runtime.runtime import AssistantRuntime
from app.models.assistant import Assistant, AssistantKnowledgeBase
from app.models.conversation import Conversation, Message
from app.models.knowledge import Document, DocumentChunk, KnowledgeBase
from app.repositories.assistant_repository import AssistantRepository
from app.vectorstores.base import VectorSearchResult


@pytest.mark.asyncio
async def test_assistant_crud_lifecycle(db_session: AsyncSession, seed_data: dict, client: AsyncClient):
    tenant_a = seed_data["tenant_a"]
    token_a = seed_data["token_a_owner"]

    # 1. Create Knowledge Base to connect
    kb = KnowledgeBase(id=uuid.uuid4(), tenant_id=tenant_a.id, name="KB For Assistant", status="ACTIVE")
    db_session.add(kb)
    await db_session.commit()

    # 2. Create Assistant via API
    create_payload = {
        "name": "HR Policy Assistant",
        "description": "Answers employee HR questions",
        "llm_provider": "mock",
        "default_model": "mock-gpt",
        "temperature": 0.5,
        "max_tokens": 512,
        "visibility": "workspace",
        "retrieval_mode": "hybrid",
        "top_k": 3,
        "system_prompt": "You are an HR expert.",
        "knowledge_base_ids": [str(kb.id)],
    }
    resp = await client.post(
        "/api/v1/assistants",
        headers={"Authorization": f"Bearer {token_a}", "X-Tenant-ID": str(tenant_a.id)},
        json=create_payload,
    )
    assert resp.status_code == 201
    asst_data = resp.json()
    asst_id = asst_data["id"]
    assert asst_data["name"] == "HR Policy Assistant"
    assert asst_data["llm_provider"] == "mock"
    assert asst_data["connected_kb_ids"] == [str(kb.id)]

    # 3. Read Assistant
    get_resp = await client.get(
        f"/api/v1/assistants/{asst_id}",
        headers={"Authorization": f"Bearer {token_a}", "X-Tenant-ID": str(tenant_a.id)},
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == asst_id

    # 4. Update Assistant
    update_resp = await client.put(
        f"/api/v1/assistants/{asst_id}",
        headers={"Authorization": f"Bearer {token_a}", "X-Tenant-ID": str(tenant_a.id)},
        json={"name": "HR Senior Policy Assistant", "temperature": 0.2},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "HR Senior Policy Assistant"
    assert update_resp.json()["temperature"] == 0.2

    # 5. Delete Assistant
    del_resp = await client.delete(
        f"/api/v1/assistants/{asst_id}",
        headers={"Authorization": f"Bearer {token_a}", "X-Tenant-ID": str(tenant_a.id)},
    )
    assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_cross_tenant_assistant_isolation(db_session: AsyncSession, seed_data: dict, client: AsyncClient):
    """Security Requirement: Tenant B cannot access or modify Tenant A's assistants."""
    tenant_a = seed_data["tenant_a"]
    tenant_b = seed_data["tenant_b"]
    token_b = seed_data["token_b_owner"]

    # Create Assistant in Tenant A
    repo_a = AssistantRepository(db_session, tenant_a.id)
    asst_a = await repo_a.create_assistant(
        name="Confidential A Assistant",
        default_model="mock-gpt",
    )
    await db_session.commit()

    # Tenant B tries to GET Tenant A's assistant
    resp = await client.get(
        f"/api/v1/assistants/{asst_a.id}",
        headers={"Authorization": f"Bearer {token_b}", "X-Tenant-ID": str(tenant_b.id)},
    )
    assert resp.status_code == 404

    # Tenant B tries to DELETE Tenant A's assistant
    del_resp = await client.delete(
        f"/api/v1/assistants/{asst_a.id}",
        headers={"Authorization": f"Bearer {token_b}", "X-Tenant-ID": str(tenant_b.id)},
    )
    assert del_resp.status_code == 404


@pytest.mark.asyncio
async def test_cross_tenant_conversation_isolation(db_session: AsyncSession, seed_data: dict, client: AsyncClient):
    """Security Requirement: Tenant B cannot read or stream to Tenant A's conversations."""
    tenant_a = seed_data["tenant_a"]
    tenant_b = seed_data["tenant_b"]
    user_a = seed_data["user_a_owner"]
    token_b = seed_data["token_b_owner"]

    repo_a = AssistantRepository(db_session, tenant_a.id)
    asst_a = await repo_a.create_assistant(name="Tenant A Bot")

    conv_a = Conversation(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        user_id=user_a.id,
        assistant_id=asst_a.id,
        title="Tenant A Private Chat",
        status="ACTIVE",
    )
    db_session.add(conv_a)
    await db_session.commit()

    # Tenant B tries to fetch messages from Tenant A's conversation
    resp = await client.get(
        f"/api/v1/conversations/{conv_a.id}/messages",
        headers={"Authorization": f"Bearer {token_b}", "X-Tenant-ID": str(tenant_b.id)},
    )
    assert resp.status_code == 404

    # Tenant B tries to stream to Tenant A's conversation
    stream_resp = await client.post(
        f"/api/v1/conversations/{conv_a.id}/messages/stream",
        headers={"Authorization": f"Bearer {token_b}", "X-Tenant-ID": str(tenant_b.id)},
        json={"content": "Malicious prompt injection"},
    )
    assert stream_resp.status_code == 404


def test_rag_context_builder_budgeting_and_boundaries():
    """Unit test for token budgeting and prompt injection boundaries."""
    results = [
        VectorSearchResult(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            knowledge_base_id=uuid.uuid4(),
            document_title="Employee Leave Policy",
            content="Employees get 20 vacation days annually.",
            page_number=1,
            score=0.92,
            retrieval_source="semantic",
        )
    ]

    history = [
        {"role": "user", "content": "Hello bot"},
        {"role": "assistant", "content": "Hello! How can I assist you today?"},
    ]

    messages, citations = build_rag_context(
        system_prompt="You are a helpful assistant.",
        conversation_history=history,
        current_user_message="How many vacation days do I get?",
        retrieved_results=results,
        max_context_tokens=1000,
    )

    # 1. Verify system message has untrusted boundaries
    sys_msg = messages[0]
    assert sys_msg.role == "system"
    assert "<KNOWLEDGE_BASE_CONTEXT>" in sys_msg.content
    assert "</KNOWLEDGE_BASE_CONTEXT>" in sys_msg.content
    assert "Employees get 20 vacation days annually." in sys_msg.content

    # 2. Verify citations metadata
    assert len(citations) == 1
    assert citations[0]["citation_num"] == 1
    assert citations[0]["document_name"] == "Employee Leave Policy"

    # 3. Verify user message is preserved
    assert messages[-1].role == "user"
    assert messages[-1].content == "How many vacation days do I get?"


@pytest.mark.asyncio
async def test_end_to_end_conversational_rag_with_citations(db_session: AsyncSession, seed_data: dict):
    """End-to-End RAG test: Knowledge Base -> Assistant -> Conversation -> Streaming RAG -> Citations."""
    tenant_a = seed_data["tenant_a"]
    user_a = seed_data["user_a_owner"]

    # 1. Create Knowledge Base and Document Chunk
    kb = KnowledgeBase(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Corporate Portal", status="ACTIVE")
    db_session.add(kb)
    await db_session.flush()

    doc = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb.id,
        filename="leave_policy.txt",
        safe_filename="leave_policy.txt",
        file_path="/tenants/leave_doc",
        mime_type="text/plain",
        status="COMPLETED",
    )
    db_session.add(doc)
    await db_session.flush()

    chunk_id = uuid.uuid4()
    chunk = DocumentChunk(
        id=chunk_id,
        tenant_id=tenant_a.id,
        knowledge_base_id=kb.id,
        document_id=doc.id,
        chunk_index=0,
        content="All permanent staff receive 20 days of paid vacation per year.",
        page_number=1,
    )
    db_session.add(chunk)
    await db_session.commit()

    # 2. Create Assistant connected to KB with Mock LLM
    asst = Assistant(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        name="RAG Assistant",
        slug="rag-assistant",
        llm_provider="mock",
        default_model="mock-gpt",
        retrieval_mode="lexical",
        top_k=3,
        system_prompt="Ground answers in internal corporate policy.",
        status="ACTIVE",
    )
    db_session.add(asst)
    await db_session.flush()

    assoc = AssistantKnowledgeBase(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        assistant_id=asst.id,
        knowledge_base_id=kb.id,
    )
    db_session.add(assoc)

    # 3. Create Conversation
    conv = Conversation(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        user_id=user_a.id,
        assistant_id=asst.id,
        title="Vacation Policy Inquiry",
        status="ACTIVE",
    )
    db_session.add(conv)
    await db_session.commit()

    # 4. Execute streaming chat through runtime
    runtime = AssistantRuntime(
        session=db_session,
        tenant_id=tenant_a.id,
        user_id=user_a.id,
        is_admin=True,
    )

    events: list[str] = []
    async for sse_frame in runtime.stream_chat(conv.id, "How many vacation days do permanent staff get?"):
        events.append(sse_frame)

    # Verify SSE events received
    event_str = "".join(events)
    assert "event: message_start" in event_str
    assert "event: retrieval_start" in event_str
    assert "event: retrieval_complete" in event_str
    assert "event: token" in event_str
    assert "event: usage" in event_str
    assert "event: message_complete" in event_str

    # 5. Verify database persistence
    msg_rows = (await db_session.execute(
        Message.__table__.select().where(Message.conversation_id == conv.id)
    )).all()
    # Expect 2 messages: user message and assistant message
    assert len(msg_rows) == 2
    assistant_msg = next(m for m in msg_rows if m.sender_type == "assistant")
    assert "[1]" in assistant_msg.content

    # Verify citation was persisted
    from app.models.conversation import MessageCitation
    citations = (await db_session.execute(
        MessageCitation.__table__.select().where(MessageCitation.message_id == assistant_msg.id)
    )).all()
    assert len(citations) >= 1
    assert citations[0].document_name == "leave_policy.txt"
    assert citations[0].citation_num == 1
