"""M28.7 Defect Closure: Web Extraction, Cache Contract, and Grounding Tests."""

import pytest
import uuid
from app.services.web.extractor import WebContentExtractor
from app.services.web.reader import WebFetchService, WebFetchResult, _WEB_CACHE


def test_w3schools_c_for_loop_clean_extraction_without_nav_drowning():
    """Verify that W3Schools-like HTML extracts the main tutorial content rather than navigation links."""
    # Synthetic HTML mimicking W3Schools structure with large sidenav preceding #main
    html = """<!DOCTYPE html>
    <html>
    <head><title>C++ For Loop</title></head>
    <body>
      <div id='sidenav' class='w3-sidebar'>
        <div id='leftmenuinner'>
          <a href='/cpp/default.asp'>C++ HOME</a>
          <a href='/cpp/cpp_intro.asp'>C++ Intro</a>
          <a href='/cpp/cpp_getstarted.asp'>C++ Get Started</a>
          <a href='/cpp/cpp_syntax.asp'>C++ Syntax</a>
          <a href='/cpp/cpp_output.asp'>C++ Output</a>
          <a href='/cpp/cpp_variables.asp'>C++ Variables</a>
          <a href='/cpp/cpp_user_input.asp'>C++ User Input</a>
          <a href='/cpp/cpp_operators.asp'>C++ Operators</a>
          <a href='/cpp/cpp_strings.asp'>C++ Strings</a>
          <a href='/cpp/cpp_math.asp'>C++ Math</a>
          <a href='/cpp/cpp_booleans.asp'>C++ Booleans</a>
          <a href='/cpp/cpp_conditions.asp'>C++ Conditions</a>
          <a href='/cpp/cpp_switch.asp'>C++ Switch</a>
          <a href='/cpp/cpp_while_loop.asp'>C++ While Loop</a>
          <a href='/cpp/cpp_for_loop.asp'>C++ For Loop</a>
          <a href='/cpp/cpp_break.asp'>C++ Break/Continue</a>
          <a href='/cpp/cpp_arrays.asp'>C++ Arrays</a>
        </div>
      </div>
      <div id='main' class='w3-col l10 m12'>
        <h1>C++ For Loop</h1>
        <p>When you know exactly how many times you want to loop through a block of code, use the for loop instead of a while loop:</p>
        <h3>Syntax</h3>
        <pre><code class="language-cpp">for (statement 1; statement 2; statement 3) {
  // code block to be executed
}</code></pre>
        <p>Statement 1 is executed (one time) before the execution of the code block.</p>
        <p>Statement 2 defines the condition for executing the code block.</p>
        <p>Statement 3 is executed (every time) after the code block has been executed.</p>
        <h2>Example</h2>
        <pre><code class="language-cpp">for (int i = 0; i < 5; i++) {
  cout &lt;&lt; i &lt;&lt; "\\n";
}</code></pre>
      </div>
    </body>
    </html>"""

    result = WebContentExtractor.extract(html, source_url="https://www.w3schools.com/cpp/cpp_for_loop.asp")
    assert result["status"] == "SUCCESS"
    assert result["title"] == "C++ For Loop"
    content = result["content"]

    # Verify article content is extracted and appears prominently
    assert "statement 1; statement 2; statement 3" in content
    assert "for (int i = 0; i < 5; i++)" in content
    assert "When you know exactly how many times" in content

    # Verify that the navigation list was not prepended to the article
    assert content.index("statement 1") < 500


def test_web_fetch_result_contract_and_cache_consistency():
    """Verify WebFetchResult provides .to_dict() and mapping access on both cache hit and miss."""
    svc = WebFetchService()
    tenant_id = uuid.uuid4()

    # Pre-populate cache with a test result
    cache_url = "https://example.com/cached-page"
    cached_data = {
        "canonical_url": cache_url,
        "domain": "example.com",
        "title": "Cached Title",
        "description": "Cached Description",
        "extracted_text": "Sample cached article body text.",
        "status": "SUCCESS",
        "http_status": 200,
        "content_type": "text/html",
        "source_type": "web_html",
        "content_hash": "abc123",
        "char_count": 32,
        "retrieved_at": "2026-11-19T10:00:00Z",
        "citation": {"source_type": "web", "source_url": cache_url},
    }

    _WEB_CACHE[(str(tenant_id), cache_url)] = (9999999999.0, cached_data)

    import asyncio
    res = asyncio.run(svc.read_webpage(cache_url, tenant_id=tenant_id))

    # Verify it is an instance of WebFetchResult
    assert isinstance(res, WebFetchResult)
    # Verify .to_dict() exists and works without AttributeError
    d = res.to_dict()
    assert isinstance(d, dict)
    assert d["title"] == "Cached Title"
    assert d["cached"] is True
    # Verify mapping access
    assert res["status"] == "SUCCESS"
    assert res.get("extracted_text") == "Sample cached article body text."


def test_url_detection_in_untrusted_prompt():
    """Verify URL detection in runtime prompt extraction."""
    import re

    prompts = [
        ("Read https://www.w3schools.com/cpp/cpp_for_loop.asp and explain C++ for loops.", True, "https://www.w3schools.com/cpp/cpp_for_loop.asp"),
        ("https://docs.python.org/3/tutorial/controlflow.html", True, "https://docs.python.org/3/tutorial/controlflow.html"),
        ("What does the page https://example.com/about say?", True, "https://example.com/about"),
        ("Check `https://example.com/ignored` in code block", False, None),
    ]

    for p, should_detect, expected_url in prompts:
        clean = re.sub(r"```[\s\S]*?```", "", p)
        clean = re.sub(r"`[^`]*`", "", clean)
        matches = re.findall(r"https?://[^\s<>'\"{}|\\^`]+", clean)
        if should_detect:
            assert len(matches) > 0
            assert matches[0].rstrip(".,;!?)]}") == expected_url
        else:
            assert len(matches) == 0


