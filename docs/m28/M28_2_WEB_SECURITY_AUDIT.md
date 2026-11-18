# M28.2 Web Security & SSRF Defense Audit

## 1. Problem Statement & Threat Model
In M27/M28.1, URL preflight and web reading used `validate_web_url()` with `socket.getaddrinfo()`.
However, because `httpx` internally re-resolves domain names when opening TCP sockets, an attacker controlling an authoritative nameserver could return a public IP during preflight and a private IP (e.g., `127.0.0.1`, `169.254.169.254`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`) upon actual connection establishment (DNS Rebinding / TOCTOU).
Furthermore, responses buffered into memory using `client.get()` risked memory exhaustion (decompression bombs / payload flood).

## 2. Technical Remediation

### 2.1 Connection-Level Socket Peer IP Validation
In `backend/app/services/web/ssrf.py`:
- Implemented `verify_ip_address(ip: ipaddress.IPv4Address | IPv6Address)` which strictly validates against:
  - Private IP spaces (RFC1918, RFC4193).
  - Loopback addresses (`127.0.0.0/8`, `::1`).
  - Link-local and cloud metadata endpoints (`169.254.169.254`, `fe80::/10`).
  - Reserved, broadcast, and multicast addresses.
- Implemented `SSRFSafeNetworkBackend(httpcore.AnyIOBackend)`:
  - Hooks `connect_tcp` and `connect_tls`.
  - Performs pre-connect DNS resolution and verifies all candidate addresses.
  - Immediately upon socket establishment, queries `stream.get_extra_info("socket").getpeername()`.
  - If the connected peer IP is non-public, the stream is closed immediately and `SSRFSecurityError` is raised before any HTTP request bytes or headers are sent.
- Implemented `SSRFSafeAsyncTransport(httpx.AsyncHTTPTransport)` configured with `SSRFSafeNetworkBackend`.

### 2.2 Streaming Body Size & Decompression Bomb Protection
In `backend/app/services/web/reader.py`:
- Configured `httpx.AsyncClient(transport=SSRFSafeAsyncTransport(...))`.
- Used `client.stream("GET", ...)` instead of `client.get(...)`.
- Iterated incoming bytes via `resp.aiter_bytes()`, enforcing `MAX_RESPONSE_BYTES = 2 * 1024 * 1024` (2 MiB).
- If accumulated raw/decompressed bytes exceed 2 MiB, the stream is aborted immediately with `ValueError("Payload exceeds maximum size limit of 2 MiB")` without buffering the full response into RAM.
- Text content is capped at `MAX_TEXT_LENGTH = 100_000` characters.

## 3. Adversarial Test Verification
- `test_ssrf_blocks_forbidden_destinations`: Blocks localhost, 127.0.0.1, 169.254.169.254, 10.0.0.1, and cloud metadata.
- `test_ssrf_connection_level_backend_blocks_private_peer`: Proves `SSRFSafeNetworkBackend` rejects TCP connection if socket peer resolves to private IP, preventing DNS rebinding.

## 4. Gate Assessment
**WEB_EGRESS_SECURITY = PASS**
Outbound connections enforce public HTTPS-only targets with socket peer verification and 2 MiB hard streaming limits.
