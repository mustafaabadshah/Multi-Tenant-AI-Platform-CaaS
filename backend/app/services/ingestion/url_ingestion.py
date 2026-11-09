"""Safe URL Ingestion Service with strict SSRF defense, DNS rebinding mitigation, and content limits."""

import ipaddress
import logging
import re
import socket
import urllib.parse
import uuid
from typing import Optional

import httpx

from app.core.config import settings
from app.models.knowledge import Document, DocumentVersion, IngestionJob, KnowledgeBase
from app.repositories.document_repository import DocumentRepository, IngestionJobRepository
from app.services.ingestion.service import run_ingestion_in_background
from app.storage import get_storage_provider

logger = logging.getLogger("mmaip.services.url_ingest")

# Blocked IP networks for SSRF protection
BLOCKED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("127.0.0.0/8"),       # Loopback
    ipaddress.ip_network("10.0.0.0/8"),        # Private RFC 1918
    ipaddress.ip_network("172.16.0.0/12"),     # Private RFC 1918
    ipaddress.ip_network("192.168.0.0/16"),    # Private RFC 1918
    ipaddress.ip_network("169.254.0.0/16"),    # Link-local / Cloud metadata (169.254.169.254)
    ipaddress.ip_network("100.64.0.0/10"),     # Carrier-grade NAT
    ipaddress.ip_network("::1/128"),           # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),          # IPv6 Unique Local
    ipaddress.ip_network("fe80::/10"),         # IPv6 Link-Local
]

BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata.google.internal",
    "instance-data",
    "169.254.169.254",
}

MAX_URL_CONTENT_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_CONTENT_TYPES = [
    "text/html",
    "text/plain",
    "text/markdown",
    "application/json",
    "application/pdf",
]


class SSRFValidationError(Exception):
    """Raised when an ingested URL targets internal, loopback, or metadata destinations."""
    pass


def validate_destination_ip(host: str) -> str:
    """Resolve destination hostname and ensure it does not route to private, loopback, or metadata addresses."""
    cleaned_host = host.lower().strip()
    if cleaned_host in BLOCKED_HOSTNAMES:
        raise SSRFValidationError(f"Target host '{cleaned_host}' is blocked for security.")

    try:
        # Resolve address records
        addr_info = socket.getaddrinfo(cleaned_host, None)
        if not addr_info:
            raise SSRFValidationError(f"Could not resolve host '{cleaned_host}'")

        for item in addr_info:
            ip_str = item[4][0]
            ip_obj = ipaddress.ip_address(ip_str)

            for blocked in BLOCKED_NETWORKS:
                if ip_obj in blocked:
                    raise SSRFValidationError(
                        f"Target IP {ip_str} falls within blocked network {blocked}."
                    )
        return addr_info[0][4][0]
    except (socket.gaierror, socket.herror) as exc:
        raise SSRFValidationError(f"DNS resolution failure for host '{cleaned_host}': {exc}") from exc


async def fetch_url_content_safe(url: str, max_redirects: int = 3) -> tuple[str, bytes, str]:
    """Fetch URL with SSRF protection, strict redirect revalidation, and content type filtering.

    Returns (clean_title, content_bytes, mime_type).
    """
    current_url = url.strip()
    redirect_count = 0

    while True:
        parsed = urllib.parse.urlparse(current_url)
        if parsed.scheme not in ("http", "https"):
            raise SSRFValidationError(f"Unsupported URL scheme: {parsed.scheme}. Only HTTP/HTTPS allowed.")

        if not parsed.hostname:
            raise SSRFValidationError("Missing hostname in target URL.")

        # Revalidate IP on every hop to block DNS rebinding and internal redirects
        validate_destination_ip(parsed.hostname)

        async with httpx.AsyncClient(
            follow_redirects=False,
            timeout=15.0,
            headers={"User-Agent": "MultiTenant-AI-Platform/1.0 (Safe URL Ingester)"},
        ) as client:
            resp = await client.get(current_url)

        if resp.is_redirect:
            redirect_count += 1
            if redirect_count > max_redirects:
                raise SSRFValidationError(f"Exceeded maximum redirect limit of {max_redirects}.")
            location = resp.headers.get("location")
            if not location:
                raise SSRFValidationError("Redirect response missing Location header.")
            current_url = urllib.parse.urljoin(current_url, location)
            continue

        if not resp.is_success:
            raise ValueError(f"HTTP error {resp.status_code} fetching URL: {resp.text[:200]}")

        content_length = len(resp.content)
        if content_length > MAX_URL_CONTENT_BYTES:
            raise ValueError(f"Content length {content_length} bytes exceeds maximum allowed {MAX_URL_CONTENT_BYTES} bytes.")

        raw_ct = resp.headers.get("content-type", "text/html").lower()
        mime_type = raw_ct.split(";")[0].strip()

        if not any(mime_type.startswith(allowed) for allowed in ALLOWED_CONTENT_TYPES):
            raise ValueError(f"Unsupported content type '{mime_type}'. Supported: {ALLOWED_CONTENT_TYPES}")

        # Extract title if HTML
        title = parsed.path.rstrip("/").split("/")[-1] or parsed.hostname
        if "html" in mime_type:
            try:
                text_content = resp.content.decode("utf-8", errors="ignore")
                match = re.search(r"<title[^>]*>(.*?)</title>", text_content, re.IGNORECASE | re.DOTALL)
                if match:
                    extracted_title = match.group(1).strip()
                    if extracted_title:
                        title = extracted_title
            except Exception:
                pass

        return title, resp.content, mime_type
