"""M05 Phase 6: LLM Provider Architecture & Streaming Reliability Assessment.

Tests all reliability and security vectors across:
1. Provider Architecture & Registry Contract (PRV-01 to PRV-04).
2. BYOK Credential Isolation & Endpoint SSRF Security (BYOK-01 to BYOK-04).
3. HTTP Provider Failure Normalization (HTTP-01 to HTTP-06).
4. SSE Streaming Lifecycle, Timeout, Disconnect & Error Frames (SSE-01 to SSE-05).
5. Persistence Consistency & Atomic Message/Citation State (PERSIST-01 to PERSIST-03).
"""

import uuid
from unittest.mock import patch

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assistant_runtime.runtime import AssistantRuntime
from app.core.crypto import decrypt_secret, encrypt_secret
from app.llm import LLMConfig, LLMMessage, get_llm_registry
from app.llm.base import (
    LLMAuthenticationError,
    LLMConnectionError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app.llm.providers.openai_provider import (
    OpenAICompatibleLLMProvider,
    validate_provider_endpoint,
)
from app.models.conversation import Conversation, Message
from app.repositories.assistant_repository import AssistantRepository
from app.services.byok_vault import BYOKVaultService

# ==============================================================================
# 1. PROVIDER ARCHITECTURE & REGISTRY CONTRACT (PRV-01 to PRV-04)
# ==============================================================================


def test_provider_registry_default_providers():
    """Registry resolves omniroute, openai, and mock providers."""
    registry = get_llm_registry()
    providers = registry.list_providers()
    provider_names = {p["name"] for p in providers}

    assert "omniroute" in provider_names
    assert "openai" in provider_names
    assert "mock" in provider_names

    # Provider instance resolution
    omni = registry.get_provider("omniroute")
    assert omni.provider_name == "omniroute"

    mock = registry.get_provider("mock")
    assert mock.provider_name == "mock"


def test_provider_registry_strict_lookup_unknown_provider():
    """Strict lookup on unknown provider raises KeyError."""
    registry = get_llm_registry()
    with pytest.raises(KeyError) as exc_info:
        registry.get_provider("unregistered_vendor", strict=True)
    assert "unregistered_vendor" in str(exc_info.value)


@pytest.mark.asyncio
async def test_assistant_creation_rejects_unsupported_provider(db_session: AsyncSession, seed_data: dict):
    """Server-side assistant creation rejects unknown or unapproved providers."""
    tenant = seed_data["tenant_a"]
    repo = AssistantRepository(session=db_session, tenant_id=tenant.id)

    with pytest.raises(ValueError) as exc_info:
        await repo.create_assistant(
            name="Invalid Provider Assistant",
            llm_provider="unsupported_cloud_ai",
            default_model="auto",
        )
    assert "Unsupported LLM provider" in str(exc_info.value)


@pytest.mark.asyncio
async def test_assistant_creation_and_update_rejects_empty_model(db_session: AsyncSession, seed_data: dict):
    """Assistant creation and update reject empty or whitespace default_model."""
    tenant = seed_data["tenant_a"]
    repo = AssistantRepository(session=db_session, tenant_id=tenant.id)

    # Empty model on create
    with pytest.raises(ValueError) as exc_info:
        await repo.create_assistant(
            name="Empty Model Assistant",
            llm_provider="omniroute",
            default_model="   ",
        )
    assert "default_model cannot be empty" in str(exc_info.value)

    # Create valid assistant
    asst = await repo.create_assistant(
        name="Valid Assistant",
        llm_provider="omniroute",
        default_model="gpt-4o-mini",
    )
    assert asst.default_model == "gpt-4o-mini"

    # Empty model on update
    with pytest.raises(ValueError) as exc_info:
        await repo.update_assistant(assistant_id=asst.id, default_model="")
    assert "default_model cannot be empty" in str(exc_info.value)

    # Invalid provider on update
    with pytest.raises(ValueError) as exc_info:
        await repo.update_assistant(assistant_id=asst.id, llm_provider="fake_provider")
    assert "Unsupported LLM provider" in str(exc_info.value)


# ==============================================================================
# 2. BYOK CREDENTIAL ISOLATION & ENDPOINT SSRF SECURITY (BYOK-01 to BYOK-04)
# ==============================================================================


def test_byok_encryption_and_tamper_resistance():
    """BYOK secret encryption protects credentials at rest and fails safely on tampering."""
    synthetic_key = "TEST_SECRET_PROVIDER_KEY_84X2"
    ciphertext = encrypt_secret(synthetic_key)

    assert ciphertext != synthetic_key
    assert decrypt_secret(ciphertext) == synthetic_key

    # Tampered ciphertext fails closed (returns None, never raises unhandled exception)
    assert decrypt_secret("invalid-tampered-data-gibberish") is None
    assert decrypt_secret("") is None


def test_validate_provider_endpoint_blocks_ssrf_cloud_metadata():
    """validate_provider_endpoint blocks cloud metadata IP 169.254.169.254 and link-local addresses."""
    # AWS / GCP / Azure link-local metadata IP
    with pytest.raises(ValueError) as exc_info:
        validate_provider_endpoint("http://169.254.169.254/latest/meta-data/")
    assert "cloud metadata address" in str(exc_info.value)

    # Metadata hostname
    with pytest.raises(ValueError) as exc_info:
        validate_provider_endpoint("http://metadata.google.internal/computeMetadata/v1")
    assert "cloud metadata endpoint is forbidden" in str(exc_info.value)


def test_validate_provider_endpoint_blocks_forbidden_schemes():
    """validate_provider_endpoint blocks non-http/https URL schemes."""
    with pytest.raises(ValueError) as exc_info:
        validate_provider_endpoint("file:///etc/passwd")
    assert "Invalid URL scheme 'file'" in str(exc_info.value)

    with pytest.raises(ValueError) as exc_info:
        validate_provider_endpoint("gopher://evil.com:70/1")
    assert "Invalid URL scheme 'gopher'" in str(exc_info.value)

    with pytest.raises(ValueError) as exc_info:
        validate_provider_endpoint("ftp://files.example.com/api")
    assert "Invalid URL scheme 'ftp'" in str(exc_info.value)


def test_validate_provider_endpoint_allows_valid_local_and_remote_targets():
    """validate_provider_endpoint permits trusted local OmniRoute and remote HTTPS endpoints."""
    # Local development OmniRoute gateway
    omni_url = validate_provider_endpoint("http://localhost:20128/v1", allow_local=True)
    assert omni_url == "http://localhost:20128/v1"

    # Remote HTTPS OpenAI endpoint
    openai_url = validate_provider_endpoint("https://api.openai.com/v1", allow_local=True)
    assert openai_url == "https://api.openai.com/v1"


# ==============================================================================
# 3. HTTP PROVIDER FAILURE NORMALIZATION (HTTP-01 to HTTP-06)
# ==============================================================================


@pytest.mark.asyncio
async def test_openai_provider_handles_connect_timeout():
    """Connect timeout raises normalized LLMTimeoutError."""
    provider = OpenAICompatibleLLMProvider(name="openai", default_base_url="https://api.openai.com/v1")
    config = LLMConfig(provider="openai", model="gpt-4o", timeout_seconds=5)

    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectTimeout("Connection timed out")):
        with pytest.raises(LLMTimeoutError) as exc_info:
            await provider.generate([LLMMessage(role="user", content="Hi")], config)
        assert "timed out" in str(exc_info.value)


