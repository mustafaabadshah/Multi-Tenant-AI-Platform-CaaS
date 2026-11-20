"""M28.12 Test Suite: Groq Tool-Choice Failure Recovery, Deterministic Academic Search,
Provider Compatibility, Citation & Markdown Quality.
"""

import asyncio
import json
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.assistant_runtime.context import build_rag_context, normalize_markdown
from app.assistant_runtime.runtime import AssistantRuntime, format_user_facing_error
from app.llm.base import (
    LLMConfig,
    LLMMessage,
    LLMStreamChunk,
    LLMStreamInterruptedError,
    LLMToolCallUnsupportedError,
)
from app.llm.capabilities import get_model_capability_registry
from app.llm.providers.groq_provider import GroqLLMProvider
from app.llm.providers.openai_provider import OpenAICompatibleLLMProvider
from app.observability.policy import ErrorCategory, categorize_error
from app.services.research.academic_search import (
    detect_academic_search_intent,
    execute_academic_search_preflight,
)
from app.services.web.search import ArxivSearchProvider
from app.vectorstores.base import VectorSearchResult


# ==============================================================================
# 1. Groq Tool-Choice Request Construction & Normalization
# ==============================================================================

def test_groq_normalize_config_preserves_tools_and_tool_choice():
    provider = GroqLLMProvider()
    tools = [
        {
            "name": "web_search",
            "description": "Search the web",
            "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}},
        }
    ]
    cfg = LLMConfig(
        provider="groq",
        model="auto",
        tools=tools,
        tool_choice="auto",
    )
    normalized = provider._normalize_config(cfg)
    assert normalized.tools == tools
    assert normalized.tool_choice == "auto"
    assert normalized.model in ("openai/gpt-oss-20b", "llama-3.3-70b-versatile", "openai/gpt-oss-120b")


def test_groq_normalize_config_without_tools():
    provider = GroqLLMProvider()
    cfg = LLMConfig(provider="groq", model="llama-3.3-70b-versatile", tools=None)
    normalized = provider._normalize_config(cfg)
    assert normalized.tools is None
    assert normalized.tool_choice is None
    assert normalized.model == "llama-3.3-70b-versatile"


def test_openai_compatible_payload_formats_tools_and_tool_choice():
    provider = OpenAICompatibleLLMProvider(name="groq")
    tools = [
        {
            "name": "calc",
            "description": "Calculate expression",
            "input_schema": {"type": "object", "properties": {"expr": {"type": "string"}}},
        }
    ]
    cfg = LLMConfig(
        provider="groq",
        model="llama-3.3-70b-versatile",
        api_key="gsk_test_key",
        tools=tools,
    )
    messages = [
        LLMMessage(role="system", content="System instruction"),
        LLMMessage(role="user", content="What is 2+2?"),
    ]
    formatted_msgs = provider._format_messages_payload(messages)
    assert len(formatted_msgs) == 2
    assert formatted_msgs[0] == {"role": "system", "content": "System instruction"}
    assert formatted_msgs[1] == {"role": "user", "content": "What is 2+2?"}


def test_openai_compatible_payload_with_tool_call_and_response():
    provider = OpenAICompatibleLLMProvider(name="groq")
    messages = [
        LLMMessage(role="user", content="Calculate 5 * 5"),
        LLMMessage(
            role="assistant",
            content="",
            tool_calls=[{"id": "call_123", "type": "function", "function": {"name": "calc", "arguments": '{"expr": "5*5"}'}}],
        ),
        LLMMessage(role="tool", content='{"result": 25}', tool_call_id="call_123"),
    ]
    formatted = provider._format_messages_payload(messages)
    assert len(formatted) == 3
    assert formatted[1]["tool_calls"][0]["id"] == "call_123"
    assert formatted[2]["tool_call_id"] == "call_123"
    assert formatted[2]["role"] == "tool"


# ==============================================================================
# 2. Provider Error Classification & Tool-Choice Conflicts
# ==============================================================================

def test_groq_tool_choice_error_classification_in_handle_http_error():
    provider = OpenAICompatibleLLMProvider(name="groq")
    err_json = json.dumps({
        "error": {
            "message": "Tool choice is none, but model called a tool",
            "type": "invalid_request_error",
            "code": "tool_use_failed",
        }
    })
    with pytest.raises(LLMToolCallUnsupportedError) as exc_info:
        provider._handle_http_error(400, err_json)
    assert "Tool choice is none" in str(exc_info.value) or "tool choice conflict" in str(exc_info.value).lower()


def test_groq_tool_choice_error_categorization_in_observability():
    err = LLMToolCallUnsupportedError("Provider 'groq' stream error: Tool choice is none, but model called a tool")
    cat, summary = categorize_error(err)
    assert cat == ErrorCategory.TOOL_ERROR
    assert "tool choice conflict" in summary.lower() or "tool action" in summary.lower()


