"""M28.16 Comprehensive Test Suite:
Provider Rate-Limit Recovery, Gemini Model Compatibility, Token Budgeting, and Citation Integrity.
"""

import json
import uuid
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from app.assistant_runtime.context import (
    build_rag_context,
    estimate_tokens,
    sanitize_untrusted_content,
)
from app.assistant_runtime.runtime import format_user_facing_error
from app.llm import LLMConfig
from app.llm.base import (
    LLMAuthenticationError,
    LLMConnectionError,
    LLMMessage,
    LLMModelUnavailableError,
    LLMRateLimitError,
    LLMResponse,
    LLMStreamChunk,
)
from app.llm.capabilities import get_model_capability_registry
from app.llm.providers.gemini_provider import GeminiLLMProvider
from app.llm.providers.groq_provider import GroqLLMProvider
from app.llm.providers.openai_provider import OpenAICompatibleLLMProvider
from app.observability.policy import ErrorCategory, categorize_error
from app.services.research.academic_search import (
    detect_academic_search_intent,
    execute_academic_search_preflight,
)
from app.vectorstores.base import VectorSearchResult


# =============================================================================
# 1. TOKEN ESTIMATOR & BUDGET ENFORCEMENT
# =============================================================================

def test_token_estimator_conservative():
    """Conservative estimator accounts for ~3.3 chars per token."""
    text = "Solar irradiance forecasting with Bi-LSTM models and RMSE metrics."
    tokens = estimate_tokens(text)
    # len is 66 chars -> 66 / 3.3 = 20 tokens
    assert tokens >= 18
    assert estimate_tokens("") == 0
    assert estimate_tokens("a") == 1


def test_build_rag_context_bounds_knowledge_tokens():
    """Knowledge blocks are strictly capped at max_knowledge_tokens to prevent TPM exhaustion."""
    chunks = [
        VectorSearchResult(
            chunk_id=str(uuid.uuid4()),
            document_id=f"doc_{i}",
            document_title=f"Paper {i}",
            knowledge_base_id=None,
            content="Long academic text description detailing empirical research findings. " * 30,
            score=0.9 - (i * 0.05),
        )
        for i in range(10)
    ]
    # Set max_knowledge_tokens = 500
    messages, citations = build_rag_context(
        system_prompt="Assistant prompt",
        conversation_history=[],
        current_user_message="Explain solar irradiance",
        retrieved_results=chunks,
        max_knowledge_tokens=500,
    )
    # Citations should be bounded to only the chunks that fit within the 500-token budget
    assert len(citations) < len(chunks)
    assert len(citations) <= 3
    # Provenance: citation numbers match 1-indexed count
    for idx, c in enumerate(citations, start=1):
        assert c["citation_num"] == idx


def test_empty_knowledge_context_does_not_instruct_fake_citations():
    """When no documents are retrieved, the prompt instructs the model NOT to generate fake citations."""
    messages, citations = build_rag_context(
        system_prompt="Assistant prompt",
        conversation_history=[],
        current_user_message="what knowledge you have",
        retrieved_results=[],
    )
    assert len(citations) == 0
    system_content = messages[0].content
    assert "NO KNOWLEDGE BASE SOURCES ATTACHED" in system_content
    assert "NEVER generate bracket citation badges like [1]" in system_content
    assert "</KNOWLEDGE_BASE_CONTEXT>" not in system_content


def test_no_solar_irradiance_prompt_leakage_in_unrelated_queries():
    """Generic assistants do not have hardcoded domain text in their system prompts."""
    messages, _ = build_rag_context(
        system_prompt="You are a general knowledge helper.",
        conversation_history=[],
        current_user_message="Hello, what do you know?",
        retrieved_results=[],
    )
    system_content = messages[0].content
    # Domain-specific terms should not appear in generic system prompts
    assert "solar irradiance" not in system_content.lower()
    assert "bi-lstm" not in system_content.lower()


# =============================================================================
# 2. GROQ PROVIDER & RATE LIMIT RESOLUTION
# =============================================================================

def test_groq_auto_model_resolves_to_gpt_oss_20b():
    """Groq 'auto' resolves to openai/gpt-oss-20b by default for active free-tier compatibility."""
    provider = GroqLLMProvider()
    cfg = LLMConfig(provider="groq", model="auto")
    normalized = provider._normalize_config(cfg)
    assert normalized.model == "openai/gpt-oss-20b"


