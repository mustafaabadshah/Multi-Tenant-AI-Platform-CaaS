"""M28.10 Automated Test Suite: Provider Robustness, Citation Integrity, Research Quality, and Search Reliability."""

import json
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.llm.base import (
    LLMAuthenticationError,
    LLMConfig,
    LLMConnectionError,
    LLMMessage,
    LLMModelUnavailableError,
    LLMRateLimitError,
    LLMResponseInvalidError,
    LLMStreamInterruptedError,
    LLMTimeoutError,
    LLMToolCallUnsupportedError,
)
from app.llm.providers.openai_provider import OpenAICompatibleLLMProvider as OpenAIProvider
from app.assistant_runtime.context import build_rag_context
from app.assistant_runtime.runtime import (
    filter_substantive_relevance,
    format_user_facing_error,
)
from app.services.web.search import (
    ArxivSearchProvider,
    BraveSearchProvider,
    MockSearchProvider,
    WebSearchService,
)
from app.vectorstores.base import VectorSearchResult


# ---------------------------------------------------------------------------
# 1. Provider Robustness Tests (KeyError: 'choices' Defect Closure)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_openai_provider_missing_choices_raises_typed_error():
    """Verify that a provider response missing 'choices' raises LLMResponseInvalidError, never KeyError."""
    provider = OpenAIProvider()
    fake_config = LLMConfig(provider="omniroute", api_key="test-key", model="test-model", temperature=0.7, max_tokens=100, timeout_seconds=5)

    # Simulate HTTP 200 with missing choices key
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"id": "chatcmpl-123", "created": 123456789}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(LLMResponseInvalidError) as exc_info:
            await provider.generate([LLMMessage(role="user", content="Hi")], fake_config)
        assert "choices" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_openai_provider_empty_choices_raises_typed_error():
    """Verify that a provider response with empty choices array raises LLMResponseInvalidError."""
    provider = OpenAIProvider()
    fake_config = LLMConfig(provider="omniroute", api_key="test-key", model="test-model", temperature=0.7, max_tokens=100, timeout_seconds=5)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"choices": []}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(LLMResponseInvalidError):
            await provider.generate([LLMMessage(role="user", content="Hi")], fake_config)


@pytest.mark.asyncio
async def test_openai_provider_http200_error_payload_raises_typed_error():
    """Verify that an HTTP 200 response with an error payload raises LLMResponseInvalidError."""
    provider = OpenAIProvider()
    fake_config = LLMConfig(provider="omniroute", api_key="test-key", model="test-model", temperature=0.7, max_tokens=100, timeout_seconds=5)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "error": {"message": "Invalid request or rate limit exceeded", "type": "invalid_request_error"}
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(LLMResponseInvalidError) as exc_info:
            await provider.generate([LLMMessage(role="user", content="Hi")], fake_config)
        assert "Invalid request" in str(exc_info.value)


