# URL Ingestion & SSRF Mitigation Architecture (M07)

## Threat Model
Ingesting web URLs exposes servers to Server-Side Request Forgery (SSRF), DNS rebinding, internal network reconnaissance, and cloud metadata theft (e.g., AWS/GCP instance credentials).

## Implemented Defense-in-Depth

```
  [User URL Input]
         │
         ▼
[Protocol Check: http/https only]
         │
         ▼
[Hostname Blacklist: localhost, metadata.google.internal, instance-data]
         │
         ▼
[DNS Resolution & IP Network Inspection]
  ├── Block: 127.0.0.0/8 (Loopback)
  ├── Block: 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16 (RFC 1918 Private)
  ├── Block: 169.254.0.0/16 (Link-Local & Cloud Metadata 169.254.169.254)
  └── Block: ::1/128, fc00::/7, fe80::/10 (IPv6 Loopback & Unique Local)
         │
         ▼
[Async HTTP Client with follow_redirects=False]
         │
         ▼
[Redirect Destination Re-Validation on Every Hop]
         │
         ▼
[Size Ceiling: max 10 MB] & [Content-Type Whitelist: text/html, json, markdown, pdf]
```

### Protection Against DNS Rebinding
Standard libraries that follow redirects automatically or re-resolve hostnames post-validation are vulnerable to Time-of-Check to Time-of-Use (TOCTOU) DNS rebinding attacks. 

Our implementation (`backend/app/services/ingestion/url_ingestion.py`):
1. Configures `httpx.AsyncClient(follow_redirects=False)`.
2. Inspects HTTP 301/302/307/308 redirect headers manually.
3. Completely re-resolves and validates the destination IP before initiating each subsequent request hop.
4. Enforces a maximum redirect depth of 3 hops.
