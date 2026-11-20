"""M27 Web Intelligence Test Suite: SSRF Hardening, Content Extraction, Web Search & KB Integration."""

import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.web.ssrf import (
    validate_web_url,
    SSRFSecurityError,
)
from app.services.web.extractor import WebContentExtractor
from app.services.web.search import (
    MockSearchProvider,
    BraveSearchProvider,
    WebSearchService,
)
from app.services.web.context_store import (
    ConversationWebContextStore,
    WebPageContext,
)
from app.services.web.kb_saver import WebKBSaveService, WebSaveMode
from app.services.tools.builtin import BUILTIN_TOOL_DEFINITIONS
from app.services.tools.registry import ToolRegistryService
from app.models.tenant import Tenant
from app.models.user import User
from app.models.knowledge import KnowledgeBase, Document, DocumentChunk


@pytest.fixture
async def setup_m27_environment(db_session: AsyncSession):
    """Fixture providing isolated tenant and user records."""
    tenant = Tenant(id=uuid.uuid4(), name="M27 Test Org", slug=f"m27-test-{uuid.uuid4().hex[:8]}")
    user = User(
        id=uuid.uuid4(),
        email="m27_test_user@example.com",
        hashed_password="mocked_argon2id_hash_placeholder",
        full_name="M27 Engineer",
        status="ACTIVE",
    )
    db_session.add(tenant)
    db_session.add(user)
    await db_session.commit()
    return {"tenant": tenant, "user": user}


# =============================================================================
# 1. SSRF SECURITY HARDENING TESTS (Phase 27)
# =============================================================================


class TestSSRFDefense:
    """Rigorous SSRF test suite verifying rejection of loopback, private, and internal addresses."""

    @pytest.mark.parametrize(
        "blocked_url",
        [
            "http://localhost",
            "http://localhost:8000",
            "https://localhost/admin",
            "http://127.0.0.1",
            "http://127.0.0.1:8080",
            "http://127.0.1.1",
            "http://127.255.255.255",
            "http://0.0.0.0",
            "http://[::1]",
            "http://[::1]:80",
            "http://10.0.0.1",
            "http://10.254.0.1/secrets",
            "http://172.16.0.1",
            "http://172.31.255.255",
            "http://192.168.0.1",
            "http://192.168.1.254",
            "http://169.254.169.254",  # AWS/GCP/Azure metadata
            "http://169.254.169.254/latest/meta-data/",
            "http://metadata.google.internal",
            "http://instance-data",
            "http://2130706433",  # Decimal encoding of 127.0.0.1
            "http://0x7f000001",  # Hex encoding of 127.0.0.1
            "file:///etc/passwd",
            "ftp://ftp.example.com",
            "gopher://gopher.example.com",
            "javascript:alert(1)",
            "data:text/html,hello",
            "http://user:password@example.com",  # Credential-bearing
            "http://example.com:22",  # Forbidden SSH port
            "http://example.com:25",  # Forbidden SMTP port
            "http://example.com:3306",  # Forbidden MySQL port
            "http://example.com:5432",  # Forbidden Postgres port
        ],
    )
    def test_ssrf_rejects_dangerous_destinations(self, blocked_url: str):
        with pytest.raises(SSRFSecurityError):
            validate_web_url(blocked_url, allow_http_for_testing=False)

    @pytest.mark.parametrize(
        "valid_url",
        [
            "https://www.w3schools.com/cpp/cpp_for_loop.asp",
            "https://en.wikipedia.org/wiki/Retrieval-augmented_generation",
            "https://docs.python.org/3/library/html.parser.html",
        ],
    )
    def test_ssrf_allows_public_destinations(self, valid_url: str):
        canonical, ips = validate_web_url(valid_url)
        assert canonical.startswith("https://")
        assert len(ips) > 0

    def test_ssrf_respects_domain_allowlist(self):
        allowlist = "docs.python.org, wikipedia.org"
        # Permitted
        canonical, ips = validate_web_url("https://docs.python.org/3/", allowed_domains=allowlist)
        assert canonical.startswith("https://docs.python.org")

        # Denied
        with pytest.raises(SSRFSecurityError, match="not in the allowed domains list"):
            validate_web_url("https://www.w3schools.com/cpp/", allowed_domains=allowlist)


