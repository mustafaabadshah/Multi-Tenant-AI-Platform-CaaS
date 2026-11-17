# M27.4 — Agentic Web Search Provider Architecture

## 1. Separation of Concerns: Search vs. Retrieval Grounding

M27 strictly decouples **web search** from **web fetching**:
1. **Search (`WebSearchProvider`):** Discovers candidate URLs and high-level relevance snippets based on a query.
2. **Fetch (`WebFetchService`):** Safely fetches and extracts content from selected URLs for grounded conversational answers.

Under no circumstances does the platform scrape raw HTML search results (e.g., scraping Google or DuckDuckGo HTML), as this is fragile, violates search terms of service, and is prone to blocking.

---

## 2. Provider Abstraction & Pluggable Architecture

The provider contract is defined in [search.py](file:///E:/MM%20Office/Multi-Tanant-CaaS/backend/app/services/web/search.py):

```python
class WebSearchProvider(abc.ABC):
    @abc.abstractmethod
    async def search(self, query: str, max_results: int = 5, count: Optional[int] = None) -> list[dict[str, Any]]:
        """Execute a web search and return normalized results."""
        pass
```

### Supported Providers

| Provider | Purpose | Status & Requirements |
|---|---|---|
| **`MockSearchProvider`** | Offline, deterministic synthetic provider for local regression, unit testing, and zero-cost operation | **Default Active Provider** in development and test environments without paid keys |
| **`BraveSearchProvider`** | Official, terms-compliant commercial search API | Configured via `BRAVE_SEARCH_API_KEY` environment variable. Free tier offers 2,000 queries/month |
| **Unconfigured Fallback** | Graceful explanation when no provider is active | Returns `status="NOT_CONFIGURED"`, allowing direct URL reading to continue functioning |

---

## 3. Query Bounds & Anti-Spam Controls

To prevent noisy recursive search loops and runaway provider costs:
- Maximum search results returned per query: **5** (bounded between 1 and 10).
- Maximum search execution steps in agent loop: controlled by assistant `tools_config.max_execution_steps` (default: 5).
- Clean query normalization: whitespace trimmed, empty queries rejected upfront with `status="EMPTY_QUERY"`.
- Rate limiting and caching: queries are resolved through `WebSearchService`.
