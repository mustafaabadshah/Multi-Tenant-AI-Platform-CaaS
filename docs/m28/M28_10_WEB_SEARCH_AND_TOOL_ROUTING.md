# M28.10 — Web Search & Tool Routing

## 1. Distinct Capabilities: Direct URL Reading vs. Public Web Search
- **Direct Web Page Reading (`web_read_url`)**:
  - Deterministic HTTP/HTTPS fetch and text extraction via `WebContentExtractor`.
  - Zero search API required.
  - Fully functional even when search providers are unconfigured.
- **Web Search (`web_search`)**:
  - Execution over search provider APIs to discover unknown URLs.

---

## 2. Free-First Academic Search Provider (`ArxivSearchProvider`)
To support truthful research comparisons (such as solar irradiance forecasting or ML literature review) without incurring paid search API costs:
- Implemented `ArxivSearchProvider` in `backend/app/services/web/search.py`.
- Connects to the official, open ArXiv REST API (`http://export.arxiv.org/api/query`).
- Zero API keys required.
- $0.00 cost ceiling.
- Parses Atom XML feed into clean normalized paper results with paper title, abstract snippet, arXiv URL (`http://arxiv.org/abs/...`), domain (`arxiv.org`), and publication date.
- Fully compliant with terms of service.

---

## 3. Provider Resolution & Honest Configured State
In `WebSearchService`:
1. If `BRAVE_SEARCH_API_KEY` is configured: uses `BraveSearchProvider` for general web search.
2. If query pertains to research/literature/forecasting/academic models: automatically routes to `ArxivSearchProvider` for real scientific literature.
3. If running under `pytest`: falls back to `MockSearchProvider` for offline deterministic test stability.
4. Otherwise (general queries without external search credentials in staging/production): returns honest `status="NOT_CONFIGURED"`, message:
   `"Web search provider is not configured. Direct URL reading is still available."`
   Never presents synthetic or fabricated mock search results to users as real discoveries.

---

## 4. Test Evidence
- `test_arxiv_search_provider_parses_atom_feed`: PASSED
- `test_web_search_service_honest_not_configured_when_no_provider`: PASSED