@pytest.mark.asyncio
async def test_openai_provider_streaming_usage_only_chunk_does_not_crash():
    """Verify that an SSE frame with only token usage statistics (no choices) is safely skipped without KeyError."""
    provider = OpenAIProvider()
    fake_config = LLMConfig(provider="omniroute", api_key="test-key", model="test-model", temperature=0.7, max_tokens=100, timeout_seconds=5)

    # Simulate SSE stream with a normal delta chunk, a usage-only chunk, and [DONE]
    sse_lines = [
        b'data: {"choices": [{"delta": {"content": "Hello world"}}]}\n',
        b'data: {"usage": {"prompt_tokens": 12, "completion_tokens": 2, "total_tokens": 14}}\n',
        b'data: [DONE]\n',
    ]

    async def mock_aiter_lines():
        for line in sse_lines:
            yield line.decode("utf-8")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.aiter_lines = mock_aiter_lines
    mock_resp.aclose = AsyncMock()

    with patch("httpx.AsyncClient.send", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = mock_resp
        chunks = []
        async for chunk in provider.generate_stream([LLMMessage(role="user", content="Hi")], fake_config):
            chunks.append(chunk)

        assert len(chunks) == 2
        assert chunks[0].content_delta == "Hello world"
        assert chunks[1].usage == {"prompt_tokens": 12, "completion_tokens": 2, "total_tokens": 14}


@pytest.mark.asyncio
async def test_openai_provider_streaming_error_frame_raises_stream_interrupted():
    """Verify that an SSE frame containing an error object raises LLMStreamInterruptedError."""
    provider = OpenAIProvider()
    fake_config = LLMConfig(provider="omniroute", api_key="test-key", model="test-model", temperature=0.7, max_tokens=100, timeout_seconds=5)

    sse_lines = [
        b'data: {"choices": [{"delta": {"content": "Starting response..."}}]}\n',
        b'data: {"error": {"message": "GPU worker terminated mid-generation", "code": "worker_terminated"}}\n',
    ]

    async def mock_aiter_lines():
        for line in sse_lines:
            yield line.decode("utf-8")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.aiter_lines = mock_aiter_lines
    mock_resp.aclose = AsyncMock()

    with patch("httpx.AsyncClient.send", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = mock_resp
        with pytest.raises(LLMStreamInterruptedError) as exc_info:
            async for _ in provider.generate_stream([LLMMessage(role="user", content="Hi")], fake_config):
                pass
        assert "GPU worker terminated" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 2. Safe Error Presentation Tests (Phase 3.4)
# ---------------------------------------------------------------------------

def test_format_user_facing_error_replaces_raw_choices_keyerror():
    """Verify that a raw KeyError('choices') is translated into a helpful nontechnical message."""
    raw_error = KeyError("choices")
    msg = format_user_facing_error(raw_error)
    assert "choices" not in msg
    assert "invalid response format" in msg.lower() or "unexpected response structure" in msg.lower()


def test_format_user_facing_error_typed_exceptions():
    """Verify that typed provider exceptions are translated into clear, actionable messages."""
    assert "invalid response" in format_user_facing_error(LLMResponseInvalidError("Malformed JSON")).lower()
    assert "interrupted" in format_user_facing_error(LLMStreamInterruptedError("Connection dropped")).lower()
    assert "authentication failed" in format_user_facing_error(LLMAuthenticationError("Bad token")).lower()
    assert "rate limit reached" in format_user_facing_error(LLMRateLimitError("429 Too Many Requests")).lower()
    assert "timed out" in format_user_facing_error(LLMTimeoutError("Read timeout")).lower()
    assert "could not connect" in format_user_facing_error(LLMConnectionError("Connection refused")).lower()


# ---------------------------------------------------------------------------
# 3. Relevance & Context Selection (Phase 5: C++ vs Solar Isolation)
# ---------------------------------------------------------------------------

def test_filter_substantive_relevance_cpp_query_rejects_solar_paper():
    """Verify that a general C++ query rejects solar irradiance forecasting chunks."""
    solar_chunk = VectorSearchResult(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_title="Solar_irradiance__TechScience.pdf",
        knowledge_base_id=uuid.uuid4(),
        content="Deep learning models for GHI solar irradiance prediction using LSTM and RMSE metrics in agricultural regions.",
        score=0.45,
        metadata={"semantic_score": 0.45, "lexical_score": 0.0},
    )
    cpp_chunk = VectorSearchResult(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_title="C++ For Loop - W3Schools",
        knowledge_base_id=uuid.uuid4(),
        content="When you know exactly how many times you want to loop in C++, use the for loop with initialization, condition, and increment.",
        score=0.88,
        metadata={"semantic_score": 0.88, "lexical_score": 0.9},
    )

    results = [solar_chunk, cpp_chunk]
    filtered = filter_substantive_relevance("Do you have knowledge of C++?", results)

    # Only C++ chunk should pass; solar paper must be rejected
    assert len(filtered) == 1
    assert filtered[0].document_title == "C++ For Loop - W3Schools"


def test_filter_substantive_relevance_solar_query_rejects_cpp_chunks():
    """Verify that a solar forecasting query rejects C++ chunks and retains solar papers."""
    solar_chunk = VectorSearchResult(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_title="Solar_irradiance__TechScience.pdf",
        knowledge_base_id=uuid.uuid4(),
        content="Deep learning models for GHI solar irradiance prediction using LSTM and RMSE metrics.",
        score=0.85,
        metadata={"semantic_score": 0.85, "lexical_score": 0.8},
    )
    cpp_chunk = VectorSearchResult(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_title="C++ For Loop - W3Schools",
        knowledge_base_id=uuid.uuid4(),
        content="When you know exactly how many times you want to loop in C++, use the for loop.",
        score=0.25,
        metadata={"semantic_score": 0.25, "lexical_score": 0.0},
    )

    results = [solar_chunk, cpp_chunk]
    filtered = filter_substantive_relevance("Which model should I use next for solar irradiance forecasting?", results)

    assert len(filtered) == 1
    assert filtered[0].document_title == "Solar_irradiance__TechScience.pdf"


# ---------------------------------------------------------------------------
# 4. Citation Integrity & True Coordinate Provenance (Phase 4)
# ---------------------------------------------------------------------------

def test_context_builder_no_fabricated_bounding_boxes_or_page_one():
    """Verify that build_rag_context does NOT synthesize fake bounding boxes or default to page 1."""
    chunk = VectorSearchResult(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_title="Unprocessed_Document.pdf",
        knowledge_base_id=uuid.uuid4(),
        content="Plain text content without page numbers or spatial OCR bounding boxes.",
        score=0.9,
        metadata={},  # No bounding_box metadata
    )
    # Explicitly set page_number to None
    chunk.page_number = None

    messages, citations = build_rag_context(
        system_prompt="Test assistant",
        conversation_history=[],
        current_user_message="Summarize this",
        retrieved_results=[chunk],
    )

    assert len(citations) == 1
    cit = citations[0]
    # Critical verification: Must be None, NEVER fabricated standard US Letter or page 1!
    assert cit["bounding_box"] is None
    assert cit["page_number"] is None


def test_context_builder_preserves_genuine_extracted_bounding_box():
    """Verify that genuine spatial coordinates are preserved when present in metadata."""
    chunk = VectorSearchResult(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_title="Scientific_Figure.pdf",
        knowledge_base_id=uuid.uuid4(),
        content="Actual diagram and table extraction with genuine bounding box.",
        score=0.95,
        metadata={
            "bounding_box": {"page": 3, "x": 100.5, "y": 200.0, "width": 350.0, "height": 120.0}
        },
    )
    chunk.page_number = 3

    _, citations = build_rag_context(
        system_prompt="Test assistant",
        conversation_history=[],
        current_user_message="Look at figure",
        retrieved_results=[chunk],
    )

    assert len(citations) == 1
    cit = citations[0]
    assert cit["page_number"] == 3
    assert cit["bounding_box"] == {"page": 3, "x": 100.5, "y": 200.0, "width": 350.0, "height": 120.0}


# ---------------------------------------------------------------------------
# 5. Scientific Forecasting Rigor Guidelines (Phase 7)
# ---------------------------------------------------------------------------

def test_context_system_prompt_contains_forecasting_causal_leakage_guidelines():
    """Verify that the assembled system prompt strictly instructs causal forecasting constraints and baselines."""
    messages, _ = build_rag_context(
        system_prompt="Forecasting assistant",
        conversation_history=[],
        current_user_message="Recommend a model for solar forecasting",
        retrieved_results=[],
        citation_style="strict",
    )

    system_content = messages[0].content
    assert "Bidirectional architectures" in system_content or "Bi-LSTM" in system_content
    assert "historical input windows do not inherently leak future targets" in system_content
    assert "causal forecasting constraints" in system_content
    assert "baselines (persistence, linear/statistical, or gradient boosted trees" in system_content


# ---------------------------------------------------------------------------
# 6. Web Search Reliability & Honest State (Phase 6)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_arxiv_search_provider_parses_atom_feed():
    """Verify that ArxivSearchProvider parses Atom XML responses without errors."""
    provider = ArxivSearchProvider()
    atom_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <title type="html">ArXiv Query</title>
      <entry>
        <id>http://arxiv.org/abs/2401.12345v1</id>
        <published>2024-01-20T10:00:00Z</published>
        <title>Multi-Horizon Solar Irradiance Forecasting Using Temporal Convolutional Networks</title>
        <summary>We propose a causal temporal architecture for solar irradiance forecasting across multiple prediction horizons...</summary>
      </entry>
    </feed>"""

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = atom_xml
    mock_resp.content = atom_xml.encode("utf-8")

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        results = await provider.search("solar irradiance forecasting", max_results=3)

    assert len(results) == 1
    r = results[0]
    assert r["source"] in ("arXiv Preprint", "arXiv.org")
    assert "Solar Irradiance Forecasting" in r["title"]
    assert "causal temporal architecture" in r["snippet"]
    assert r["url"].endswith("2401.12345v1")
    assert r["publication_date"] == "2024-01-20"


@pytest.mark.asyncio
async def test_web_search_service_honest_not_configured_when_no_provider():
    """Verify that WebSearchService returns honest NOT_CONFIGURED when no search key or research query applies."""
    with patch.dict("os.environ", {}, clear=True):
        service = WebSearchService(tenant_id=uuid.uuid4())
        # Query without academic research keywords
        resp = await service.search("latest celebrity gossip news today", count=5)
        assert resp.get("status") == "NOT_CONFIGURED"
        assert "not configured" in resp.get("message", "").lower()
        assert "Direct URL reading is still available" in resp.get("message", "")
        assert len(resp.get("results", [])) == 0
