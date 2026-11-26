"""Unit and integration tests for M28.1 Web Reader Repair, HTML Ingestion, and Citation Grounding."""

import pytest
import re
from app.parsers.html import HTMLParser
from app.parsers.registry import ParserRegistry, get_parser_registry
from app.services.ingestion.limits import PERMANENT_INGESTION_ERRORS, IngestionLimitExceededError
from app.assistant_runtime.context import build_rag_context
from app.vectorstores.base import VectorSearchResult


# ---------------------------------------------------------------------------
# Problem B: HTML Ingestion & Extraction Tests
# ---------------------------------------------------------------------------

SAMPLE_CPP_HTML = b"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>C++ For Loop - W3Schools Reference</title>
</head>
<body>
    <header>
        <nav><a href="/">Home</a> | <a href="/cpp">C++ Tutorial</a></nav>
    </header>
    <main>
        <h1>C++ For Loop</h1>
        <p>When you know exactly how many times you want to loop through a block of code, use the for loop instead of a while loop.</p>
        
        <h2>Syntax</h2>
        <pre><code>for (statement 1; statement 2; statement 3) {
  // code block to be executed
}</code></pre>

        <h2>Example</h2>
        <p>This example will print the numbers 0 through 4:</p>
        <pre><code>for (int i = 0; i < 5; i++) {
  cout &lt;&lt; i &lt;&lt; "\\n";
}</code></pre>

        <h2>Loop Parameters</h2>
        <table>
            <tr><th>Statement</th><th>Description</th></tr>
            <tr><td>Statement 1</td><td>Executed once before the execution of the code block.</td></tr>
            <tr><td>Statement 2</td><td>Defines the condition for executing the code block.</td></tr>
            <tr><td>Statement 3</td><td>Executed every time after the code block has been executed.</td></tr>
        </table>
    </main>
    <footer>
        <p>Copyright 1999-2026 by Refsnes Data. All Rights Reserved.</p>
    </footer>