def test_groq_explicit_model_preserved():
    """Explicit user selection of Groq models is respected."""
    provider = GroqLLMProvider()
    cfg = LLMConfig(provider="groq", model="llama-3.1-8b-instant")
    normalized = provider._normalize_config(cfg)
    assert normalized.model == "llama-3.1-8b-instant"


def test_openai_handle_http_error_429_parses_header_retry_after():
    """HTTP 429 parses Retry-After header and sets structured attributes."""
    provider = OpenAICompatibleLLMProvider(name="groq")
    headers = {"retry-after": "19.5"}
    err_text = json.dumps({"error": {"message": "Rate limit reached. Please try again later."}})

    with pytest.raises(LLMRateLimitError) as exc_info:
        provider._handle_http_error(429, err_text, headers=headers, model="llama-3.3-70b-versatile")

    err = exc_info.value
    assert err.retry_after == 19.5
    assert err.model == "llama-3.3-70b-versatile"
    assert err.provider == "groq"


def test_openai_handle_http_error_429_parses_groq_body_text_seconds():
    """Groq body 'Please try again in 19.9425s' is parsed when no header exists."""
    provider = OpenAICompatibleLLMProvider(name="groq")
    err_text = (
        '{"error":{"message":"Rate limit reached for model openai/gpt-oss-120b in organization ... '
        'tokens per minute (TPM): Limit 8000, Used 6216, Requested 4443. Please try again in 19.9425s."}}'
    )

    with pytest.raises(LLMRateLimitError) as exc_info:
        provider._handle_http_error(429, err_text, headers={}, model="openai/gpt-oss-120b")

    err = exc_info.value
    assert err.retry_after == pytest.approx(19.9425)
    assert err.limit_type == "TPM"
    assert err.model == "openai/gpt-oss-120b"


def test_openai_handle_http_error_429_parses_groq_body_text_milliseconds():
    """Groq body 'Please try again in 500ms' is converted to seconds."""
    provider = OpenAICompatibleLLMProvider(name="groq")
    err_text = '{"error":{"message":"Rate limit reached. Please try again in 500ms."}}'

    with pytest.raises(LLMRateLimitError) as exc_info:
        provider._handle_http_error(429, err_text, headers={}, model="llama-3.3-70b-versatile")

    err = exc_info.value
    assert err.retry_after == 0.5


def test_openai_handle_http_error_404_raises_model_unavailable():
    """HTTP 404 raises LLMModelUnavailableError instead of generic LLMProviderError."""
    provider = OpenAICompatibleLLMProvider(name="groq")
    err_text = '{"error":{"message":"The model `deprecated-model` does not exist."}}'

    with pytest.raises(LLMModelUnavailableError) as exc_info:
        provider._handle_http_error(404, err_text, model="deprecated-model")

    err = exc_info.value
    assert err.model == "deprecated-model"
    assert err.provider == "groq"


# =============================================================================
# 3. GEMINI MODEL RESOLUTION & ERROR HANDLING
# =============================================================================

def test_gemini_auto_resolves_to_gemini_3_5_flash_lite():
    """Gemini 'auto' resolves to current production default 'gemini-3.5-flash-lite'."""
    provider = GeminiLLMProvider()
    resolved = provider._resolve_model("auto")
    assert resolved == "gemini-3.5-flash-lite"


def test_gemini_model_path_strips_leading_models_prefix():
    """Gemini model normalization strips 'models/' prefix to prevent /models/models/... path duplication."""
    provider = GeminiLLMProvider()
    resolved = provider._resolve_model("models/gemini-3.5-flash-lite")
    assert resolved == "gemini-3.5-flash-lite"

    resolved_sub = provider._resolve_model("models/gemini-3.8-flash")
    assert resolved_sub == "gemini-3.8-flash"