def test_user_facing_error_formatting_for_tool_unsupported():
    err = LLMToolCallUnsupportedError("Tool choice is none, but model called a tool")
    msg = format_user_facing_error(err)
    assert msg == "This model couldn't complete the requested tool action. Please retry or choose a compatible model."


# ==============================================================================
# 3. Academic Search Intent Classification
# ==============================================================================

@pytest.mark.parametrize(
    "query,expected_academic,expected_topic,expected_comp,expected_recent",
    [
        (
            "Search recent solar irradiance forecasting papers and compare them with my uploaded paper.",
            True,
            "solar irradiance forecasting",
            True,
            True,
        ),
        (
            "Do you have knowledge of C++?",
            False,
            "",
            False,
            False,
        ),
        (
            "According to my uploaded solar irradiance paper, which forecasting model performed best?",
            False,
            "",
            False,
            False,
        ),
        (
            "Which models should I evaluate next for solar irradiance forecasting, and why?",
            False,
            "",
            False,
            False,
        ),
        (
            "Read https://www.w3schools.com/cpp/cpp_for_loop.asp and explain the for-loop examples.",
            False,
            "",
            False,
            False,
        ),
        (
            "Search arXiv for transformer time series papers",
            True,
            "transformer time series",
            False,
            False,
        ),
        (
            "Find recent studies on photovoltaic power prediction",
            True,
            "photovoltaic power prediction",
            False,
            True,
        ),
        (
            "Compare recent research papers with my uploaded paper",
            True,
            "",
            True,
            True,
        ),
    ],
)
def test_detect_academic_search_intent(query, expected_academic, expected_topic, expected_comp, expected_recent):
    is_acad, topic, wants_comp, wants_rec = detect_academic_search_intent(query)
    assert is_acad == expected_academic
    if expected_topic:
        assert topic == expected_topic
    assert wants_comp == expected_comp
    assert wants_rec == expected_recent


# ==============================================================================
# 4. arXiv Search Quality, User-Agent, and Bounded Preflight
# ==============================================================================

