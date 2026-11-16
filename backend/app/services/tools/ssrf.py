"""SSRF Protection and URL validation security boundary for outbound custom tool and MCP requests."""

import ipaddress
import socket
from urllib.parse import urlparse


class SSRFSecurityError(ValueError):
    """Raised when an outbound URL violates SSRF or private network isolation policies."""
    pass


FORBIDDEN_HOSTNAMES = frozenset({
    "localhost",
    "127.0.0.1",
    "::1",
    "metadata.google.internal",
    "instance-data",
})


def validate_outbound_url(url: str, allow_http_for_testing: bool = False) -> str:
    """Validate that a URL is safe for outbound execution.

    Enforces:
    - HTTPS scheme required (unless testing explicitly enabled for synthetic fixtures).
    - No userinfo/credentials in authority (e.g. user:pass@host).
    - Hostname resolves to a public, non-private, non-loopback, non-metadata IP address.
    """
    if not url or not isinstance(url, str):
        raise SSRFSecurityError("URL must be a non-empty string.")

    parsed = urlparse(url.strip())

    # 1. Validate Scheme
    if not allow_http_for_testing and parsed.scheme.lower() != "https":
        raise SSRFSecurityError(f"Protocol '{parsed.scheme}' forbidden. Only HTTPS outbound endpoints are permitted.")
    if parsed.scheme.lower() not in ("https", "http"):
        raise SSRFSecurityError(f"Unsupported scheme: '{parsed.scheme}'.")

    # 2. Block credentials in URL
    if parsed.username or parsed.password:
        raise SSRFSecurityError("URLs containing embedded username or password credentials are forbidden.")

    hostname = parsed.hostname
    if not hostname:
        raise SSRFSecurityError("URL must have a valid hostname.")

    hostname_lower = hostname.lower().strip()
    if hostname_lower in FORBIDDEN_HOSTNAMES:
        raise SSRFSecurityError(f"Host '{hostname}' is a restricted local or cloud metadata address.")

    # 3. Resolve DNS and check all returned IP addresses
    try:
        addr_info = socket.getaddrinfo(hostname_lower, None)
    except socket.gaierror as err:
        raise SSRFSecurityError(f"Failed to resolve host '{hostname}': {err}") from err

    resolved_ips: set[str] = set()
    for item in addr_info:
        sockaddr = item[4]
        ip_str = sockaddr[0]
        resolved_ips.add(ip_str)

    if not resolved_ips:
        raise SSRFSecurityError(f"Could not resolve any IP address for host '{hostname}'.")

    for ip_str in resolved_ips:
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError as val_err:
            raise SSRFSecurityError(f"Invalid IP address returned: '{ip_str}'") from val_err

        # Disallow loopback, private, link-local, multicast, or reserved IPs
        if ip.is_loopback:
            raise SSRFSecurityError(f"Destination IP '{ip_str}' resolves to a forbidden loopback address.")
        if ip.is_private and not allow_http_for_testing:
            raise SSRFSecurityError(f"Destination IP '{ip_str}' resolves to a forbidden private network (RFC1918).")
        if ip.is_link_local:
            raise SSRFSecurityError(f"Destination IP '{ip_str}' resolves to a forbidden link-local address.")
        if ip.is_multicast:
            raise SSRFSecurityError(f"Destination IP '{ip_str}' resolves to a forbidden multicast address.")
        if ip.is_reserved:
            raise SSRFSecurityError(f"Destination IP '{ip_str}' resolves to a reserved address.")

        # Special check for cloud metadata (169.254.169.254)
        if str(ip) == "169.254.169.254":
            raise SSRFSecurityError("Destination IP matches AWS/GCP/Azure cloud metadata service (169.254.169.254).")

    return url.strip()
