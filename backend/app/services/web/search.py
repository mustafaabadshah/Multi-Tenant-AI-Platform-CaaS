"""Web Search Provider Abstraction and Search Service for M27."""

import abc
import os
import uuid
from typing import Any, Optional

import httpx

from app.core.config import settings


class SearchResponse(dict):
    """Dictionary subclass providing dot-attribute access for convenience."""
    @property
    def total(self) -> int:
        return self.get("result_count", len(self.get("results", [])))

    @property
    def query(self) -> str:
        return self.get("query", "")

    @property
    def results(self) -> list[dict[str, Any]]:
        return self.get("results", [])

    def to_dict(self) -> dict[str, Any]:
        return dict(self)


class WebSearchProvider(abc.ABC):
    """Abstract base class for terms-compliant web search providers."""

    @abc.abstractmethod
    async def search(self, query: str, max_results: int = 5, count: Optional[int] = None) -> list[dict[str, Any]]:
        """Execute a web search and return normalized results."""
        pass


class MockSearchProvider(WebSearchProvider):
    """Deterministic, offline synthetic search provider for local tests and regression."""

    SYNTHETIC_DATABASE = [
        {
            "keywords": ["c++", "for", "loop", "cpp", "iteration"],
            "title": "C++ For Loop - W3Schools",
            "url": "https://www.w3schools.com/cpp/cpp_for_loop.asp",
            "snippet": "When you know exactly how many times you want to loop through a block of code, use the for loop instead of a while loop. Syntax: for (statement 1; statement 2; statement 3) { // code block }.",
            "source": "w3schools.com",
            "domain": "www.w3schools.com",
            "publication_date": "2024-01-15",
        },
        {
            "keywords": ["c++", "range", "for", "loop", "container"],
            "title": "Range-based for loop - cppreference.com",
            "url": "https://en.cppreference.com/w/cpp/language/range-for",
            "snippet": "Executes a for loop over a range. Used as a more readable equivalent to the traditional for loop operating over a range of values, such as all elements in a container.",
            "source": "cppreference.com",
            "domain": "en.cppreference.com",
            "publication_date": "2024-02-10",
        },
        {
            "keywords": ["rag", "retrieval", "augmented", "generation", "llm", "recent"],
            "title": "Recent Advances in Retrieval-Augmented Generation for Large Language Models",
            "url": "https://arxiv.org/abs/2312.10997",
            "snippet": "A comprehensive survey of Retrieval-Augmented Generation (RAG) paradigms including Naive RAG, Advanced RAG, and Modular RAG architectures, evaluation benchmarks, and industry integrations.",
            "source": "arxiv.org",
            "domain": "arxiv.org",
            "publication_date": "2024-03-01",
        },
        {
            "keywords": ["solar", "irradiance", "forecasting", "deep learning", "ghi"],
            "title": "Deep Learning for Solar Irradiance Forecasting in Agricultural Regions",
            "url": "https://example.org/research/solar_forecasting_pakistan",
            "snippet": "Convolutional Neural Networks and LSTM hybrids for multi-horizon GHI solar predictions across agricultural areas in Peshawar, Karachi, Multan, and Hyderabad.",
            "source": "example.org",
            "domain": "example.org",
            "publication_date": "2024-04-12",
        },
    ]

    async def search(self, query: str, max_results: int = 5, count: Optional[int] = None) -> list[dict[str, Any]]:
        limit = count if count is not None else max_results
        q_lower = query.lower()
        matched: list[dict[str, Any]] = []

        for item in self.SYNTHETIC_DATABASE:
            score = sum(1 for kw in item["keywords"] if kw in q_lower)
            if score > 0:
                matched.append({**item, "_score": score})

        # Sort by relevance score
        matched.sort(key=lambda x: x["_score"], reverse=True)

        if not matched:
            # Fallback synthetic result for any generic query
            matched = [
                {
                    "title": f"Web Overview: {query.title()}",
                    "url": f"https://en.wikipedia.org/wiki/{query.strip().replace(' ', '_')}",
                    "snippet": f"Encyclopedia article and verified documentation on {query}. Overview, history, applications, and verified citations.",
                    "source": "wikipedia.org",
                    "domain": "wikipedia.org",
                    "publication_date": "2024-01-01",
                }
            ]

        results = []
        for rank, item in enumerate(matched[:limit], start=1):
            results.append({
                "title": item["title"],
                "url": item["url"],
                "snippet": item["snippet"],
                "source": item["source"],
                "domain": item.get("domain", item["source"]),
                "publication_date": item.get("publication_date"),
                "rank": rank,
            })
        return results