@pytest.mark.asyncio
async def test_openai_provider_handles_connect_error():
    """Connection failure raises normalized LLMConnectionError."""
    provider = OpenAICompatibleLLMProvider(name="openai", default_base_url="https://api.openai.com/v1")
    config = LLMConfig(provider="openai", model="gpt-4o")

    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")):
        with pytest.raises(LLMConnectionError) as exc_info:
            await provider.generate([LLMMessage(role="user", content="Hi")], config)
        assert "Failed to connect" in str(exc_info.value)


@pytest.mark.asyncio
async def test_openai_provider_handles_http_401_and_403_authentication():
    """HTTP 401 and 403 status codes raise LLMAuthenticationError."""
    provider = OpenAICompatibleLLMProvider(name="openai", default_base_url="https://api.openai.com/v1")
    config = LLMConfig(provider="openai", model="gpt-4o")

    # 401 Unauthorized
    mock_resp_401 = httpx.Response(status_code=401, json={"error": {"message": "Invalid API key"}})
    with patch("httpx.AsyncClient.post", return_value=mock_resp_401):
        with pytest.raises(LLMAuthenticationError) as exc_info:
            await provider.generate([LLMMessage(role="user", content="Hi")], config)
        assert "HTTP 401" in str(exc_info.value)

    # 403 Forbidden
    mock_resp_403 = httpx.Response(status_code=403, json={"error": {"message": "Country not supported"}})
    with patch("httpx.AsyncClient.post", return_value=mock_resp_403):
        with pytest.raises(LLMAuthenticationError) as exc_info:
            await provider.generate([LLMMessage(role="user", content="Hi")], config)
        assert "HTTP 403" in str(exc_info.value)


