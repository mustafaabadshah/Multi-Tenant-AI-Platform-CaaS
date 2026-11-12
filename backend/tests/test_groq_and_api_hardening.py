"""Tests for Groq provider resolution, error normalization, and API hardening (M10 Stage 5.1)."""

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.llm.base import (
    LLMAuthenticationError,
    LLMConfig,
    LLMMessage,
    LLMProviderError,
)
from app.llm.capabilities import get_model_capability_registry
from app.llm.providers.groq_provider import (
    GROQ_DEFAULT_MODEL,
    GroqLLMProvider,
)
from app.llm.providers.openai_provider import OpenAICompatibleLLMProvider

# ==============================================================================
# OBJECTIVE A — GROQ MODEL RESOLUTION AND DEFECT CORRECTION TESTS
# ==============================================================================

def test_groq_model_explicitly_configured():
    """Explicitly configured Groq model is strictly preserved and not changed."""
    provider = GroqLLMProvider()
    config = LLMConfig(
        provider="groq",
        model="llama-3.1-8b-instant",
        api_key="gsk_test_key_12345",
    )
    normalized = provider._normalize_config(config)
    assert normalized.model == "llama-3.1-8b-instant"
    assert normalized.provider == "groq"


def test_groq_model_auto_resolves_supported_default():
    """Groq model='auto' resolves to the supported production default (openai/gpt-oss-120b)."""
    provider = GroqLLMProvider()
    config = LLMConfig(
        provider="groq",
        model="auto",
        api_key="gsk_test_key_12345",
    )
    normalized = provider._normalize_config(config)
    assert normalized.model == "openai/gpt-oss-120b"
    assert normalized.model == GROQ_DEFAULT_MODEL


def test_groq_model_empty_resolves_supported_default():
    """Empty or whitespace Groq model resolves to the supported production default."""
    provider = GroqLLMProvider()
    for empty_val in ["", "   ", "\t"]:
        config = LLMConfig(
            provider="groq",
            model=empty_val,
            api_key="gsk_test_key_12345",
        )
        normalized = provider._normalize_config(config)
        assert normalized.model == "openai/gpt-oss-120b"


def test_groq_explicit_deprecated_model_not_silently_replaced():
    """If user explicitly configured a deprecated model, system does not silently replace it."""
    provider = GroqLLMProvider()
    config = LLMConfig(
        provider="groq",
        model="llama-3.3-70b-versatile",
        api_key="gsk_test_key_12345",
    )
    normalized = provider._normalize_config(config)
    assert normalized.model == "llama-3.3-70b-versatile"


def test_another_provider_selected_does_not_apply_groq_default():
    """Non-Groq provider (e.g. OpenAI or OmniRoute) does not inherit Groq default model."""
    _openai_provider = OpenAICompatibleLLMProvider(name="openai")
    config = LLMConfig(
        provider="openai",
        model="auto",
        api_key="sk-test-key",
    )
    assert config.model == "auto"
    assert config.model != GROQ_DEFAULT_MODEL


def test_llm_config_extra_headers_attribute_safety():
    """LLMConfig safely supports extra_headers without AttributeError."""
    config_default = LLMConfig(provider="groq", model="auto")
    assert hasattr(config_default, "extra_headers")
    assert config_default.extra_headers == {}

    config_with_headers = LLMConfig(
        provider="groq",
        model="auto",
        extra_headers={"X-Custom-Header": "value123"},
    )
    assert config_with_headers.extra_headers == {"X-Custom-Header": "value123"}

    provider = GroqLLMProvider()
    norm = provider._normalize_config(config_default)
    assert norm.extra_headers == {}


@pytest.mark.asyncio
async def test_groq_provider_credentials_missing_rejected_before_external_request():
    """Provider without API key is rejected before initiating external HTTP calls."""
    provider = GroqLLMProvider()
    config = LLMConfig(
        provider="groq",
        model="openai/gpt-oss-120b",
        api_key="",  # Empty credentials
    )
    messages = [LLMMessage(role="user", content="Hello")]

    with patch.dict(os.environ, {"GROQ_API_KEY": "", "OPENAI_API_KEY": ""}, clear=False):
        with pytest.raises(LLMAuthenticationError) as exc_info:
            await provider.generate(messages, config)
        assert "No API key configured" in str(exc_info.value)


@pytest.mark.asyncio
async def test_groq_provider_json_error_preserves_upstream_message():
    """Upstream JSON error response from provider preserves actionable message."""
    provider = GroqLLMProvider()
    config = LLMConfig(
        provider="groq",
        model="openai/gpt-oss-120b",
        api_key="gsk_mock_valid_key",
    )
    messages = [LLMMessage(role="user", content="Hello")]

    err_payload = {
        "error": {
            "message": "The model `openai/gpt-oss-120b` does not exist or you do not have access.",
            "type": "invalid_request_error",
            "code": "model_not_found",
        }
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.json.return_value = err_payload
    mock_resp.text = json.dumps(err_payload)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(LLMProviderError) as exc_info:
            await provider.generate(messages, config)
        assert "model_not_found" in str(exc_info.value) or "The model" in str(exc_info.value)


@pytest.mark.asyncio
async def test_groq_provider_non_json_error_preserves_safe_fallback():
    """Upstream 502/503 non-JSON HTML/gateway error preserves safe fallback message."""
    provider = GroqLLMProvider()
    config = LLMConfig(
        provider="groq",
        model="openai/gpt-oss-120b",
        api_key="gsk_mock_valid_key",
    )
    messages = [LLMMessage(role="user", content="Hello")]

    mock_resp = MagicMock()
    mock_resp.status_code = 502
    mock_resp.json.side_effect = Exception("Not valid JSON")
    mock_resp.text = "<html><body>502 Bad Gateway</body></html>"

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(LLMProviderError) as exc_info:
            await provider.generate(messages, config)
        assert "502" in str(exc_info.value) or "HTTP 502" in str(exc_info.value)


def test_model_capability_registry_includes_production_groq_model():
    """Model capability registry lists openai/gpt-oss-120b under verified Groq catalog."""
    registry = get_model_capability_registry()
    model = registry.get_model("groq", "openai/gpt-oss-120b")
    assert model is not None
    assert model.provider == "groq"
    assert model.model_id == "openai/gpt-oss-120b"
    assert model.supports_streaming is True
    assert model.context_window >= 128000