class BraveSearchProvider(WebSearchProvider):
    """Terms-compliant web search using the official Brave Search API."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    async def search(self, query: str, max_results: int = 5, count: Optional[int] = None) -> list[dict[str, Any]]:
        if not self.api_key:
            return []

        limit = count if count is not None else max_results
        endpoint = "https://api.search.brave.com/res/v1/web/search"
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.api_key,
        }
        params = {
            "q": query.strip(),
            "count": min(max(limit, 1), 10),
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(endpoint, headers=headers, params=params)
            if resp.status_code != 200:
                raise ValueError(f"Brave Search API error HTTP {resp.status_code}: {resp.text[:200]}")

            data = resp.json()
            web_results = data.get("web", {}).get("results", [])

            results = []
            for rank, r in enumerate(web_results[:limit], start=1):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("description", ""),
                    "source": r.get("meta_url", {}).get("hostname", ""),
                    "domain": r.get("meta_url", {}).get("hostname", ""),
                    "publication_date": r.get("page_age"),
                    "rank": rank,
                })
            return results


class WebSearchService:
    """Orchestrates search queries across configured providers."""

    def __init__(
        self,
        tenant_id: Optional[uuid.UUID] = None,
        provider: Optional[WebSearchProvider] = None,
        provider_override: Optional[WebSearchProvider] = None,
    ):
        self.tenant_id = tenant_id
        self._provider = provider or provider_override

    def _resolve_provider(self) -> Optional[WebSearchProvider]:
        if self._provider:
            return self._provider

        # Check for configured Brave Search API key in environment
        brave_key = os.environ.get("BRAVE_SEARCH_API_KEY") or getattr(settings, "BRAVE_SEARCH_API_KEY", None)
        if brave_key:
            return BraveSearchProvider(brave_key)

        # In testing or development environments without an external key, use deterministic mock
        if getattr(settings, "ENVIRONMENT", "development") in ("development", "test"):
            return MockSearchProvider()

        return None

    async def search(self, query: str, max_results: int = 5, count: Optional[int] = None) -> SearchResponse:
        """Search the public web and return normalized results."""
        clean_query = query.strip()
        limit = count if count is not None else max_results

        if not clean_query:
            return SearchResponse({
                "query": "",
                "results": [],
                "status": "EMPTY_QUERY",
                "message": "Search query cannot be empty.",
                "result_count": 0,
            })

        provider = self._resolve_provider()
        if not provider:
            return SearchResponse({
                "query": clean_query,
                "results": [],
                "status": "NOT_CONFIGURED",
                "message": "Web search provider is not configured. Direct URL reading is still available.",
                "result_count": 0,
            })

        bounded_limit = min(max(limit, 1), 10)
        try:
            results = await provider.search(clean_query, max_results=bounded_limit)
            return SearchResponse({
                "query": clean_query,
                "results": results,
                "status": "SUCCESS",
                "result_count": len(results),
            })
        except Exception as err:
            return SearchResponse({
                "query": clean_query,
                "results": [],
                "status": "PROVIDER_ERROR",
                "message": f"Search failed: {err}",
                "result_count": 0,
            })


def get_web_search_service(tenant_id: Optional[uuid.UUID] = None) -> WebSearchService:
    return WebSearchService(tenant_id=tenant_id)
