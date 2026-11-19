"""M28.10.1 Phase 2: Comprehensive 20-Scenario Provider Contract & Failure Modes Test Suite."""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.assistant_runtime.runtime import format_user_facing_error
from app.llm.base import (
    LLMAuthenticationError,
    LLMConfig,
    LLMConnectionError,
    LLMMessage,
    LLMModelUnavailableError,
    LLMProviderError,
    LLMRateLimitError,
    LLMResponseInvalidError,
    LLMStreamInterruptedError,
    LLMTimeoutError,
    LLMToolCallUnsupportedError,
)
from app.llm.providers.openai_provider import OpenAICompatibleLLMProvider


@pytest.fixture
def test_config():
    """Provides standard valid LLMConfig for testing without external endpoints."""
    return LLMConfig(
        provider="openai",
        api_key="sk-test-key-12345",
        model="gpt-4o",
        temperature=0.7,
        max_tokens=100,
        timeout_seconds=5,
    )


# 1. Normal streaming
@pytest.mark.asyncio
async def test_01_normal_streaming(test_config):
    provider = OpenAICompatibleLLMProvider("openai")
    sse_lines = [
        'data: {"id":"1","choices":[{"delta":{"content":"Hello"},"finish_reason":null}]}',
        'data: {"id":"1","choices":[{"delta":{"content":" world!"},"finish_reason":"stop"}]}',
        "data: [DONE]",
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.aread = AsyncMock(return_value=b"")

    async def mock_aiter_lines():
        for line in sse_lines:
            yield line

    mock_resp.aiter_lines = mock_aiter_lines

    mock_stream_ctx = MagicMock()
    mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient.stream", return_value=mock_stream_ctx):
        chunks = []
        async for chunk in provider.generate_stream([LLMMessage(role="user", content="Hi")], test_config):
            chunks.append(chunk.content_delta)

    assert "".join(chunks) == "Hello world!"


# 2. Normal non-streaming
@pytest.mark.asyncio
async def test_02_normal_non_streaming(test_config):
    provider = OpenAICompatibleLLMProvider("openai")
    payload = {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "choices": [{
            "message": {"role": "assistant", "content": "Normal completion"},
            "finish_reason": "stop"
        }],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json = MagicMock(return_value=payload)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        res = await provider.generate([LLMMessage(role="user", content="Hi")], test_config)

    assert res.content == "Normal completion"
    assert res.tokens_used["total_tokens"] == 15


# 3. Usage-only SSE event
@pytest.mark.asyncio
async def test_03_usage_only_sse_event(test_config):
    provider = OpenAICompatibleLLMProvider("openai")
    sse_lines = [
        'data: {"choices":[{"delta":{"content":"Answer"},"finish_reason":null}]}',
        'data: {"usage":{"prompt_tokens":12,"completion_tokens":1}}',  # No choices key
        "data: [DONE]",
    ]
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.aread = AsyncMock(return_value=b"")

    async def mock_aiter():
        for line in sse_lines:
            yield line
    mock_resp.aiter_lines = mock_aiter

    mock_stream_ctx = MagicMock()
    mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient.stream", return_value=mock_stream_ctx):
        chunks = [c.content_delta async for c in provider.generate_stream([LLMMessage(role="user", content="Hi")], test_config)]

    assert "".join(chunks) == "Answer"


# 4. Metadata-only SSE event
@pytest.mark.asyncio
async def test_04_metadata_only_sse_event(test_config):
    provider = OpenAICompatibleLLMProvider("openai")
    sse_lines = [
        ': ping / keepalive comment',
        'event: ping',
        'data: {"id":"chatcmpl-123","model":"gpt-4o","choices":[]}',  # Empty choices
        'data: {"choices":[{"delta":{"content":"Valid"},"finish_reason":"stop"}]}',
        "data: [DONE]",
    ]
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.aread = AsyncMock(return_value=b"")

    async def mock_aiter():
        for line in sse_lines:
            yield line
    mock_resp.aiter_lines = mock_aiter

    mock_stream_ctx = MagicMock()
    mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient.stream", return_value=mock_stream_ctx):
        chunks = [c.content_delta async for c in provider.generate_stream([LLMMessage(role="user", content="Hi")], test_config)]

    assert "".join(chunks) == "Valid"


# 5. Empty choices (non-streaming)
@pytest.mark.asyncio
async def test_05_empty_choices_raises_typed_error(test_config):
    provider = OpenAICompatibleLLMProvider("openai")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json = MagicMock(return_value={"id": "cmpl", "choices": []})

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(LLMResponseInvalidError) as exc_info:
            await provider.generate([LLMMessage(role="user", content="Hi")], test_config)
    assert "choices" in str(exc_info.value)


# 6. Missing choices (non-streaming)
@pytest.mark.asyncio
async def test_06_missing_choices_raises_typed_error(test_config):
    provider = OpenAICompatibleLLMProvider("openai")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json = MagicMock(return_value={"id": "cmpl", "object": "chat.completion"})

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(LLMResponseInvalidError) as exc_info:
            await provider.generate([LLMMessage(role="user", content="Hi")], test_config)
    assert "missing or empty 'choices'" in str(exc_info.value)


# 7. Provider error payload (HTTP 200 with {"error": "..."})
@pytest.mark.asyncio
async def test_07_provider_error_payload_in_json(test_config):
    provider = OpenAICompatibleLLMProvider("openai")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json = MagicMock(return_value={"error": {"message": "Invalid API request parameters"}})

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(LLMResponseInvalidError) as exc_info:
            await provider.generate([LLMMessage(role="user", content="Hi")], test_config)
    assert "Invalid API request parameters" in str(exc_info.value)


# 8. HTTP 200 with embedded error in streaming
@pytest.mark.asyncio
async def test_08_streaming_embedded_error_event(test_config):
    provider = OpenAICompatibleLLMProvider("openai")
    sse_lines = [
        'data: {"choices":[{"delta":{"content":"Partial"},"finish_reason":null}]}',
        'data: {"error":{"message":"Midstream token allocation exhausted"}}',
    ]
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.aread = AsyncMock(return_value=b"")

    async def mock_aiter():
        for line in sse_lines:
            yield line
    mock_resp.aiter_lines = mock_aiter

    mock_stream_ctx = MagicMock()
    mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient.stream", return_value=mock_stream_ctx):
        with pytest.raises(LLMStreamInterruptedError) as exc_info:
            async for _ in provider.generate_stream([LLMMessage(role="user", content="Hi")], test_config):
                pass
    assert "Midstream token allocation exhausted" in str(exc_info.value)


# 9. HTTP 401 Unauthorized
@pytest.mark.asyncio
async def test_09_http_401_raises_authentication_error(test_config):
    provider = OpenAICompatibleLLMProvider("openai")
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = json.dumps({"error": {"message": "Incorrect API key provided"}})

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(LLMAuthenticationError) as exc_info:
            await provider.generate([LLMMessage(role="user", content="Hi")], test_config)
    assert "Incorrect API key" in str(exc_info.value)


# 10. HTTP 429 Rate Limited
@pytest.mark.asyncio
async def test_10_http_429_raises_ratelimit_error(test_config):
    provider = OpenAICompatibleLLMProvider("openai")
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.text = json.dumps({"error": {"message": "Rate limit reached for requests"}})

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(LLMRateLimitError) as exc_info:
            await provider.generate([LLMMessage(role="user", content="Hi")], test_config)
    assert "Rate limit" in str(exc_info.value)


# 11. Unsupported model (HTTP 404 with model message)
@pytest.mark.asyncio
async def test_11_unsupported_model_raises_model_unavailable(test_config):
    provider = OpenAICompatibleLLMProvider("openai")
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.text = json.dumps({"error": {"message": "The model `gpt-99-nonexistent` does not exist"}})

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(LLMModelUnavailableError) as exc_info:
            await provider.generate([LLMMessage(role="user", content="Hi")], test_config)
    assert "Model unavailable" in str(exc_info.value)


# 12. Unsupported tools
@pytest.mark.asyncio
async def test_12_unsupported_tools_raises_tool_unsupported(test_config):
    provider = OpenAICompatibleLLMProvider("openai")
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.text = json.dumps({"error": {"message": "Tools are not supported with this model"}})

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(LLMToolCallUnsupportedError) as exc_info:
            await provider.generate([LLMMessage(role="user", content="Hi")], test_config)
    assert "Tools unsupported" in str(exc_info.value)


# 13. Partial SSE frame (data: without space and whitespace tolerance)
@pytest.mark.asyncio
async def test_13_partial_and_compact_sse_frames(test_config):
    provider = OpenAICompatibleLLMProvider("openai")
    sse_lines = [
        'data:{"choices":[{"delta":{"content":"ChunkA"},"finish_reason":null}]}',
        'data: {"choices":[{"delta":{"content":"ChunkB"},"finish_reason":null}]}',
        'data: [DONE]',
    ]
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.aread = AsyncMock(return_value=b"")

    async def mock_aiter():
        for line in sse_lines:
            yield line
    mock_resp.aiter_lines = mock_aiter

    mock_stream_ctx = MagicMock()
    mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient.stream", return_value=mock_stream_ctx):
        chunks = [c.content_delta async for c in provider.generate_stream([LLMMessage(role="user", content="Hi")], test_config)]

    assert "".join(chunks) == "ChunkAChunkB"


# 14. Multiple tool calls in stream
@pytest.mark.asyncio
async def test_14_multiple_tool_calls_in_stream(test_config):
    provider = OpenAICompatibleLLMProvider("openai")
    sse_lines = [
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_01","function":{"name":"weather_lookup","arguments":"{\\"city\\":\\""}}]},"finish_reason":null}]}',
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"Karachi\\"}"}}]},"finish_reason":null}]}',
        'data: {"choices":[{"delta":{"tool_calls":[{"index":1,"id":"call_02","function":{"name":"web_search","arguments":"{\\"query\\":\\"solar\\"}"}}]},"finish_reason":null}]}',
        'data: {"choices":[{"delta":{},"finish_reason":"tool_calls"}]}',
        'data: [DONE]',
    ]
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.aread = AsyncMock(return_value=b"")

    async def mock_aiter():
        for line in sse_lines:
            yield line
    mock_resp.aiter_lines = mock_aiter

    mock_stream_ctx = MagicMock()
    mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient.stream", return_value=mock_stream_ctx):
        chunks = [c async for c in provider.generate_stream([LLMMessage(role="user", content="Hi")], test_config)]

    final_chunk = [c for c in chunks if c.tool_calls]
    assert len(final_chunk) == 1
    tcs = final_chunk[0].tool_calls
    assert len(tcs) == 2
    assert tcs[0]["name"] == "weather_lookup"
    assert tcs[0]["arguments"] == {"city": "Karachi"}
    assert tcs[1]["name"] == "web_search"
    assert tcs[1]["arguments"] == {"query": "solar"}