# =============================================================================
# 2. WEB CONTENT EXTRACTION TESTS (Phase 28)
# =============================================================================


class TestWebContentExtraction:
    """Verifies deterministic HTML parsing, boilerplate stripping, code preservation, and table conversion."""

    def test_extract_tutorial_page(self):
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>C++ For Loop - W3Schools</title>
            <script>trackUser();</script>
            <style>body { font-size: 14px; }</style>
        </head>
        <body>
            <header><nav><a href="/">Home</a><a href="/cpp">C++</a></nav></header>
            <aside class="ads"><p>Buy something now!</p></aside>
            <main>
                <h1>C++ For Loop</h1>
                <p>When you know exactly how many times you want to loop through a block of code, use the <code>for</code> loop.</p>
                <h2>Syntax</h2>
                <pre><code class="language-cpp">for (statement 1; statement 2; statement 3) {
    // code block to be executed
}</code></pre>
                <h3>Example</h3>
                <p>This example will print the numbers 0 to 4:</p>
                <pre><code>for (int i = 0; i &lt; 5; i++) {
    cout &lt;&lt; i &lt;&lt; "\\n";
}</code></pre>
            </main>
            <footer><p>Copyright 1999-2026 by Refsnes Data.</p></footer>
        </body>
        </html>
        """
        doc = WebContentExtractor.extract(html, source_url="https://www.w3schools.com/cpp/cpp_for_loop.asp")

        assert doc["status"] == "SUCCESS"
        assert doc["title"] == "C++ For Loop - W3Schools"
        assert "C++ For Loop" in doc["content"]
        assert "for (int i = 0; i < 5; i++)" in doc["content"]
        assert "```cpp" in doc["content"] or "```" in doc["content"]
        # Stripped elements
        assert "trackUser" not in doc["content"]
        assert "Buy something now!" not in doc["content"]
        assert "Copyright 1999-2026" not in doc["content"]

    def test_extract_html_table(self):
        html = """
        <html>
        <body>
            <table>
                <thead>
                    <tr><th>Parameter</th><th>Type</th><th>Description</th></tr>
                </thead>
                <tbody>
                    <tr><td>url</td><td>string</td><td>Target web page URL</td></tr>
                    <tr><td>max_length</td><td>integer</td><td>Max characters to extract</td></tr>
                </tbody>
            </table>
        </body>
        </html>
        """
        doc = WebContentExtractor.extract(html)
        assert doc["status"] == "SUCCESS"
        assert "| Parameter | Type | Description |" in doc["content"]
        assert "| url | string | Target web page URL |" in doc["content"]

    def test_detect_js_required_page(self):
        html = """
        <html>
        <head><title>App Loading</title></head>
        <body>
            <p>You need to enable JavaScript to run this app.</p>
            <div id="root"></div>
        </body>
        </html>
        """
        doc = WebContentExtractor.extract(html)
        assert doc["is_js_required"] is True

    def test_detect_blocked_captcha_page(self):
        html = """
        <html>
        <head><title>Attention Required! | Cloudflare</title></head>
        <body>
            <h2>Please complete the security check to access example.com</h2>
            <div class="cf-browser-verification">Verifying your browser...</div>
        </body>
        </html>
        """
        doc = WebContentExtractor.extract(html)
        assert doc["is_blocked"] is True or doc["status"] == "BLOCKED"


# =============================================================================
# 3. SEARCH PROVIDER TESTS (Phases 9 & 10)
# =============================================================================


class TestSearchProviders:
    """Verifies search provider abstractions, offline deterministic mock, and unconfigured safety."""

    @pytest.mark.asyncio
    async def test_mock_search_provider_cpp(self):
        provider = MockSearchProvider()
        results = await provider.search("C++ for loop tutorial", max_results=3)
        assert len(results) >= 1
        top = results[0]
        assert "C++" in top["title"]
        assert "https://" in top["url"]
        assert top["domain"] == "www.w3schools.com" or "cpp" in top["domain"]
        assert top["snippet"]

    @pytest.mark.asyncio
    async def test_mock_search_provider_rag(self):
        provider = MockSearchProvider()
        results = await provider.search("retrieval augmented generation developments", max_results=2)
        assert len(results) >= 1
        assert any("RAG" in r["title"] or "Retrieval" in r["title"] for r in results)

    @pytest.mark.asyncio
    async def test_brave_search_without_key_fails_gracefully(self):
        brave = BraveSearchProvider(api_key=None)
        res = await brave.search("test query")
        assert res == []

    @pytest.mark.asyncio
    async def test_search_service_wrapper(self):
        svc = WebSearchService(provider=MockSearchProvider())
        resp = await svc.search("solar forecasting research", max_results=3)
        assert resp.total > 0
        assert resp.query == "solar forecasting research"
        assert len(resp.results) <= 3


# =============================================================================
# 4. CONVERSATION-SCOPED WEB CONTEXT TESTS (Phases 12 & 13)
# =============================================================================


class TestConversationWebContext:
    """Verifies temporary conversation web context storage, follow-up retention, and boundary isolation."""

    def test_store_and_retrieve_context(self):
        store = ConversationWebContextStore(ttl_seconds=3600, max_pages_per_conversation=5)
        conv_id = uuid.uuid4()

        page = WebPageContext(
            canonical_url="https://www.w3schools.com/cpp/cpp_for_loop.asp",
            original_url="https://www.w3schools.com/cpp/cpp_for_loop.asp",
            title="C++ For Loop",
            extracted_text="A for loop executes a block of code a specified number of times.",
            hostname="www.w3schools.com",
        )
        store.store_page(conv_id, page)

        pages = store.get_pages(conv_id)
        assert len(pages) == 1
        assert pages[0].title == "C++ For Loop"

        # Check retrieval by canonical URL
        retrieved = store.get_page_by_url(conv_id, "https://www.w3schools.com/cpp/cpp_for_loop.asp")
        assert retrieved is not None
        assert retrieved.hostname == "www.w3schools.com"

    def test_conversation_isolation(self):
        store = ConversationWebContextStore()
        conv_a = uuid.uuid4()
        conv_b = uuid.uuid4()

        page = WebPageContext(
            canonical_url="https://example.com/page",
            original_url="https://example.com/page",
            title="Example Page",
            extracted_text="Secret content in conversation A",
            hostname="example.com",
        )
        store.store_page(conv_a, page)

        assert len(store.get_pages(conv_a)) == 1
        # Conversation B cannot access Conversation A's web source
        assert len(store.get_pages(conv_b)) == 0
        assert store.get_page_by_url(conv_b, "https://example.com/page") is None


# =============================================================================
# 5. KNOWLEDGE BASE SAVING & DEDUPLICATION TESTS (Phases 15-18)
# =============================================================================


class TestWebKBSaveService:
    """Verifies safe promotion of web sources to existing Knowledge Base entities."""

    @pytest.mark.asyncio
    async def test_save_reference_mode(self, db_session: AsyncSession, setup_m27_environment):
        env = setup_m27_environment
        # 1. Create a Knowledge Base
        kb = KnowledgeBase(
            id=uuid.uuid4(),
            tenant_id=env["tenant"].id,
            name="Test Research KB",
            status="ACTIVE",
        )
        db_session.add(kb)
        await db_session.commit()

        # 2. Save web source in REFERENCE mode
        saver = WebKBSaveService(db_session, env["tenant"].id, env["user"].id)
        res = await saver.save_web_source_to_kb(
            url="https://www.w3schools.com/cpp/cpp_for_loop.asp",
            knowledge_base_id=kb.id,
            title="W3Schools C++ Loops Reference",
            storage_mode=WebSaveMode.REFERENCE,
            notes="Helpful reference for C++ syntax.",
        )

        assert res["status"] == "SUCCESS"
        assert res["storage_mode"] == "REFERENCE"
        doc_id = uuid.UUID(res["document_id"])

        # Verify Document record in database
        doc = await db_session.get(Document, doc_id)
        assert doc is not None
        assert doc.tenant_id == env["tenant"].id
        assert doc.filename == "W3Schools C++ Loops Reference"
        assert doc.file_path == "https://www.w3schools.com/cpp/cpp_for_loop.asp"
        assert doc.metadata_json["storage_mode"] == "REFERENCE"
        assert doc.metadata_json["source_type"] == "web"

    @pytest.mark.asyncio
    async def test_save_full_content_mode(self, db_session: AsyncSession, setup_m27_environment):
        env = setup_m27_environment
        kb = KnowledgeBase(
            id=uuid.uuid4(),
            tenant_id=env["tenant"].id,
            name="Technical Tutorials KB",
            status="ACTIVE",
        )
        db_session.add(kb)
        await db_session.commit()

        sample_text = (
            "C++ for loops provide structured repetition. "
            "Syntax: for (init; condition; increment) { body; }. "
            "For loops are commonly used to iterate over arrays and vectors."
        )

        saver = WebKBSaveService(db_session, env["tenant"].id, env["user"].id)
        res = await saver.save_web_source_to_kb(
            url="https://www.w3schools.com/cpp/cpp_for_loop.asp",
            knowledge_base_id=kb.id,
            title="C++ For Loop Deep Dive",
            storage_mode=WebSaveMode.FULL_CONTENT,
            extracted_text=sample_text,
        )

        assert res["status"] == "SUCCESS"
        assert res["storage_mode"] == "FULL_CONTENT"
        assert res["chunks_created"] > 0
        doc_id = uuid.UUID(res["document_id"])

        # Verify chunks created in DB
        doc = await db_session.get(Document, doc_id)
        assert doc is not None
        assert doc.total_chunks > 0

    @pytest.mark.asyncio
    async def test_cross_tenant_kb_rejection(self, db_session: AsyncSession, setup_m27_environment):
        env = setup_m27_environment
        other_tenant = Tenant(id=uuid.uuid4(), name="Other Org", slug=f"other-org-{uuid.uuid4().hex[:8]}")
        db_session.add(other_tenant)
        other_kb = KnowledgeBase(
            id=uuid.uuid4(),
            tenant_id=other_tenant.id,
            name="Other Tenant KB",
            status="ACTIVE",
        )
        db_session.add(other_kb)
        await db_session.commit()

        saver = WebKBSaveService(db_session, env["tenant"].id, env["user"].id)
        with pytest.raises(ValueError, match="not found or access unauthorized"):
            await saver.save_web_source_to_kb(
                url="https://example.com",
                knowledge_base_id=other_kb.id,
            )


# =============================================================================
# 6. TOOL REGISTRY & AGENTIC INTEGRATION TESTS (Phases 19-22)
# =============================================================================


class TestAgenticWebTools:
    """Verifies tool definitions, registry dispatch, and prompt-injection safety."""

    def test_builtin_tool_definitions_present(self):
        tool_names = [t["name"] for t in BUILTIN_TOOL_DEFINITIONS]
        assert "web_read_url" in tool_names
        assert "web_search" in tool_names
        assert "web_save_to_kb" in tool_names

        # Verify web_save_to_kb requires approval and is risk_level WRITE
        save_tool = next(t for t in BUILTIN_TOOL_DEFINITIONS if t["name"] == "web_save_to_kb")
        assert save_tool["requires_approval"] is True
        assert save_tool["risk_level"] == "WRITE"

    @pytest.mark.asyncio
    async def test_tool_registry_web_search_execution(self, db_session: AsyncSession, setup_m27_environment):
        env = setup_m27_environment
        registry = ToolRegistryService(db_session, env["tenant"].id, user_id=env["user"].id)
        result = await registry.execute_tool(
            "web_search",
            {"query": "C++ for loop", "count": 2},
        )
        assert "results" in result
        assert len(result["results"]) > 0

    @pytest.mark.asyncio
    async def test_tool_registry_ssrf_blocking_in_web_read(self, db_session: AsyncSession, setup_m27_environment):
        env = setup_m27_environment
        registry = ToolRegistryService(db_session, env["tenant"].id, user_id=env["user"].id)
        # Attempting to read 169.254.169.254 must return a blocked status
        result = await registry.execute_tool(
            "web_read_url",
            {"url": "http://169.254.169.254/latest/meta-data/"},
        )
        assert result["status"] == "BLOCKED_SSRF"