@pytest.mark.asyncio
async def test_gemini_generate_404_raises_model_unavailable_not_connection_error():
    """Gemini HTTP 404 must raise LLMModelUnavailableError, never LLMConnectionError."""
    provider = GeminiLLMProvider()
    config = LLMConfig(provider="gemini", model="gemini-1.5-flash", api_key="test-key")

    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.is_success = False
    mock_resp.json.return_value = {
        "error": {
            "code": 404,
            "message": "models/gemini-1.5-flash is not found for API version v1beta, or is not supported for generateContent.",
            "status": "NOT_FOUND",
        }
    }

    with patch("httpx.AsyncClient.post", AsyncMock(return_value=mock_resp)):
        with pytest.raises(LLMModelUnavailableError) as exc_info:
            await provider.generate([LLMMessage(role="user", content="Hello")], config)

        err = exc_info.value
        assert err.model == "gemini-1.5-flash"
        assert err.provider == "gemini"
        assert "404" in str(err)


@pytest.mark.asyncio
async def test_gemini_stream_404_raises_model_unavailable():
    """Gemini streaming HTTP 404 must raise LLMModelUnavailableError."""
    provider = GeminiLLMProvider()
    config = LLMConfig(provider="gemini", model="gemini-1.5-flash", api_key="test-key")

    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.is_success = False
    err_payload = json.dumps({
        "error": {
            "code": 404,
            "message": "models/gemini-1.5-flash is not found for API version v1beta.",
        }
    }).encode("utf-8")
    mock_resp.aread = AsyncMock(return_value=err_payload)

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_stream_ctx = MagicMock()
    mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)
    mock_client.stream.return_value = mock_stream_ctx

    with patch("httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(LLMModelUnavailableError) as exc_info:
            async for _ in provider.generate_stream([LLMMessage(role="user", content="Hi")], config):
                pass

        assert exc_info.value.model == "gemini-1.5-flash"


@pytest.mark.asyncio
async def test_gemini_list_available_models_filters_generate_content():
    """Gemini list_available_models only returns models supporting generateContent."""
    provider = GeminiLLMProvider()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "models": [
            {
                "name": "models/gemini-2.0-flash",
                "displayName": "Gemini 2.0 Flash",
                "supportedGenerationMethods": ["generateContent", "countTokens"],
            },
            {
                "name": "models/text-embedding-004",
                "displayName": "Text Embedding 004",
                "supportedGenerationMethods": ["embedContent"],
            },
        ]
    }

    with patch("httpx.AsyncClient.get", AsyncMock(return_value=mock_resp)):
        models = await provider.list_available_models(api_key="fake-key")

    assert len(models) == 1
    assert models[0]["name"] == "gemini-2.0-flash"


# =============================================================================
# 4. ERROR CATEGORIZATION & OBSERVABILITY
# =============================================================================

def test_error_categorization_rate_limited():
    """Rate limit errors are categorized as RATE_LIMITED."""
    err = LLMRateLimitError("Limit exceeded", retry_after=20.0)
    category, summary = categorize_error(err)
    assert category == ErrorCategory.RATE_LIMITED
    assert "rate limit" in summary.lower()


def test_error_categorization_model_unavailable():
    """Model not found / 404 errors are categorized as MODEL_UNAVAILABLE."""
    err = LLMModelUnavailableError("Gemini model not found (HTTP 404)")
    category, summary = categorize_error(err)
    assert category == ErrorCategory.MODEL_UNAVAILABLE
    assert "model is unavailable" in summary.lower()


def test_format_user_facing_error_rate_limit_with_seconds():
    """User-facing message shows seconds to wait when retry_after is available."""
    err = LLMRateLimitError("Groq 429", retry_after=19.94)
    msg = format_user_facing_error(err)
    assert "20s" in msg or "19s" in msg or "wait" in msg.lower()
    assert "rate limit" in msg.lower()


def test_format_user_facing_error_model_unavailable():
    """User-facing message guides user to settings when model is unavailable."""
    err = LLMModelUnavailableError("Model not found (HTTP 404)")
    msg = format_user_facing_error(err)
    assert "Assistant settings" in msg or "supported model" in msg


# =============================================================================
# 5. MODEL CAPABILITY REGISTRY
# =============================================================================