# 15. Tool-call JSON fragmentation and recovery
@pytest.mark.asyncio
async def test_15_tool_call_json_fragmentation(test_config):
    provider = OpenAICompatibleLLMProvider("openai")
    sse_lines = [
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_99","function":{"name":"calc","arguments":"{\\"exp"}}]},"finish_reason":null}]}',
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"ression\\":\\"2+2\\"}"}}]},"finish_reason":null}]}',
        'data: {"choices":[{"delta":{},"finish_reason":"tool_calls"}]}',
        'data: [DONE]',
    ]
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.aread = AsyncMock(return_value=b"")

    async def mock_aiter():
        for line in sse_lines:
            yield line
    mock_resp.aiter_lines = mock_aiter

    mock_stream_ctx = MagicMock()
    mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient.stream", return_value=mock_stream_ctx):
        chunks = [c async for c in provider.generate_stream([LLMMessage(role="user", content="Hi")], test_config)]

    final_chunk = [c for c in chunks if c.tool_calls]
    assert len(final_chunk) == 1
    tc = final_chunk[0].tool_calls[0]
    assert tc["arguments"] == {"expression": "2+2"}


# 16. Network interruption mid-stream
@pytest.mark.asyncio
async def test_16_network_interruption_mid_stream(test_config):
    provider = OpenAICompatibleLLMProvider("openai")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.aread = AsyncMock(return_value=b"")

    async def mock_aiter_failing():
        yield 'data: {"choices":[{"delta":{"content":"First chunk"},"finish_reason":null}]}'
        raise httpx.RemoteProtocolError("Connection abruptly terminated by peer")

    mock_resp.aiter_lines = mock_aiter_failing

    mock_stream_ctx = MagicMock()
    mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient.stream", return_value=mock_stream_ctx):
        with pytest.raises(LLMStreamInterruptedError) as exc_info:
            async for _ in provider.generate_stream([LLMMessage(role="user", content="Hi")], test_config):
                pass
    assert "interrupted mid-stream" in str(exc_info.value)


