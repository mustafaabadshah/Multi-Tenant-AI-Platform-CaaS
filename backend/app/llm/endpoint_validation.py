"""Central SSRF-safe validation for LLM provider endpoints.

Provider base URLs are validated before any HTTP client is constructed.
Validation resolves the hostname once at validation time; it does not pin
the resolved address to the subsequent connection. This leaves a narrow
DNS-rebinding window between validation and connect. Provider clients
therefore also disable automatic redirects so a validated public endpoint
cannot bounce credentials to a private, loopback, or link-local destination.

``allow_local=True`` is reserved for operator-controlled built-in endpoints
(the OmniRoute gateway). Tenant/BYOK supplied base URLs must always be
validated with ``allow_local=False`` and are additionally gated behind the
``CUSTOM_PROVIDER_ENDPOINTS_ENABLED`` feature flag.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

from app.core.config import settings

OFFICIAL_PROVIDER_HOSTS = frozenset(
    {
        "api.openai.com",
        "api.anthropic.com",
        "generativelanguage.googleapis.com",
        "api.groq.com",
    }
)

_METADATA_HOSTNAMES = frozenset(
    {
        "metadata",
        "instance-data",
        "metadata.google.internal",
        "metadata.goog",
    }
)

_METADATA_IPS = frozenset(
    {
        "169.254.169.254",
        "169.254.170.2",
        "169.254.170.23",
        "100.100.100.200",
        "fd00:ec2::254",
    }
)

_ALLOWED_SCHEMES = frozenset({"http", "https"})
_DEFAULT_PORTS = {"http": 80, "https": 443}


def _normalize_host(host: str) -> str:
    return host.strip().lower().rstrip(".")


def _candidate_addresses(
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    candidates: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = [ip]
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        candidates.append(mapped)
    return candidates


def _reject_metadata_address(
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address, host: str
) -> None:
    for candidate in _candidate_addresses(ip):
        if str(candidate) in _METADATA_IPS:
            raise ValueError(f"Access to cloud metadata address '{host}' is forbidden.")


def _reject_forbidden_address(
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address,
    host: str,
    *,
    allow_local: bool,
) -> None:
    for candidate in _candidate_addresses(ip):
        if candidate.is_link_local:
            raise ValueError(
                f"Access to link-local / cloud metadata address '{host}' is forbidden."
            )
        if candidate.is_multicast:
            raise ValueError(f"Access to multicast address '{host}' is forbidden.")
        if candidate.is_unspecified:
            raise ValueError(f"Access to unspecified address '{host}' is forbidden.")
        if candidate.is_loopback:
            if allow_local:
                continue
            raise ValueError(f"Access to loopback address '{host}' is forbidden.")
        if candidate.is_private:
            if allow_local:
                continue
            raise ValueError(f"Access to private address '{host}' is forbidden.")
        if candidate.is_reserved:
            raise ValueError(f"Access to reserved address '{host}' is forbidden.")


def validate_provider_endpoint(url: str, *, allow_local: bool = False) -> str:
    """Validate and normalize a provider endpoint URL.

    Raises ``ValueError`` with a sanitized message when the URL or any DNS
    answer is unsafe. The rejected host may appear in the message; embedded
    credentials never do.

    Note: validation resolves DNS at call time and does not pin the result to
    the later connection, so a determined attacker with control of DNS could
    rebind between validation and connect. Redirects are disabled in provider
    clients to prevent a second, unvalidated hop.
    """
    if not isinstance(url, str) or not url.strip():
        raise ValueError("Provider endpoint URL cannot be empty.")

    raw = url.strip()
    if any(ch.isspace() or ord(ch) < 0x20 for ch in raw):
        raise ValueError(
            "Provider endpoint URL contains invalid whitespace or control characters."
        )

    try:
        parsed = urlsplit(raw)
        scheme = (parsed.scheme or "").lower()
        hostname = parsed.hostname
        username = parsed.username
        password = parsed.password
        port = parsed.port
    except ValueError:
        raise ValueError("Invalid provider endpoint URL.") from None

    if scheme not in _ALLOWED_SCHEMES:
        raise ValueError(
            f"Invalid URL scheme '{scheme}'. Only http and https are permitted."
        )
    if username is not None or password is not None:
        raise ValueError("Provider endpoint URL must not contain embedded credentials.")
    if not hostname:
        raise ValueError("Invalid provider endpoint: missing hostname.")

    host = _normalize_host(hostname)
    if not host:
        raise ValueError("Invalid provider endpoint: missing hostname.")
    if host in _METADATA_HOSTNAMES:
        raise ValueError("Access to cloud metadata endpoint is forbidden.")

    if port is None:
        port = _DEFAULT_PORTS[scheme]
    if port < 1 or port > 65535:
        raise ValueError(f"Invalid port '{port}' for provider endpoint.")

    literal_address: ipaddress.IPv4Address | ipaddress.IPv6Address | None
    try:
        literal_address = ipaddress.ip_address(host)
    except ValueError:
        literal_address = None

    if literal_address is not None:
        _reject_metadata_address(literal_address, host)
        _reject_forbidden_address(literal_address, host, allow_local=allow_local)

    try:
        resolved = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, OSError):
        raise ValueError(f"Could not resolve provider endpoint host '{host}'.") from None

    addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for entry in resolved:
        sockaddr = entry[4]
        if not sockaddr:
            continue
        address_text = str(sockaddr[0]).split("%", 1)[0]
        try:
            addresses.append(ipaddress.ip_address(address_text))
        except ValueError:
            continue

    if not addresses:
        raise ValueError(f"Could not resolve provider endpoint host '{host}'.")

    for address in addresses:
        _reject_metadata_address(address, host)
        _reject_forbidden_address(address, host, allow_local=allow_local)

    return raw.rstrip("/")


def validate_custom_provider_endpoint(url: str) -> str:
    """Validate a tenant/BYOK supplied endpoint under the custom-endpoint policy."""
    if not settings.CUSTOM_PROVIDER_ENDPOINTS_ENABLED:
        raise ValueError(
            "Custom provider endpoints are disabled. "
            "Set CUSTOM_PROVIDER_ENDPOINTS_ENABLED=true to allow non-official "
            "provider base URLs."
        )
    return validate_provider_endpoint(url, allow_local=False)