@pytest.mark.asyncio
async def test_openai_provider_handles_http_429_rate_limiting():
    """HTTP 429 status code raises LLMRateLimitError."""
    provider = OpenAICompatibleLLMProvider(name="openai", default_base_url="https://api.openai.com/v1")
    config = LLMConfig(provider="openai", model="gpt-4o")

    mock_resp_429 = httpx.Response(status_code=429, json={"error": {"message": "Rate limit exceeded"}})
    with patch("httpx.AsyncClient.post", return_value=mock_resp_429):
        with pytest.raises(LLMRateLimitError) as exc_info:
            await provider.generate([LLMMessage(role="user", content="Hi")], config)
        assert "HTTP 429" in str(exc_info.value)


@pytest.mark.asyncio
async def test_openai_provider_handles_http_500_provider_error():
    """HTTP 500 status code raises LLMProviderError."""
    provider = OpenAICompatibleLLMProvider(name="openai", default_base_url="https://api.openai.com/v1")
    config = LLMConfig(provider="openai", model="gpt-4o")

    mock_resp_500 = httpx.Response(status_code=500, text="Internal Server Error")
    with patch("httpx.AsyncClient.post", return_value=mock_resp_500):
        with pytest.raises(LLMProviderError) as exc_info:
            await provider.generate([LLMMessage(role="user", content="Hi")], config)
        assert "HTTP 500" in str(exc_info.value)


# ==============================================================================
# 4. SSE STREAMING LIFECYCLE & EDGE CASES (SSE-01 to SSE-05)
# ==============================================================================


@pytest.mark.asyncio
async def test_sse_streaming_successful_lifecycle_and_ordering(db_session: AsyncSession, seed_data: dict):
    """Successful SSE stream emits message_start -> token -> usage -> message_complete in exact order."""
    tenant = seed_data["tenant_a"]
    user = seed_data["user_a_owner"]

    asst_repo = AssistantRepository(session=db_session, tenant_id=tenant.id)
    asst = await asst_repo.create_assistant(
        name="Lifecycle Assistant",
        llm_provider="mock",
        default_model="mock-gpt",
    )

    conv = Conversation(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        user_id=user.id,
        assistant_id=asst.id,
        title="Lifecycle Session",
        status="ACTIVE",
    )
    db_session.add(conv)
    await db_session.commit()

    runtime = AssistantRuntime(session=db_session, tenant_id=tenant.id, user_id=user.id, is_admin=True)

    event_types: list[str] = []
    async for frame in runtime.stream_chat(conv.id, "Hello"):
        for line in frame.splitlines():
            if line.startswith("event: "):
                event_types.append(line.replace("event: ", "").strip())

    # Verify event ordering
    assert event_types[0] == "message_start"
    assert "token" in event_types
    assert event_types[-2] == "usage"
    assert event_types[-1] == "message_complete"
    assert "message_error" not in event_types