def test_mdn_style_html_extraction():
    """Verify clean extraction on MDN-style HTML with breadcrumbs, side navigation, and code."""
    html = """<!DOCTYPE html>
    <html lang="en">
    <head><title>Array.prototype.map() - JavaScript | MDN</title></head>
    <body>
      <header class="top-navigation">
        <a href="/">MDN Web Docs</a>
      </header>
      <div class="breadcrumbs">
        <a href="/en-US/docs/Web">Web</a> &gt; <a href="/en-US/docs/Web/JavaScript">JavaScript</a>
      </div>
      <aside class="sidebar-wrapper" id="sidebar">
        <nav>
          <ul>
            <li><a href="/docs/Array">Array</a></li>
            <li><a href="/docs/Array/filter">Array.filter()</a></li>
            <li><a href="/docs/Array/map">Array.map()</a></li>
          </ul>
        </nav>
      </aside>
      <main id="content">
        <h1>Array.prototype.map()</h1>
        <p>The map() method of Array instances creates a new array populated with the results of calling a provided function on every element in the calling array.</p>
        <h2>Syntax</h2>
        <pre><code class="language-javascript">map(callbackFn)
map(callbackFn, thisArg)</code></pre>
        <h2>Parameters</h2>
        <p>callbackFn: A function to execute for each element in the array.</p>
      </main>
      <footer class="page-footer">
        <p>© 2026 Mozilla and individual contributors.</p>
      </footer>
    </body>
    </html>"""

    result = WebContentExtractor.extract(html, source_url="https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array/map")
    assert result["status"] == "SUCCESS"
    assert "Array.prototype.map()" in result["title"]
    content = result["content"]

    # Main content must be present
    assert "creates a new array populated with the results" in content
    assert "map(callbackFn)" in content
    assert "callbackFn: A function to execute" in content

    # Boilerplate from header, footer, breadcrumbs, sidebar should be excluded
    assert "MDN Web Docs" not in content
    assert "Mozilla and individual contributors" not in content


def test_python_sphinx_docs_extraction():
    """Verify clean extraction of Python official Sphinx documentation."""
    html = """<!DOCTYPE html>
    <html>
    <head><title>4. More Control Flow Tools — Python 3.12 documentation</title></head>
    <body>
      <div class="related" role="navigation" aria-label="related navigation">
        <ul>
          <li><a href="../index.html">Python 3.12 documentation</a></li>
        </ul>
      </div>
      <div class="sphinxsidebar" role="navigation" aria-label="main navigation">
        <div class="sphinxsidebarwrapper">
          <h3>Table of Contents</h3>
          <ul>
            <li><a href="#if-statements">4.1. if Statements</a></li>
            <li><a href="#for-statements">4.2. for Statements</a></li>
          </ul>
        </div>
      </div>
      <div class="document">
        <div class="documentwrapper">
          <div class="body" role="main">
            <section id="for-statements">
              <h1>4.2. for Statements</h1>
              <p>The for statement in Python differs a bit from what you may be used to in C or Pascal. Rather than always iterating over an arithmetic progression of numbers, Python's for statement iterates over the items of any sequence.</p>
              <pre><code class="language-python">words = ['cat', 'window', 'defenestrate']
for w in words:
    print(w, len(w))</code></pre>
            </section>
          </div>
        </div>
      </div>
      <div class="clearer"></div>
    </body>
    </html>"""

    result = WebContentExtractor.extract(html, source_url="https://docs.python.org/3/tutorial/controlflow.html")
    assert result["status"] == "SUCCESS"
    content = result["content"]

    # Verify article content
    assert "The for statement in Python differs a bit" in content
    assert "words = ['cat', 'window', 'defenestrate']" in content

    # Verify Sphinx sidebar boilerplate is excluded
    assert "Table of Contents" not in content


def test_modern_blog_with_cookie_notice_and_forms():
    """Verify that cookie notices, banners, and subscription forms are stripped."""
    html = """<!DOCTYPE html>
    <html>
    <head>
      <title>Building Resilient AI Systems</title>
      <meta name="description" content="A guide to deterministic fallback patterns in LLM engineering.">
    </head>
    <body>
      <div class="cookie-banner" id="cookie-notice">
        <p>We use cookies to improve your experience. <button>Accept All</button></p>
      </div>
      <header class="top-nav">
        <a href="/" class="logo">Engineering Blog</a>
      </header>
      <main class="post-content">
        <h1>Building Resilient AI Systems</h1>
        <p>In distributed agentic systems, deterministic fallbacks ensure that transient network failures do not cascade into system-wide outages.</p>
        <p>Always implement bounded timeouts and exponential backoff on remote RPC boundaries.</p>
      </main>
      <div class="newsletter-signup widget-area">
        <form>
          <label>Subscribe to our newsletter</label>
          <input type="email" placeholder="you@domain.com" />
          <button type="submit">Subscribe</button>
        </form>
      </div>
    </body>
    </html>"""

    result = WebContentExtractor.extract(html, source_url="https://blog.example.com/resilient-ai")
    assert result["status"] == "SUCCESS"
    assert result["title"] == "Building Resilient AI Systems"
    assert "deterministic fallback patterns" in result["description"]
    content = result["content"]

    # Main content present
    assert "deterministic fallbacks ensure that transient network failures" in content
    assert "bounded timeouts and exponential backoff" in content

    # Boilerplate stripped
    assert "We use cookies" not in content
    assert "Subscribe to our newsletter" not in content
