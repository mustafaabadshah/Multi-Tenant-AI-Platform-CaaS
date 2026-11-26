# M27.3 — Web Content Extraction & Site Policy Compliance

## 1. Design Principles & Architecture

Placing raw website HTML into the LLM context wastes tokens, damages prompt formatting, and introduces noise from advertisements, navigation menus, and tracking scripts.

`WebContentExtractor` in [extractor.py](file:///E:/MM%20Office/Multi-Tanant-CaaS/backend/app/services/web/extractor.py) is a **pure-Python, deterministic HTML extractor** built on `html.parser.HTMLParser` with:
- **Zero Headless Browsers:** No Puppeteer, Playwright, or Selenium required. Extremely fast, CPU-friendly, and memory-safe for Render Free and 8 GB CPU development environments.
- **Strict Boilerplate Stripping:** Ignores non-content tags including `<script>`, `<style>`, `<nav>`, `<header>`, `<footer>`, `<aside>`, `<form>`, `<noscript>`, `<svg>`, `<button>`, and `<iframe>`.
- **Structured Markdown Normalization:**
  - Headings (`<h1>`–`<h6>`) are converted to clean Markdown `#`, `##`, etc.
  - Paragraphs and line breaks are cleanly separated with double newlines.
  - Lists (`<ul>` and `<ol>`) are rendered as standard bulleted and numbered items.
  - HTML Tables (`<table>`, `<thead>`, `<tbody>`, `<tr>`, `<th>`, `<td>`) are converted into GitHub Flavored Markdown (GFM) tables.
  - Code Blocks (`<pre><code>` with optional `class="language-*"` tags) are preserved as syntax-highlighted Markdown code fences.

---

## 2. Token & Size Bounds

| Metric | Bound | Action on Exceeded |
|---|---|---|
| **Max Extracted Characters** | 30,000 chars (~7,500 tokens) | Truncated cleanly with `[Content truncated at length limit...]` |
| **Fallback Plaintext Mode** | If DOM parsing fails due to severely malformed HTML, regex tag stripping is used | Marked with `status="FALLBACK_PARSED"` |
| **Empty Threshold** | Content with < 10 readable non-whitespace chars | Marked with `status="EMPTY"` |

---

## 3. Site Policy & Access Control Handling

In compliance with web etiquette and access boundaries:
- **JavaScript Rendering Detection:** If a page only contains a SPA loader or `<noscript>Please enable JavaScript to view this application</noscript>`, the extractor detects this condition and reports `status="JS_REQUIRED"`. It transparently notifies the user that the site requires interactive client-side execution rather than hanging or returning useless empty boilerplate.
- **Anti-Bot & CAPTCHA Detection:** If Cloudflare challenges, Captcha interstitials, or 403 Forbidden blocks occur, the extractor reports `status="BLOCKED"`. It never attempts to circumvent paywalls, bypass access controls, or hammer blocked domains.
- **User Choice:** When access is blocked, the user is offered the opportunity to upload an authorized document or paste an excerpt into the chat.