# 17. Timeout
@pytest.mark.asyncio
async def test_17_timeout_raises_llm_timeout(test_config):
    provider = OpenAICompatibleLLMProvider("openai")
    with patch("httpx.AsyncClient.post", side_effect=httpx.ReadTimeout("Read timed out")):
        with pytest.raises(LLMTimeoutError) as exc_info:
            await provider.generate([LLMMessage(role="user", content="Hi")], test_config)
    assert "timed out" in str(exc_info.value)


# 18. Client cancellation (GeneratorExit during streaming)
@pytest.mark.asyncio
async def test_18_client_cancellation_generator_exit(test_config):
    provider = OpenAICompatibleLLMProvider("openai")
    sse_lines = [
        'data: {"choices":[{"delta":{"content":"Chunk1"},"finish_reason":null}]}',
        'data: {"choices":[{"delta":{"content":"Chunk2"},"finish_reason":null}]}',
    ]
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.aread = AsyncMock(return_value=b"")

    async def mock_aiter():
        for line in sse_lines:
            yield line
    mock_resp.aiter_lines = mock_aiter

    mock_stream_ctx = MagicMock()
    mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient.stream", return_value=mock_stream_ctx):
        stream_gen = provider.generate_stream([LLMMessage(role="user", content="Hi")], test_config)
        first_chunk = await anext(stream_gen)
        assert first_chunk.content_delta == "Chunk1"
        # Close early like client disconnecting
        await stream_gen.aclose()