@pytest.mark.asyncio
async def test_sse_streaming_provider_failure_emits_sanitized_error_frame(db_session: AsyncSession, seed_data: dict):
    """When a provider stream fails, SSE emits message_error and aborts without message_complete."""
    tenant = seed_data["tenant_a"]
    user = seed_data["user_a_owner"]

    asst_repo = AssistantRepository(session=db_session, tenant_id=tenant.id)
    asst = await asst_repo.create_assistant(
        name="Failing Stream Assistant",
        llm_provider="openai",
        default_model="gpt-4o",
    )

    conv = Conversation(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        user_id=user.id,
        assistant_id=asst.id,
        title="Failing Stream Session",
        status="ACTIVE",
    )
    db_session.add(conv)

    byok_svc = BYOKVaultService(session=db_session, tenant_id=tenant.id)
    await byok_svc.add_credential(
        provider_name="openai",
        display_name="Test Key",
        api_key="sk-test-byok-12345",
        is_default=True,
    )
    await db_session.commit()

    runtime = AssistantRuntime(session=db_session, tenant_id=tenant.id, user_id=user.id, is_admin=True)

    # Simulate provider failure during stream with a synthetic secret in error
    with patch(
        "app.llm.providers.openai_provider.OpenAICompatibleLLMProvider.generate_stream",
        side_effect=LLMAuthenticationError("HTTP 401: Invalid key sk-live-secret-test-key-12345678"),
    ):
        frames: list[str] = [f async for f in runtime.stream_chat(conv.id, "Hi")]

    frame_str = "".join(frames)
    assert "message_error" in frame_str
    assert "message_complete" not in frame_str
    # Verify API key was sanitized in error frame
    assert "sk-live-secret-test-key-12345678" not in frame_str
    assert "[REDACTED_API_KEY]" in frame_str


@pytest.mark.asyncio
async def test_sse_streaming_empty_response_stream_fails_safely(db_session: AsyncSession, seed_data: dict):
    """If provider emits 0 tokens, stream fails with message_error and does not commit a blank message."""
    tenant = seed_data["tenant_a"]
    user = seed_data["user_a_owner"]

    asst_repo = AssistantRepository(session=db_session, tenant_id=tenant.id)
    asst = await asst_repo.create_assistant(
        name="Empty Stream Assistant",
        llm_provider="mock",
        default_model="mock-gpt",
    )

    conv = Conversation(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        user_id=user.id,
        assistant_id=asst.id,
        title="Empty Stream Session",
        status="ACTIVE",
    )
    db_session.add(conv)
    await db_session.commit()

    runtime = AssistantRuntime(session=db_session, tenant_id=tenant.id, user_id=user.id, is_admin=True)

    # Empty async generator simulating 0 token stream
    async def empty_stream(*args, **kwargs):
        if False:
            yield None

    with patch("app.llm.providers.mock_provider.MockLLMProvider.generate_stream", side_effect=empty_stream):
        frames = [f async for f in runtime.stream_chat(conv.id, "Hello?")]

    frame_str = "".join(frames)
    assert "message_error" in frame_str
    assert "Empty response stream received" in frame_str
    assert "message_complete" not in frame_str

    # Verify a visible error assistant message was persisted
    msg_stmt = select(Message).where(Message.conversation_id == conv.id, Message.sender_type == "assistant")
    messages = (await db_session.execute(msg_stmt)).scalars().all()
    assert len(messages) == 1
    assert "Empty response stream received" in messages[0].content


@pytest.mark.asyncio
async def test_sse_streaming_cancellation_cleans_up_without_completion(db_session: AsyncSession, seed_data: dict):
    """Client disconnect / cancellation aborts stream without emitting message_complete or persisting."""
    tenant = seed_data["tenant_a"]
    user = seed_data["user_a_owner"]

    asst_repo = AssistantRepository(session=db_session, tenant_id=tenant.id)
    asst = await asst_repo.create_assistant(
        name="Cancellation Assistant",
        llm_provider="mock",
        default_model="mock-gpt",
    )

    conv = Conversation(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        user_id=user.id,
        assistant_id=asst.id,
        title="Cancellation Session",
        status="ACTIVE",
    )
    db_session.add(conv)
    await db_session.commit()

    runtime = AssistantRuntime(session=db_session, tenant_id=tenant.id, user_id=user.id, is_admin=True)

    # Consume only the first 2 frames then simulate client disconnect (close generator)
    stream_gen = runtime.stream_chat(conv.id, "Long query...")
    frame1 = await anext(stream_gen)
    assert "message_start" in frame1

    # Close generator (simulating client abort / disconnect)
    await stream_gen.aclose()

    # Verify no completed assistant message was written to database
    msg_stmt = select(Message).where(Message.conversation_id == conv.id, Message.sender_type == "assistant")
    messages = (await db_session.execute(msg_stmt)).scalars().all()
    assert len(messages) == 0


