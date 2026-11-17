"""Safe Outbound Web Page Reader Service (M27).

Enforces SSRF prevention, redirect re-validation, size bounds, and deterministic extraction.
"""

import hashlib
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlparse, urljoin

import httpx

from app.core.config import settings
from app.services.web.extractor import WebContentExtractor
from app.services.web.ssrf import validate_web_url, SSRFSecurityError


# In-memory cache for conversation follow-ups: (tenant_id, canonical_url) -> (cache_timestamp, result_dict)
_WEB_CACHE: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}
_CACHE_TTL_SECONDS = 3600  # 1 hour


class WebFetchResult(dict):
    """Dictionary subclass with .to_dict() support for AssistantRuntime."""
    def to_dict(self) -> dict[str, Any]:
        return dict(self)


class WebFetchService:
    """Provides secure, bounded outbound fetching and text extraction for public web pages."""

    MAX_RESPONSE_BYTES = 2 * 1024 * 1024  # 2 MiB
    MAX_REDIRECTS = 3
    CONNECT_TIMEOUT_SECONDS = 10.0
    READ_TIMEOUT_SECONDS = 15.0
    USER_AGENT = "MultiTenantAIPlatform-Bot/1.0 (+https://mmaip-backend.onrender.com; Educational AI Research)"

    def __init__(self, tenant_id: Optional[uuid.UUID] = None):
        self.tenant_id = tenant_id or uuid.uuid4()

    @classmethod
    def clear_cache(cls):
        """Clear memory cache (for testing/maintenance)."""
        _WEB_CACHE.clear()

    async def read_webpage(
        self,
        url: str,
        allow_http_for_testing: bool = False,
        bypass_cache: bool = False,
        tenant_id: Optional[uuid.UUID] = None,
        max_text_length: int = 20000,
    ) -> WebFetchResult:
        """Fetch and extract readable content from a public web page with strict SSRF defense."""
        # 1. SSRF Validation upfront
        try:
            validated_url, _ = validate_web_url(
                url,
                allow_http_for_testing=allow_http_for_testing,
                allowed_domains=getattr(settings, "WEB_ALLOWED_DOMAINS", ""),
            )
        except SSRFSecurityError as ssrf_err:
            domain = urlparse(url).netloc
            return WebFetchResult(self._make_error_result(url, domain, str(ssrf_err), status="BLOCKED_SSRF"))

        canonical_url = validated_url
        domain = urlparse(canonical_url).netloc.lower()

        cache_key = (str(self.tenant_id), canonical_url)
        now = time.time()
        if not bypass_cache and cache_key in _WEB_CACHE:
            ts, cached_result = _WEB_CACHE[cache_key]
            if now - ts < _CACHE_TTL_SECONDS:
                return {**cached_result, "cached": True}

        # 2. Bounded outbound fetch with manual redirect re-validation
        headers = {
            "User-Agent": self.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.5",
            "Accept-Language": "en-US,en;q=0.9",
        }

        timeout = httpx.Timeout(
            self.READ_TIMEOUT_SECONDS,
            connect=self.CONNECT_TIMEOUT_SECONDS,
        )

        current_url = canonical_url
        redirect_count = 0
        final_html = ""
        content_type = ""
        http_status = 200

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            while True:
                try:
                    resp = await client.get(current_url, headers=headers)
                except httpx.TimeoutException:
                    return self._make_error_result(
                        canonical_url,
                        domain,
                        "Request timed out while connecting to website.",
                        status="TIMEOUT",
                    )
                except httpx.RequestError as req_err:
                    return self._make_error_result(
                        canonical_url,
                        domain,
                        f"Network connection failed: {req_err}",
                        status="NETWORK_ERROR",
                    )

                # Check for redirect (301, 302, 303, 307, 308)
                if resp.is_redirect:
                    redirect_count += 1
                    if redirect_count > self.MAX_REDIRECTS:
                        raise SSRFSecurityError(f"Exceeded maximum allowed redirects ({self.MAX_REDIRECTS}).")

                    location = resp.headers.get("Location")
                    if not location:
                        raise SSRFSecurityError("Redirect response missing Location header.")

                    # Resolve relative redirect URLs against current URL
                    next_url = urljoin(current_url, location)

                    # CRITICAL: Re-validate redirect target against SSRF boundaries
                    validated_next_url, _ = validate_web_url(
                        next_url,
                        allow_http_for_testing=allow_http_for_testing,
                        allowed_domains=getattr(settings, "WEB_ALLOWED_DOMAINS", ""),
                    )
                    current_url = validated_next_url
                    canonical_url = current_url
                    domain = urlparse(canonical_url).netloc.lower()
                    continue

                http_status = resp.status_code
                content_type = resp.headers.get("content-type", "").lower()

                # Guard against binary files / oversized media
                if resp.status_code >= 400:
                    return self._make_error_result(
                        canonical_url,
                        domain,
                        f"Remote server responded with HTTP {resp.status_code}",
                        status=f"HTTP_{resp.status_code}",
                    )

                # Check content length header if provided
                cl_header = resp.headers.get("content-length")
                if cl_header:
                    try:
                        if int(cl_header) > self.MAX_RESPONSE_BYTES:
                            raise SSRFSecurityError(f"Response size ({cl_header} bytes) exceeds maximum limit of 2 MB.")
                    except ValueError:
                        pass

                # Read body and enforce size cap
                raw_bytes = resp.content
                if len(raw_bytes) > self.MAX_RESPONSE_BYTES:
                    raise SSRFSecurityError(f"Response body exceeds maximum limit of {self.MAX_RESPONSE_BYTES} bytes.")

                # Decode text with fallback
                encoding = resp.encoding or "utf-8"
                try:
                    final_html = raw_bytes.decode(encoding, errors="replace")
                except Exception:
                    final_html = raw_bytes.decode("utf-8", errors="replace")
                break

        # 3. Extract content
        extracted = WebContentExtractor.extract(final_html, source_url=canonical_url)

        content_hash = hashlib.sha256(extracted["content"].encode("utf-8")).hexdigest()
        retrieved_at = datetime.now(timezone.utc).isoformat()

        title = extracted["title"] or f"Page from {domain}"
        description = extracted["description"] or ""

        # Citation object format matching platform RAG conventions
        citation = {
            "source_type": "web",
            "source_url": canonical_url,
            "document_name": title,
            "domain": domain,
            "snippet": (description or extracted["content"])[:300],
            "retrieved_at": retrieved_at,
            "page_number": 1,
        }

        result = {
            "canonical_url": canonical_url,
            "domain": domain,
            "title": title,
            "description": description,
            "content": extracted["content"],
            "status": extracted["status"],
            "http_status": http_status,
            "content_type": content_type,
            "content_hash": content_hash,
            "char_count": extracted["char_count"],
            "retrieved_at": retrieved_at,
            "citation": citation,
            "cached": False,
        }

        # Cache successful results
        if extracted["status"] in ("SUCCESS", "FALLBACK_PARSED"):
            _WEB_CACHE[cache_key] = (now, result)

        return WebFetchResult({
            **result,
            "url": canonical_url,
            "hostname": domain,
            "extracted_text": result.get("content", ""),
            "text": result.get("content", ""),
        })

    def _make_error_result(self, url: str, domain: str, error_msg: str, status: str) -> dict[str, Any]:
        retrieved_at = datetime.now(timezone.utc).isoformat()
        return WebFetchResult({
            "canonical_url": url,
            "url": url,
            "domain": domain,
            "hostname": domain,
            "title": f"Unavailable Page ({domain})",
            "description": error_msg,
            "content": f"⚠️ Could not retrieve webpage: {error_msg}",
            "extracted_text": "",
            "text": "",
            "status": status,
            "http_status": 0,
            "content_type": "",
            "content_hash": "",
            "char_count": 0,
            "retrieved_at": retrieved_at,
            "citation": {
                "source_type": "web",
                "source_url": url,
                "document_name": domain,
                "domain": domain,
                "snippet": error_msg,
                "retrieved_at": retrieved_at,
                "page_number": None,
            },
            "cached": False,
        })


def get_web_fetch_service(tenant_id: Optional[uuid.UUID] = None) -> WebFetchService:
    return WebFetchService(tenant_id=tenant_id)