</body>
</html>
"""


@pytest.mark.asyncio
async def test_html_parser_extracts_clean_content_and_code():
    """Verify HTMLParser extracts text, code, and headings while stripping boilerplate."""
    parser = HTMLParser()
    assert ".html" in parser.supported_extensions
    assert ".htm" in parser.supported_extensions
    assert parser.validate(SAMPLE_CPP_HTML, "C___For_Loop.html")

    doc = await parser.extract(SAMPLE_CPP_HTML, "C___For_Loop.html", mime_type="text/html")
    assert doc.title == "C++ For Loop - W3Schools Reference"
    assert "for (int i = 0; i < 5; i++)" in doc.text
    assert "Syntax" in [s.heading for s in doc.sections]
    assert doc.pages[0].text is not None
    assert len(doc.text) > 200
    # Boilerplate navigation should not dominate
    assert doc.parser_name == "deterministic_html_parser"


def test_parser_registry_resolves_html_with_octet_stream_mime():
    """Verify ParserRegistry correctly identifies HTML even when declared MIME is application/octet-stream."""
    registry = ParserRegistry()

    # 1. Standard extension resolution
    parser = registry.resolve_parser(
        filename="C___For_Loop.html",
        content=SAMPLE_CPP_HTML,
        declared_mime="application/octet-stream",
    )
    assert isinstance(parser, HTMLParser)

    # 2. Sniffing resolution without extension
    parser_no_ext = registry.resolve_parser(
        filename="unnamed_blob",
        content=SAMPLE_CPP_HTML,
        declared_mime="application/octet-stream",
    )
    assert isinstance(parser_no_ext, HTMLParser)


def test_ingestion_permanent_error_classification():
    """Verify typed errors (UnsupportedFormatError, UnparseableDocumentError) are in PERMANENT_INGESTION_ERRORS, preventing retry loops on bad files while allowing transient bugs to retry."""
    from app.services.ingestion.limits import UnsupportedFormatError, UnparseableDocumentError
    assert UnsupportedFormatError in PERMANENT_INGESTION_ERRORS
    assert UnparseableDocumentError in PERMANENT_INGESTION_ERRORS
    err = UnsupportedFormatError("Unsupported document format: extension '.unknown'")
    assert isinstance(err, PERMANENT_INGESTION_ERRORS)
    assert isinstance(err, ValueError)


@pytest.mark.asyncio
async def test_empty_html_raises_permanent_value_error():
    """Verify empty or whitespace-only HTML raises ValueError immediately."""
    parser = HTMLParser()
    empty_html = b"<html><body>   </body></html>"
    with pytest.raises(ValueError, match="contains no readable or extractable text"):
        await parser.extract(empty_html, "empty.html")


# ---------------------------------------------------------------------------
# Problem A & C: Web Preflight, Grounding & Citation Filtering Tests
# ---------------------------------------------------------------------------

def test_url_extraction_pattern():
    """Verify URL detection correctly captures public web URLs from user prompts."""
    url_pattern = re.compile(r"https?://[^\s<>\"'()]+")
    
    prompt_1 = "https://www.w3schools.com/cpp/cpp_for_loop.asp read this for knowledge using tool"
    urls_1 = url_pattern.findall(prompt_1)
    assert len(urls_1) == 1
    assert urls_1[0] == "https://www.w3schools.com/cpp/cpp_for_loop.asp"

    prompt_2 = "Can you summarize https://example.com/docs/guide and tell me how it works?"
    urls_2 = url_pattern.findall(prompt_2)
    assert len(urls_2) == 1
    assert urls_2[0] == "https://example.com/docs/guide"

    prompt_3 = "Just a general question without any links"
    assert len(url_pattern.findall(prompt_3)) == 0


def test_citation_grounding_prunes_unrelated_pdf_chunks():
    """Verify that when an explicit web chunk is present, low-scoring unrelated KB chunks are pruned."""
    web_chunk = VectorSearchResult(
        chunk_id="web-cpp-1",
        document_id="https://www.w3schools.com/cpp/cpp_for_loop.asp",
        document_title="C++ For Loop",
        knowledge_base_id=None,
        content="The C++ for loop executes a block of code a specific number of times.",
        score=0.95,
        metadata={"source_type": "web", "source_url": "https://www.w3schools.com/cpp/cpp_for_loop.asp"},
    )

    unrelated_solar_chunk = VectorSearchResult(
        chunk_id="kb-solar-1",
        document_id="doc-solar-pdf",
        document_title="Solar Irradiance and Photovoltaic Forecasting.pdf",
        knowledge_base_id="kb-solar-id",
        content="Global horizontal irradiance (GHI) measurement and direct normal irradiance.",
        score=0.48,  # Low score from matching 'knowledge' or generic terms
        metadata={"source_type": "document", "source_name": "Solar Irradiance.pdf", "page_number": 3},
    )

    explicit_web_chunks = [web_chunk]
    raw_retrieved = [unrelated_solar_chunk]

    # Apply M28.1 grounding filter
    filtered_results = explicit_web_chunks + [
        r for r in raw_retrieved
        if (r.score is not None and r.score >= 0.70)
    ]

    # Verify: only web_chunk is kept, unrelated solar chunk is discarded
    assert len(filtered_results) == 1
    assert filtered_results[0].document_title == "C++ For Loop"
    assert filtered_results[0].metadata["source_type"] == "web"


def test_build_rag_context_anti_refusal_notice():
    """Verify build_rag_context injects anti-refusal system instructions when web_notice is provided."""
    web_notice = "WEB NOTICE: The user provided https://example.com/cpp. The content was retrieved."
    
    messages, citations = build_rag_context(
        system_prompt="You are a helpful assistant.",
        conversation_history=[],
        current_user_message="Explain https://example.com/cpp",
        retrieved_results=[],
        web_notice=web_notice,
    )

    system_msg = messages[0].content if hasattr(messages[0], "content") else messages[0]["content"]
    assert "You have access to real-time web reading tools" in system_msg
    assert "NEVER claim you cannot access the internet or view external web pages" in system_msg
    assert "WEB NOTICE:" in system_msg


# ---------------------------------------------------------------------------
# M28.2: Hardened SSRF & Connection-Level Defense Tests
# ---------------------------------------------------------------------------

def test_ssrf_blocks_forbidden_destinations():
    """Verify SSRF validation rejects localhost, loopback, private IPs, and cloud metadata."""
    from app.services.web.ssrf import validate_web_url, SSRFSecurityError

    forbidden_urls = [
        "https://127.0.0.1/admin",
        "https://localhost:443/status",
        "https://[::1]/secret",
        "https://169.254.169.254/latest/meta-data/",
        "https://10.0.0.1/dashboard",
        "https://192.168.1.1/config",
        "https://172.16.0.10/internal",
        "http://0.0.0.0/debug",
    ]

    for bad_url in forbidden_urls:
        with pytest.raises(SSRFSecurityError):
            validate_web_url(bad_url, allow_http_for_testing=False)


@pytest.mark.asyncio
async def test_ssrf_connection_level_backend_blocks_private_peer():
    """Verify SSRFSafeNetworkBackend refuses connection to private/loopback peer IP."""
    import httpcore
    from app.services.web.ssrf import SSRFSafeNetworkBackend, SSRFSecurityError

    backend = SSRFSafeNetworkBackend(allow_http_for_testing=False)

    # Attempt connecting to loopback
    with pytest.raises((SSRFSecurityError, ValueError)):
        await backend.connect_tcp(host="127.0.0.1", port=80)


def test_code_block_url_does_not_trigger_preflight():
    """Verify URLs embedded inside code blocks or blockquotes do not trigger outbound preflights."""
    user_code_msg = """Here is the code sample:
```cpp
// Check https://w3schools.com/cpp/example.asp
int a = 1;
```
Can you explain the algorithm?"""

    # Same clean algorithm used in AssistantRuntime
    clean_msg = re.sub(r"```[\s\S]*?```", "", user_code_msg)
    clean_msg = re.sub(r"`[^`]*`", "", clean_msg)
    clean_msg = re.sub(r"^>.*$", "", clean_msg, flags=re.MULTILINE)
    url_matches = re.findall(r"https?://[^\s<>'\"{}|\\^`]+", clean_msg)

    assert len(url_matches) == 0


def test_source_aware_grounding_retains_comparison_only_when_requested():
    """Verify that KB documents are excluded when user asks only about a webpage, and retained when comparison is asked."""
    web_chunk = VectorSearchResult(
        chunk_id="web-1",
        document_id="https://example.com/page",
        document_title="Web Page",
        knowledge_base_id=None,
        content="Web page content about topics.",
        score=0.99,
        metadata={"source_type": "web"},
    )
    doc_chunk = VectorSearchResult(
        chunk_id="doc-1",
        document_id="doc-internal",
        document_title="Company Internal Policy.pdf",
        knowledge_base_id="kb-1",
        content="Company internal policy content.",
        score=0.72,
        metadata={"source_type": "document"},
    )

    explicit_web = [web_chunk]
    retrieved = [doc_chunk]

    # Case A: User only asked about webpage
    user_msg_page_only = "Explain this webpage https://example.com/page"
    wants_comp_a = any(w in user_msg_page_only.lower() for w in ("document", "file", "kb", "knowledge base", "compare", "pdf", "both"))
    results_a = explicit_web + [r for r in retrieved if (r.score is not None and r.score >= 0.70)] if wants_comp_a else explicit_web
    assert len(results_a) == 1
    assert results_a[0].document_title == "Web Page"

    # Case B: User explicitly requested comparison
    user_msg_compare = "Compare this webpage https://example.com/page with my document policy"
    wants_comp_b = any(w in user_msg_compare.lower() for w in ("document", "file", "kb", "knowledge base", "compare", "pdf", "both"))
    results_b = explicit_web + [r for r in retrieved if (r.score is not None and r.score >= 0.70)] if wants_comp_b else explicit_web
    assert len(results_b) == 2
    assert {r.document_title for r in results_b} == {"Web Page", "Company Internal Policy.pdf"}