def test_capability_registry_groq_and_gemini_models():
    """Registry lists verified models with streaming and tool capabilities."""
    reg = get_model_capability_registry()
    groq_models = reg.get_by_provider("groq")
    groq_ids = [m.model_id for m in groq_models]
    assert "llama-3.3-70b-versatile" in groq_ids
    assert "llama-3.1-8b-instant" in groq_ids

    gemini_models = reg.get_by_provider("gemini")
    gemini_ids = [m.model_id for m in gemini_models]
    assert "gemini-3.5-flash-lite" in gemini_ids
    assert "gemini-3.8-flash" in gemini_ids
    assert "gemini-2.0-flash" in gemini_ids


# =============================================================================
# 6. DETERMINISTIC RESEARCH QUALITY & SOLAR COMPARISON FIXTURE (PHASE 5)
# =============================================================================

@pytest.mark.asyncio
async def test_academic_search_solar_irradiance_comparison_pipeline():
    """Verify deterministic execution for:
    'Search recent solar irradiance forecasting papers and compare them with my uploaded paper.'
    """
    user_prompt = "Search recent solar irradiance forecasting papers and compare them with my uploaded paper."
    is_acad, acad_query, acad_comp, acad_recent = detect_academic_search_intent(user_prompt)
    assert is_acad is True
    assert "solar irradiance forecasting" in acad_query.lower()
    assert acad_comp is True
    assert acad_recent is True

    # Deterministic mock arXiv preprints
    mock_arxiv_results = [
        {
            "url": "https://arxiv.org/abs/2401.00001v1",
            "title": "Deep Learning for Solar Irradiance Forecasting: A Survey",
            "snippet": "Recent advances in photovoltaic power and solar irradiance prediction using deep neural architectures.",
            "publication_date": "2024-01-01T00:00:00Z",
            "authors": "A. Researcher",
            "pdf_url": "https://arxiv.org/pdf/2401.00001v1",
        },
        {
            "url": "https://arxiv.org/abs/2402.00002v1",
            "title": "Probabilistic Solar Forecasting with Transformer Networks",
            "snippet": "Transformer-based quantile regression for multi-step solar forecasting with causal masking.",
            "publication_date": "2024-02-01T00:00:00Z",
            "authors": "B. Scientist",
            "pdf_url": "https://arxiv.org/pdf/2402.00002v1",
        },
    ]

    # Deterministic mock uploaded document chunk
    doc_chunk = VectorSearchResult(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        knowledge_base_id=uuid.uuid4(),
        score=0.92,
        content="Our experimental setup compares persistence baselines with bi-directional recurrent models on hourly irradiance.",
        document_title="My Solar Forecasting Study.pdf",
        metadata={"source_type": "document", "document_name": "My Solar Forecasting Study.pdf", "page_number": 3},
    )

    with patch("app.services.web.search.ArxivSearchProvider.search", AsyncMock(return_value=mock_arxiv_results)):
        acad_chunks = await execute_academic_search_preflight(
            query=acad_query,
            tenant_id=uuid.uuid4(),
            wants_recent=acad_recent,
            max_results=2,
        )

        assert len(acad_chunks) == 2
        assert acad_chunks[0].metadata["domain"] == "arxiv.org"
        assert acad_chunks[0].metadata["is_preprint"] is True

        # Assemble context combining the arXiv preprints and the uploaded document chunk
        combined_candidates = acad_chunks + [doc_chunk]
        messages, citations = build_rag_context(
            system_prompt="You are a research assistant.",
            conversation_history=[],
            current_user_message=user_prompt,
            retrieved_results=combined_candidates,
            max_knowledge_tokens=1200,
        )

        system_text = messages[0].content
        # Verified prompt budgeting & provenance
        assert "<KNOWLEDGE_BASE_CONTEXT>" in system_text
        assert "Deep Learning for Solar Irradiance Forecasting" in system_text
        assert "My Solar Forecasting Study.pdf" in system_text
        assert len(citations) == 3
        # Check that arXiv web source and PDF document citations are cleanly differentiated
        sources = [c["source_type"] for c in citations]
        assert "web" in sources
        assert "document" in sources
        # Knowledge context tokens within 1200 token budget
        kb_text = system_text[system_text.find("<KNOWLEDGE_BASE_CONTEXT>"):system_text.find("</KNOWLEDGE_BASE_CONTEXT>")]
        assert estimate_tokens(kb_text) <= 1200
        # Total prompt budget remains well under provider limits (< 2500 tokens)
        assert estimate_tokens(system_text) < 2500

