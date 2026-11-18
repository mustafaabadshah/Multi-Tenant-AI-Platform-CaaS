"""SSRF Defense-in-Depth and Safe URL Validation for Web Intelligence (M27)."""

import ipaddress
import re
import socket
from urllib.parse import urlparse, urljoin


class SSRFSecurityError(ValueError):
    """Raised when an outbound URL violates SSRF, private network, or network egress security policies."""
    pass


FORBIDDEN_HOSTNAMES = frozenset({
    "localhost",
    "127.0.0.1",
    "::1",
    "0.0.0.0",
    "metadata.google.internal",
    "instance-data",
    "169.254.169.254",
})

ALLOWED_PORTS = frozenset({80, 443})




def verify_ip_address(ip_str: str, allow_http_for_testing: bool = False) -> None:
    """Validate that an individual IP address is public, routable, and safe."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError as val_err:
        raise SSRFSecurityError(f"Invalid IP address returned: '{ip_str}'") from val_err

    # Check loopback
    if ip.is_loopback:
        raise SSRFSecurityError(f"Destination IP '{ip_str}' resolves to a forbidden loopback address.")

    # Check private networks (RFC1918)
    if ip.is_private and not allow_http_for_testing:
        raise SSRFSecurityError(f"Destination IP '{ip_str}' resolves to a forbidden private network (RFC1918).")

    # Check link-local addresses
    if ip.is_link_local:
        raise SSRFSecurityError(f"Destination IP '{ip_str}' resolves to a forbidden link-local address.")

    # Check multicast
    if ip.is_multicast:
        raise SSRFSecurityError(f"Destination IP '{ip_str}' resolves to a forbidden multicast address.")

    # Check reserved
    if ip.is_reserved:
        raise SSRFSecurityError(f"Destination IP '{ip_str}' resolves to a reserved address.")

    # Cloud metadata endpoint check (169.254.169.254)
    if str(ip) == "169.254.169.254":
        raise SSRFSecurityError("Destination IP matches AWS/GCP/Azure cloud metadata service (169.254.169.254).")

    # 0.0.0.0 / unspecified
    if ip.is_unspecified:
        raise SSRFSecurityError(f"Destination IP '{ip_str}' is an unspecified address.")


def validate_web_url(
    url: str,
    allow_http_for_testing: bool = False,
    allowed_domains: str = "",
) -> tuple[str, list[str]]:
    """Validate that a public web URL is safe for outbound fetching.

    Enforces:
    1. Scheme: Only HTTPS (or HTTP if testing explicitly enabled).
    2. Authority: No embedded user credentials (user:pass@host).
    3. Port: Only standard web ports (80, 443).
    4. Hostname: Cannot be loopback, metadata, or local name.
    5. Domain allowlist: If allowed_domains is configured, hostname must match.
    6. DNS Resolution: All IPv4 (A) and IPv6 (AAAA) records must be public and routable.

    Returns:
        tuple[normalized_url, list_of_resolved_public_ips]
    """
    if not url or not isinstance(url, str):
        raise SSRFSecurityError("URL must be a non-empty string.")

    cleaned_url = url.strip()

    # Basic length check to prevent memory exhaustion
    if len(cleaned_url) > 2048:
        raise SSRFSecurityError("URL exceeds maximum length of 2048 characters.")

    try:
        parsed = urlparse(cleaned_url)
    except Exception as e:
        raise SSRFSecurityError(f"Malformed URL: {e}") from e

    # 1. Scheme Check
    scheme = parsed.scheme.lower()
    if not allow_http_for_testing and scheme != "https":
        raise SSRFSecurityError(f"Protocol '{scheme}' is forbidden. Only HTTPS public URLs are permitted.")
    if scheme not in ("https", "http"):
        raise SSRFSecurityError(f"Unsupported URL scheme: '{scheme}'.")

    # 2. Block embedded credentials
    if parsed.username or parsed.password:
        raise SSRFSecurityError("URLs containing embedded username or password credentials are forbidden.")

    # 3. Hostname check
    hostname = parsed.hostname
    if not hostname:
        raise SSRFSecurityError("URL must have a valid hostname.")

    hostname_lower = hostname.lower().strip()
    if hostname_lower in FORBIDDEN_HOSTNAMES:
        raise SSRFSecurityError(f"Host '{hostname}' is a restricted local or cloud metadata address.")

    # Reject numeric/hex/octal IP obfuscation in hostname string
    if re.match(r"^(?:0x[0-9a-fA-F]+|\d+|0[0-7]+)$", hostname_lower):
        raise SSRFSecurityError("Integer or hex encoded IP addresses are forbidden.")

    # 4. Port Check
    port = parsed.port
    if port is not None and port not in ALLOWED_PORTS and not allow_http_for_testing:
        raise SSRFSecurityError(f"Port {port} is not permitted. Only standard web ports (80, 443) are allowed.")

    # 5. Domain allowlist check (if configured)
    if allowed_domains and allowed_domains.strip():
        allowed_list = [d.strip().lower() for d in allowed_domains.split(",") if d.strip()]
        if allowed_list and not any(hostname_lower == d or hostname_lower.endswith(f".{d}") for d in allowed_list):
            raise SSRFSecurityError(f"Host '{hostname}' is not in the allowed domains list.")

    # 6. DNS Resolution & All-IP validation
    try:
        addr_info = socket.getaddrinfo(hostname_lower, port or (443 if scheme == "https" else 80))
    except socket.gaierror as err:
        raise SSRFSecurityError(f"Failed to resolve host '{hostname}': {err}") from err

    resolved_ips: list[str] = []
    for item in addr_info:
        sockaddr = item[4]
        ip_str = sockaddr[0]
        if ip_str not in resolved_ips:
            resolved_ips.append(ip_str)

    if not resolved_ips:
        raise SSRFSecurityError(f"Could not resolve any IP address for host '{hostname}'.")

    for ip_str in resolved_ips:
        verify_ip_address(ip_str, allow_http_for_testing)

    return cleaned_url, resolved_ips


# ---------------------------------------------------------------------------
# Connection-Level SSRF & DNS Rebinding Defense (M28.2)
# ---------------------------------------------------------------------------

import httpcore
import httpx


class SSRFSafeNetworkBackend(httpcore.AnyIOBackend):
    """Network backend enforcing socket-level IP verification at connection time.

    Eliminates DNS Time-of-Check / Time-of-Use (TOCTOU) and DNS rebinding attacks
    by resolving and verifying all destination IPs immediately before socket creation,
    and verifying the actual connected socket peer IP before TLS handshake or HTTP exchange.
    """

    def __init__(self, allow_http_for_testing: bool = False):
        super().__init__()
        self.allow_http_for_testing = allow_http_for_testing

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: httpcore.SOCKET_OPTION | None = None,
    ) -> httpcore.AsyncNetworkStream:
        # Pre-connect DNS verification of the destination host
        try:
            addr_info = socket.getaddrinfo(host, port)
            for item in addr_info:
                target_ip = item[4][0]
                verify_ip_address(target_ip, self.allow_http_for_testing)
        except socket.gaierror as gai_err:
            raise SSRFSecurityError(f"DNS resolution failed for '{host}': {gai_err}") from gai_err

        # Establish TCP connection
        stream = await super().connect_tcp(
            host=host,
            port=port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )

        # Inspect the actual connected peer address on the established socket
        try:
            peer = stream.get_extra_info("peername")
            if peer and isinstance(peer, (tuple, list)) and len(peer) > 0:
                peer_ip = str(peer[0])
                verify_ip_address(peer_ip, self.allow_http_for_testing)
        except Exception as peer_err:
            await stream.aclose()
            raise SSRFSecurityError(f"Connection-level SSRF verification failed for peer {host}: {peer_err}") from peer_err

        return stream


class SSRFSafeAsyncTransport(httpx.AsyncHTTPTransport):
    """Custom httpx transport backed by SSRFSafeNetworkBackend and single-hop connection pool."""

    def __init__(self, allow_http_for_testing: bool = False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.backend = SSRFSafeNetworkBackend(allow_http_for_testing=allow_http_for_testing)
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=self._pool._ssl_context,
            network_backend=self.backend,
            http1=True,
            http2=False,
            retries=0,
            socket_options=kwargs.get("socket_options"),
        )