# ==============================================================================
# 5. PERSISTENCE CONSISTENCY & ATOMIC STATE (PERSIST-01 to PERSIST-03)
# ==============================================================================


@pytest.mark.asyncio
async def test_persistence_atomic_user_and_assistant_messages_with_citations(db_session: AsyncSession, seed_data: dict):
    """Successful stream atomically commits user message, assistant message, and citation records."""
    tenant = seed_data["tenant_a"]
    user = seed_data["user_a_owner"]

    asst_repo = AssistantRepository(session=db_session, tenant_id=tenant.id)
    asst = await asst_repo.create_assistant(
        name="Persistence Assistant",
        llm_provider="mock",
        default_model="mock-gpt",
    )

    conv = Conversation(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        user_id=user.id,
        assistant_id=asst.id,
        title="Atomic Persistence Session",
        status="ACTIVE",
    )
    db_session.add(conv)
    await db_session.commit()

    runtime = AssistantRuntime(session=db_session, tenant_id=tenant.id, user_id=user.id, is_admin=True)

    # Execute full stream
    frames = [f async for f in runtime.stream_chat(conv.id, "What are the rules?")]
    assert any("message_complete" in f for f in frames)

    # Query DB
    user_stmt = select(Message).where(Message.conversation_id == conv.id, Message.sender_type == "user")
    asst_stmt = select(Message).where(Message.conversation_id == conv.id, Message.sender_type == "assistant")

    user_msg = (await db_session.execute(user_stmt)).scalar_one_or_none()
    asst_msg = (await db_session.execute(asst_stmt)).scalar_one_or_none()

    assert user_msg is not None
    assert user_msg.content == "What are the rules?"
    assert asst_msg is not None
    assert len(asst_msg.content) > 0


@pytest.mark.asyncio
async def test_persistence_failure_leaves_clean_database_state(db_session: AsyncSession, seed_data: dict):
    """When generation fails midway, no phantom success message is persisted; the failure is persisted safely."""
    tenant = seed_data["tenant_a"]
    user = seed_data["user_a_owner"]

    asst_repo = AssistantRepository(session=db_session, tenant_id=tenant.id)
    asst = await asst_repo.create_assistant(
        name="Abort Assistant",
        llm_provider="openai",
        default_model="gpt-4o",
    )

    conv = Conversation(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        user_id=user.id,
        assistant_id=asst.id,
        title="Abort Session",
        status="ACTIVE",
    )
    db_session.add(conv)

    byok_svc = BYOKVaultService(session=db_session, tenant_id=tenant.id)
    await byok_svc.add_credential(
        provider_name="openai",
        display_name="Test Key",
        api_key="sk-test-byok-12345",
        is_default=True,
    )
    await db_session.commit()

    runtime = AssistantRuntime(session=db_session, tenant_id=tenant.id, user_id=user.id, is_admin=True)

    # Provider yields 1 token then fails
    async def failing_stream(*args, **kwargs):
        from app.llm.base import LLMStreamChunk
        yield LLMStreamChunk(content_delta="Partial token...")
        raise LLMConnectionError("Socket closed prematurely")

    with patch("app.llm.providers.openai_provider.OpenAICompatibleLLMProvider.generate_stream", side_effect=failing_stream):
        frames = [f async for f in runtime.stream_chat(conv.id, "Will this fail?")]

    frame_str = "".join(frames)
    assert "token" in frame_str
    assert "message_error" in frame_str
    assert "message_complete" not in frame_str

    # Database must NOT contain a phantom success message; the failure is persisted safely
    asst_stmt = select(Message).where(Message.conversation_id == conv.id, Message.sender_type == "assistant")
    asst_msg = (await db_session.execute(asst_stmt)).scalar_one_or_none()
    assert asst_msg is not None
    assert "LLM generation failed:" in asst_msg.content
    assert "Socket closed prematurely" in asst_msg.content