# 19. Empty successful stream
@pytest.mark.asyncio
async def test_19_empty_successful_stream(test_config):
    provider = OpenAICompatibleLLMProvider("openai")
    sse_lines = [
        'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}',
        'data: [DONE]',
    ]
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.aread = AsyncMock(return_value=b"")

    async def mock_aiter():
        for line in sse_lines:
            yield line
    mock_resp.aiter_lines = mock_aiter

    mock_stream_ctx = MagicMock()
    mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient.stream", return_value=mock_stream_ctx):
        chunks = [c.content_delta async for c in provider.generate_stream([LLMMessage(role="user", content="Hi")], test_config)]

    assert "".join(chunks) == ""


# 20. Missing final event (stream completes cleanly without [DONE])
@pytest.mark.asyncio
async def test_20_missing_final_event_clean_termination(test_config):
    provider = OpenAICompatibleLLMProvider("openai")
    sse_lines = [
        'data: {"choices":[{"delta":{"content":"Final sentence."},"finish_reason":"stop"}]}',
        # No [DONE] event; connection closes naturally
    ]
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.aread = AsyncMock(return_value=b"")

    async def mock_aiter():
        for line in sse_lines:
            yield line
    mock_resp.aiter_lines = mock_aiter

    mock_stream_ctx = MagicMock()
    mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient.stream", return_value=mock_stream_ctx):
        chunks = [c.content_delta async for c in provider.generate_stream([LLMMessage(role="user", content="Hi")], test_config)]

    assert "".join(chunks) == "Final sentence."