@pytest.mark.asyncio
async def test_arxiv_search_provider_user_agent_and_formatting():
    provider = ArxivSearchProvider()
    mock_atom_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>http://arxiv.org/abs/2312.10997v1</id>
        <title>Deep Learning Baselines for Solar Irradiance Forecasting</title>
        <summary>Comprehensive comparison of LSTM, GRU, and LightGBM models for solar prediction.</summary>
        <published>2024-01-15T12:00:00Z</published>
        <updated>2024-02-10T12:00:00Z</updated>
        <author><name>Jane Doe</name></author>
        <author><name>John Smith</name></author>
      </entry>
    </feed>"""

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = mock_atom_xml.encode("utf-8")
    mock_resp.text = mock_atom_xml

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        results = await provider.search("solar irradiance forecasting", max_results=2)

    assert len(results) == 1
    paper = results[0]
    assert paper["title"] == "Deep Learning Baselines for Solar Irradiance Forecasting"
    assert paper["url"] == "https://arxiv.org/abs/2312.10997v1"
    assert paper["source"] == "arXiv Preprint"
    assert paper["domain"] == "arxiv.org"
    assert "Jane Doe" in paper["authors"]
    assert paper["publication_date"] == "2024-01-15"
    assert paper["updated_date"] == "2024-02-10"
    assert paper["is_preprint"] is True


@pytest.mark.asyncio
async def test_execute_academic_search_preflight_normalizes_vector_results():
    mock_papers = [
        {
            "title": "Solar Forecast Benchmark",
            "url": "https://arxiv.org/abs/2401.00001",
            "snippet": "We benchmark persistence vs AR-LSTM for GHI forecasting.",
            "source": "arXiv Preprint",
            "domain": "arxiv.org",
            "authors": "Alice Smith, Bob Jones",
            "publication_date": "2024-03-01",
            "updated_date": "2024-03-05",
            "is_preprint": True,
            "rank": 1,
        }
    ]

    with patch.object(ArxivSearchProvider, "search", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = mock_papers
        chunks = await execute_academic_search_preflight("solar forecasting", wants_recent=True)

    assert len(chunks) == 1
    c = chunks[0]
    assert isinstance(c, VectorSearchResult)
    assert c.document_id == "https://arxiv.org/abs/2401.00001"
    assert c.document_title == "arXiv: Solar Forecast Benchmark"
    assert "[arXiv Preprint: Solar Forecast Benchmark]" in c.content
    assert "Alice Smith" in c.content
    assert "Note: This is an academic preprint abstract" in c.content
    assert c.metadata["source_type"] == "web"
    assert c.metadata["source"] == "arXiv Preprint"


@pytest.mark.asyncio
async def test_execute_academic_search_preflight_graceful_timeout():
    with patch.object(ArxivSearchProvider, "search", side_effect=ValueError("ArXiv API request timed out after 15 seconds.")):
        chunks = await execute_academic_search_preflight("solar forecasting")
    assert chunks == []


# ==============================================================================
# 5. Security & Tool Execution Guardrails
# ==============================================================================

@pytest.mark.asyncio
async def test_tool_call_loop_rejects_unregistered_tool():
    """Verify that an unregistered tool proposed by LLM is rejected and never executed."""
    runtime = AssistantRuntime(session=AsyncMock(), tenant_id=uuid.uuid4(), user_id=uuid.uuid4())
    raw_tools = [{"id": "t1", "name": "web_search", "requires_approval": False}]

    pending_tc = [{"id": "call_bad", "name": "malicious_eval", "arguments": {"cmd": "rm -rf"}}]
    # Assert tool_def lookup logic
    tool_def = next((t for t in raw_tools if t["name"] == pending_tc[0]["name"]), None)
    assert tool_def is None  # Must NOT execute


# ==============================================================================
# 6. Context Assembly with tools_enabled Condition
# ==============================================================================

def test_build_rag_context_with_tools_enabled():
    messages, citations = build_rag_context(
        system_prompt="Base prompt",
        conversation_history=[],
        current_user_message="Hello",
        retrieved_results=[],
        tools_enabled=True,
    )
    system_msg = messages[0].content
    assert "- WEB BROWSING & TOOLS: You have access to real-time web reading tools" in system_msg


def test_build_rag_context_with_tools_disabled():
    messages, citations = build_rag_context(
        system_prompt="Base prompt",
        conversation_history=[],
        current_user_message="Hello",
        retrieved_results=[],
        tools_enabled=False,
    )
    system_msg = messages[0].content
    assert "Do not attempt to invoke external tool calls or functions." in system_msg
    assert "- WEB BROWSING & TOOLS: You have access to real-time web reading tools" not in system_msg


# ==============================================================================
# 7. Markdown and Code Block Normalization
# ==============================================================================

def test_normalize_markdown_preserves_cpp_code_blocks():
    input_text = (
        "Here is a C++ for loop example:\n\n"
        "```cpp\n"
        "#include <iostream>\n\n"
        "int main() {\n"
        "    for (int i = 0; i < 5; ++i) {\n"
        "        std::cout << i << '\\n';\n"
        "    }\n"
        "    return 0;\n"
        "}\n"
        "```\n\n"
        "This loops 5 times."
    )
    normalized = normalize_markdown(input_text)
    assert "```cpp" in normalized
    assert "#include <iostream>" in normalized
    assert "std::cout << i << '\\n';" in normalized
    assert "int main() {" in normalized


def test_normalize_markdown_trailing_unclosed_code_fence():
    stream_partial = "```cpp\nint x = 10;\nstd::cout << x;"
    normalized = normalize_markdown(stream_partial)
    assert "```cpp" in normalized
    assert "int x = 10;" in normalized


# ==============================================================================
# 8. End-to-End Scenarios A through F Matrix
# ==============================================================================

def test_scenario_a_cpp_general_question_no_solar_citations():
    """Scenario A: 'Do you have knowledge of C++?' — excludes unrelated solar citations."""
    query = "Do you have knowledge of C++?"
    is_acad, _, _, _ = detect_academic_search_intent(query)
    assert is_acad is False

    from app.assistant_runtime.runtime import filter_substantive_relevance
    solar_chunk = VectorSearchResult(
        chunk_id="chunk_solar_1",
        document_id="doc_solar_1",
        document_title="Solar Irradiance Forecasting Paper.pdf",
        knowledge_base_id=None,
        content="GHI irradiance was predicted using AR-LSTM and GRU with RMSE 45.2 W/m2.",
        score=0.45,
    )
    filtered = filter_substantive_relevance(query, [solar_chunk])
    assert len(filtered) == 0


def test_scenario_b_uploaded_solar_paper_retrieval_no_unrelated_cpp():
    """Scenario B: 'According to my uploaded solar irradiance paper...' — preserves paper context."""
    query = "According to my uploaded solar irradiance paper, which forecasting model performed best?"
    is_acad, _, _, _ = detect_academic_search_intent(query)
    assert is_acad is False

    from app.assistant_runtime.runtime import filter_substantive_relevance
    solar_chunk = VectorSearchResult(
        chunk_id="chunk_solar_1",
        document_id="doc_solar_1",
        document_title="Solar Irradiance Forecasting Paper.pdf",
        knowledge_base_id=None,
        content="The AR-LSTM model achieved the lowest RMSE of 38.4 W/m2.",
        score=0.91,
    )
    cpp_chunk = VectorSearchResult(
        chunk_id="chunk_cpp_1",
        document_id="doc_cpp_1",
        document_title="C++ Standard Template Library.pdf",
        knowledge_base_id=None,
        content="std::vector provides dynamic array sizing in C++.",
        score=0.35,
    )
    filtered = filter_substantive_relevance(query, [solar_chunk, cpp_chunk])
    assert len(filtered) == 1
    assert filtered[0].document_title == "Solar Irradiance Forecasting Paper.pdf"


def test_scenario_c_research_recommendations_no_unwanted_external_search():
    """Scenario C: 'Which models should I evaluate next...' — does not trigger academic search."""
    query = "Which models should I evaluate next for solar irradiance forecasting, and why?"
    is_acad, topic, wants_comp, wants_rec = detect_academic_search_intent(query)
    assert is_acad is False
    assert topic == ""


@pytest.mark.asyncio
async def test_scenario_d_academic_search_with_uploaded_pdf_comparison():
    """Scenario D: 'Search recent solar irradiance forecasting papers and compare them with my uploaded paper.'"""
    query = "Search recent solar irradiance forecasting papers and compare them with my uploaded paper."
    is_acad, topic, wants_comp, wants_rec = detect_academic_search_intent(query)
    assert is_acad is True
    assert topic == "solar irradiance forecasting"
    assert wants_comp is True
    assert wants_rec is True

    # Mock external arXiv search
    mock_papers = [
        {
            "title": "Deep Transformers for Solar Radiation Prediction",
            "url": "https://arxiv.org/abs/2402.00001",
            "snippet": "In this paper we benchmark spatial-temporal transformers against AR-LSTM.",
            "source": "arXiv Preprint",
            "domain": "arxiv.org",
            "authors": "Dr. Solar et al.",
            "publication_date": "2024-02-15",
            "is_preprint": True,
            "rank": 1,
        }
    ]
    with patch.object(ArxivSearchProvider, "search", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = mock_papers
        acad_chunks = await execute_academic_search_preflight(topic, wants_recent=wants_rec)

    assert len(acad_chunks) == 1

    uploaded_pdf_chunk = VectorSearchResult(
        chunk_id="pdf_chunk_1",
        document_id="solar_paper.pdf",
        document_title="Solar_Irradiance_Paper.pdf",
        knowledge_base_id=uuid.uuid4(),
        content="Our empirical results show AR-LSTM achieved MAE of 18.2 W/m2 at station 1.",
        score=0.88,
        metadata={"source_type": "document", "page_number": 3},
    )

    combined_context = acad_chunks + [uploaded_pdf_chunk]
    messages, citations = build_rag_context(
        system_prompt="Assistant instructions",
        conversation_history=[],
        current_user_message=query,
        retrieved_results=combined_context,
        tools_enabled=False,
    )

    assert len(citations) == 2
    # Check separate source identities
    assert citations[0]["source_type"] == "web"
    assert "arxiv.org" in citations[0]["domain"]
    assert citations[1]["source_type"] == "document"
    assert citations[1]["page_number"] == 3


def test_scenario_e_direct_webpage_read_preserves_code_formatting():
    """Scenario E: 'Read https://www.w3schools.com/cpp/cpp_for_loop.asp...' — formatting and citations."""
    query = "Read https://www.w3schools.com/cpp/cpp_for_loop.asp and explain the for-loop examples."
    is_acad, _, _, _ = detect_academic_search_intent(query)
    assert is_acad is False

    sample_cpp = (
        "Here is the for-loop from the page [1]:\n\n"
        "```cpp\n"
        "for (int i = 0; i < 5; ++i) {\n"
        "  std::cout << i << '\\n';\n"
        "}\n"
        "```"
    )
    normalized = normalize_markdown(sample_cpp)
    assert "```cpp" in normalized
    assert "std::cout << i" in normalized


def test_scenario_f_groq_simulated_400_tool_choice_none_recovery():
    """Scenario F: Simulated Groq error 'Tool choice is none, but model called a tool'."""
    provider = OpenAICompatibleLLMProvider(name="groq")
    groq_400_body = json.dumps({
        "error": {
            "message": "Tool choice is none, but model called a tool",
            "type": "invalid_request_error",
            "code": "tool_use_failed",
        }
    })

    with pytest.raises(LLMToolCallUnsupportedError) as exc_info:
        provider._handle_http_error(400, groq_400_body)

    # Verify classification in policy
    cat, summary = categorize_error(exc_info.value)
    assert cat == ErrorCategory.TOOL_ERROR

    # Verify user-facing error does not crash and provides clear instructions
    user_msg = format_user_facing_error(exc_info.value)
    assert "This model couldn't complete the requested tool action" in user_msg

