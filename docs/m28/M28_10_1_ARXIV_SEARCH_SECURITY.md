# M28.10.1 — arXiv Academic Search Production Hardening & Security Audit

## 1. Transport & Network Architecture

1. **Secure HTTPS Endpoint:**
   - Base URL updated to `https://export.arxiv.org/api/query` (SSL certificate verified, HTTP plaintext disallowed).
2. **Network Constraints:**
   - Explicit timeout: `15.0s`.
   - `follow_redirects=True, max_redirects=3` (prevents unbounded redirects).
   - Inbound and outbound SSRF protections inherited from platform networking boundaries.

---

## 2. API Usage Constraints & Rate Pacing

1. **Official arXiv Terms Compliance:**
   - arXiv documentation specifies: *"Calls should be made at a rate not exceeding one per three seconds"* and *"Do not make multiple simultaneous connections."*
2. **Concurrency & Rate-Limiting Implementation:**
   - Single in-flight connection enforced via `asyncio.Lock()`:
     ```python
     async with self._lock:
         now = time.monotonic()
         elapsed = now - self._last_request_time
         if elapsed < self.RATE_LIMIT_INTERVAL and self._last_request_time > 0:
             await asyncio.sleep(self.RATE_LIMIT_INTERVAL - elapsed)
         self._last_request_time = time.monotonic()
     ```
3. **HTTP 429 & 503 Handling:**
   - Returns structured error diagnostic: `"ArXiv API rate limited or temporarily unavailable (HTTP 429/503). Please retry after backoff."`

---

## 3. XML & Content Security

1. **Entity Expansion & XML Bomb Prevention:**
   - Response size bounded to `512,000` bytes (`MAX_RESPONSE_BYTES`). Payloads exceeding this limit are aborted immediately.
   - External DTD / XML entity inspection:
     `if "<!ENTITY" in raw_text or ("<!DOCTYPE" in raw_text and "SYSTEM" in raw_text): raise ValueError(...)`
   - Safe `xml.etree.ElementTree.fromstring` parsing without entity resolution.

---

## 4. Academic Provenance & Metadata Fidelity

1. **Preprint Identification:**
   - All results from `ArxivSearchProvider` are explicitly labeled with `source: "arXiv Preprint"` and `is_preprint: True`.
   - No synthetic claims of peer review or journal publication are fabricated.
2. **Extracted Fields:**
   - Canonical HTTPS URL (`https://arxiv.org/abs/...`).
   - Cleaned title (whitespace & newlines stripped).
   - Author list (first 5 authors with `et al.` appended if > 5).
   - Publication date (`atom:published`) and update date (`atom:updated`).
   - Abstract snippet (bounded to 400 characters).

---

## 5. Search Intent & Tool Routing

1. **Intent-Based Routing:**
   - General queries (e.g. "weather forecasting in London", "compare laptop prices") are **not** routed to arXiv.
   - Only queries with explicit academic indicators (`arxiv`, `paper`, `literature`, `preprint`, `journal`, `publication`) OR scientific ML combinations (e.g. `research/baseline/compare` + `irradiance/solar/deep learning/transformer/lstm/rmse`) route to `ArxivSearchProvider`.
2. **Honest `NOT_CONFIGURED` Handling:**
   - If a general search query is issued and no Brave Search API key is present in environment, `WebSearchService` returns `status: "NOT_CONFIGURED"`:
     `"Web search provider is not configured. Direct URL reading is still available."`
   - arXiv is never disguised as a general web search provider.

---

## 6. Real Availability Verification (Live Smoke Test)

- Executed 1 bounded HTTPS request to `https://export.arxiv.org/api/query?search_query=all:solar+forecasting&start=0&max_results=1`.
- Verified Result:
  - HTTP Status: `200 OK`
  - Body Content: Genuine Atom XML containing valid preprint entry.
  - Zero cost incurred ($0.00).
