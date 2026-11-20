"""Deterministic Academic & Research Literature Preflight Service.

Provides intent classification and terms-compliant search orchestration for explicit academic
paper queries (arXiv), ensuring models without native tool-calling capabilities can deliver
rigorous, source-grounded research comparisons without relying on spontaneous tool generation.
"""

import logging
import re
import uuid
from typing import Any, Optional

from app.services.web.search import ArxivSearchProvider, WebSearchService
from app.vectorstores.base import VectorSearchResult

logger = logging.getLogger("mmaip.research.academic_search")

# Words to strip when extracting the core scientific topic from search commands
_SEARCH_COMMAND_STOPWORDS = {
    "search", "find", "look", "up", "get", "retrieve", "recent", "latest", "newest",
    "papers", "paper", "studies", "study", "literature", "preprints", "preprint",
    "arxiv", "articles", "article", "for", "about", "on", "in", "the", "a", "an",
    "some", "any", "please", "can", "you", "could", "would",
}


def detect_academic_search_intent(user_message: str) -> tuple[bool, str, bool, bool]:
    """Classify whether a user message explicitly requests academic literature search.

    Returns:
        tuple[bool, str, bool, bool]:
            - is_academic_search: True if explicit academic search intent is identified.
            - clean_query: Extracted scientific research topic (stripped of command fluff).
            - wants_comparison: True if comparison against user's uploaded paper/document was requested.
            - wants_recent: True if recent/latest publications were requested.
    """
    if not user_message or not user_message.strip():
        return False, "", False, False

    clean_msg = re.sub(r"```[\s\S]*?```", "", user_message)
    clean_msg = re.sub(r"`[^`]*`", "", clean_msg)
    lower_msg = clean_msg.lower().strip()

    # Exclude direct URLs (handled by web URL preflight)
    if re.search(r"https?://", lower_msg):
        return False, "", False, False

    # Exclude queries solely asking about an already uploaded document without search action
    if re.search(r"^(?:according to|based on|in|from)\s+(?:my\s+)?(?:uploaded\s+)?(?:paper|document|pdf|file)\b", lower_msg) and not re.search(r"\b(?:search|find|look up)\b", lower_msg):
        return False, "", False, False

    # Explicit comparison markers with uploaded materials
    wants_comparison = bool(re.search(
        r"\b(?:compare|comparison|versus|vs\.?)\b.*\b(?:my\s+)?(?:uploaded|document|paper|file|pdf|kb)\b"
        r"|\b(?:with|against)\s+my\s+(?:uploaded\s+)?(?:paper|document|file|pdf)\b",
        lower_msg,
    ))

    wants_recent = bool(re.search(r"\b(?:recent|latest|newest|current|202[3-6])\b", lower_msg))

    # Core academic search patterns
    has_explicit_search = bool(re.search(
        r"\b(?:search|find|look up|retrieve)\b.*\b(?:papers?|studies|study|literature|preprints?|arxiv|publications?)\b",
        lower_msg,
    ))
    has_arxiv_keyword = bool(re.search(r"\barxiv\b", lower_msg))
    has_academic_paper_phrase = bool(re.search(
        r"\b(?:recent|academic|scientific|research)\s+(?:papers?|studies|preprints?|literature)\b",
        lower_msg,
    ))

    is_academic = has_explicit_search or has_arxiv_keyword or (has_academic_paper_phrase and (wants_comparison or "search" in lower_msg or "find" in lower_msg))

    if not is_academic:
        return False, "", False, False

    # Extract clean search query by stripping comparison clause and command phrases
    query_text = lower_msg
    # Strip comparison suffix e.g. "and compare them with my uploaded paper"
    query_text = re.sub(
        r"\s*(?:and\s+)?(?:compare|comparison|versus|vs\.?)\b.*$",
        "",
        query_text,
    ).strip()

    # Tokenize and strip command words
    tokens = re.findall(r"\b[a-zA-Z0-9_\-\.\+]{2,}\b", query_text)
    meaningful_tokens = [t for t in tokens if t not in _SEARCH_COMMAND_STOPWORDS]

    clean_query = " ".join(meaningful_tokens).strip()
    if not clean_query:
        # Fallback to tokens without strict command stripping
        clean_query = " ".join(tokens[:5]).strip()

    return True, clean_query, wants_comparison, wants_recent


async def execute_academic_search_preflight(
    query: str,
    tenant_id: Optional[uuid.UUID] = None,
    wants_recent: bool = False,
    max_results: int = 4,
) -> list[VectorSearchResult]:
    """Execute authorized academic literature preflight search against arXiv.

    Returns normalized VectorSearchResult objects with genuine academic metadata.
    """
    if not query or not query.strip():
        return []

    logger.info(f"Executing deterministic academic search preflight for query: '{query}'")
    arxiv_provider = ArxivSearchProvider()

    try:
        raw_results = await arxiv_provider.search(query, max_results=max_results)
    except Exception as exc:
        logger.warning(f"ArXiv preflight search failed for query '{query}': {exc}")
        return []

    if not raw_results:
        logger.info(f"No academic search results returned for query: '{query}'")
        return []

    # If recent papers were requested, sort primarily by publication or updated date descending
    if wants_recent:
        raw_results.sort(
            key=lambda r: (r.get("publication_date") or "", r.get("updated_date") or ""),
            reverse=True,
        )

    results: list[VectorSearchResult] = []
    seen_urls: set[str] = set()

    for rank, r in enumerate(raw_results[:max_results], start=1):
        url = r.get("url") or ""
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)

        title = r.get("title") or "Academic Research Preprint"
        authors = r.get("authors") or "Unknown Authors"
        pub_date = r.get("publication_date") or "Date unspecified"
        updated_date = r.get("updated_date")
        snippet = r.get("snippet") or ""

        # Safe bounded abstract representation (up to 900 chars)
        clean_abstract = snippet[:900].strip()

        date_line = f"Published: {pub_date}" + (f" (Updated: {updated_date})" if updated_date and updated_date != pub_date else "")
        content = (
            f"[arXiv Preprint: {title}]\n"
            f"Authors: {authors}\n"
            f"{date_line}\n"
            f"Canonical Link: {url}\n"
            f"Abstract: {clean_abstract}\n"
            f"Note: This is an academic preprint abstract retrieved from arXiv, not peer-reviewed full-text evidence."
        )

        chunk = VectorSearchResult(
            chunk_id=str(uuid.uuid5(uuid.NAMESPACE_URL, url)),
            document_id=url,
            document_title=f"arXiv: {title}",
            knowledge_base_id=None,
            content=content,
            score=round(0.96 - (rank * 0.01), 4),
            metadata={
                "source_type": "web",
                "source": "arXiv Preprint",
                "domain": "arxiv.org",
                "source_url": url,
                "title": title,
                "authors": authors,
                "publication_date": pub_date,
                "updated_date": updated_date,
                "is_preprint": True,
                "rank": rank,
            },
        )
        results.append(chunk)

    return results
