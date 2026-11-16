# M20.5 — Live MCP & Custom Tools Test Report

| Scenario | Target Endpoint | Payload / Action | Expected Result | Live Staging Evidence | Status |
|---|---|---|---|---|---|
| **TOOL-01** | Tool List | `GET /api/v1/tools` | Return built-in tools | 2 tools returned (`calculator`, `weather_lookup`) | **PASS** |
| **TOOL-02** | Custom Tool Creation | `POST /api/v1/tools` | Create synthetic tool with input schema | 201 Created (`synthetic_weather_checker`) | **PASS** |
| **TOOL-03** | Write-Only Secrets | `GET /api/v1/tools/{id}` | Redact sensitive auth tokens | Verified: `auth_token` omitted in response | **PASS** |
| **TOOL-04** | Assistant Tool Binding | `PUT /api/v1/assistants/{id}` | Persist `tools_config` | Verified: `enabled_tool_ids` persisted in DB | **PASS** |
| **TOOL-05** | Tool Cleanup | `DELETE /api/v1/tools/{id}` | Safely remove disposable test record | 204 No Content, deleted cleanly | **PASS** |
| **MCP-01** | List MCP Connections | `GET /api/v1/mcp/connections` | Return active workspace connections | 200 OK, count=0 | **PASS** |
| **MCP-02** | SSRF Loopback Protection | `POST /api/v1/mcp/connections` | `endpoint_url: http://127.0.0.1:8000/sse` | 422 Unprocessable Entity (SSRF rejected) | **PASS** |
| **MCP-03** | Cloud Metadata Protection | `POST /api/v1/mcp/connections` | `endpoint_url: http://169.254.169.254/...` | 422 Unprocessable Entity (SSRF rejected) | **PASS** |
| **MCP-04** | Remote MCP Global Flag | Staging Environment | Unapproved arbitrary MCP execution blocked | Verified: `MCP_ENABLED=false` enforced | **PASS** |

---

## 1. Network Boundary & SSRF Hardening

Live probing against `https://mmaip-backend.onrender.com/api/v1/mcp/connections` confirmed that URL validation rejects:
- Loopback addresses (`127.0.0.0/8`, `::1`)
- Link-local and cloud metadata addresses (`169.254.169.254`)
- Private RFC 1918 subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`)
- Non-HTTPS remote endpoints (HTTP plain-text disallowed in production mode)

## 2. Remote MCP Status

Per safety contract, arbitrary remote MCP execution remains disabled (`MCP_ENABLED=false`), and remote MCP invocation against third-party endpoints is marked **NOT RUN (SECURE DEFAULT)**.
