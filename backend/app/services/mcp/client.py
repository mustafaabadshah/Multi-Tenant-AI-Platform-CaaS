"""Model Context Protocol (MCP) Streamable HTTP Client Service."""

import hashlib
import json
import logging
import re
from typing import Any, Optional

import httpx

from app.services.tools.ssrf import validate_outbound_url

logger = logging.getLogger("mmaip.mcp_client")

# Maximum response size allowed from remote MCP endpoints (1 MB)
MAX_MCP_RESPONSE_BYTES = 1024 * 1024
DEFAULT_MCP_TIMEOUT = 20.0


class MCPClientError(Exception):
    """Base exception for MCP connectivity and execution errors."""
    pass


class MCPClientService:
    """Streamable HTTP Client for Model Context Protocol (MCP) servers."""

    @staticmethod
    def calculate_schema_fingerprint(schema: dict[str, Any]) -> str:
        """Compute deterministic SHA-256 fingerprint of tool input schema to detect schema drift."""
        encoded = json.dumps(schema or {}, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def infer_tool_risk(name: str, description: Optional[str] = None) -> tuple[str, bool]:
        """Infer risk classification (READ_ONLY, WRITE, HIGH_RISK) and human approval requirement."""
        text = f"{name} {description or ''}".lower().replace("_", " ").replace("-", " ")

        high_risk_keywords = [
            "delete", "remove", "drop", "destroy", "execute", "exec", "eval",
            "transfer", "pay", "charge", "refund", "revoke", "grant", "permission",
            "sudo", "admin", "shell", "bash", "deploy"
        ]
        write_keywords = [
            "create", "update", "modify", "write", "post", "put", "send", "insert", "save"
        ]

        for kw in high_risk_keywords:
            if re.search(rf"\b{kw}\b", text):
                return "HIGH_RISK", True

        for kw in write_keywords:
            if re.search(rf"\b{kw}\b", text):
                return "WRITE", True

        return "READ_ONLY", False

    @staticmethod
    def parse_response(resp: httpx.Response) -> dict[str, Any]:
        """Extract JSON-RPC payload from application/json or text/event-stream SSE."""
        content_type = resp.headers.get("content-type", "")
        text = resp.text.strip()
        if "text/event-stream" in content_type or text.startswith("event:") or "data:" in text:
            for line in text.splitlines():
                line = line.strip()
                if line.startswith("data:"):
                    data_str = line[len("data:"):].strip()
                    if data_str:
                        try:
                            return json.loads(data_str)
                        except json.JSONDecodeError:
                            pass
        return resp.json()

    @classmethod
    async def _ensure_session(
        cls,
        client: httpx.AsyncClient,
        validated_url: str,
        headers: dict[str, str],
    ) -> Optional[str]:
        """Attempt MCP initialize handshake to acquire session token if required by Streamable HTTP."""
        init_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "MMAIP-MCP-Host", "version": "1.0"},
            },
        }
        try:
            init_resp = await client.post(validated_url, json=init_payload, headers=headers)
            if init_resp.is_success:
                sid = init_resp.headers.get("mcp-session-id")
                if sid:
                    notif_headers = dict(headers)
                    notif_headers["mcp-session-id"] = sid
                    await client.post(
                        validated_url,
                        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                        headers=notif_headers,
                    )
                return sid
        except Exception:
            pass
        return None

    @classmethod
    async def discover_tools(
        cls,
        server_url: str,
        auth_token: Optional[str] = None,
        timeout_seconds: float = DEFAULT_MCP_TIMEOUT,
        allow_http_for_testing: bool = False,
    ) -> list[dict[str, Any]]:
        """Connect to remote MCP server over Streamable HTTP and discover published tools."""
        validated_url = validate_outbound_url(server_url, allow_http_for_testing=allow_http_for_testing)

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": "MMAIP-MCP-Host/1.0",
        }
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {},
        }

        try:
            timeout = httpx.Timeout(timeout_seconds, connect=5.0)
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
                sid = await cls._ensure_session(client, validated_url, headers)
                req_headers = dict(headers)
                if sid:
                    req_headers["mcp-session-id"] = sid

                resp = await client.post(validated_url, json=payload, headers=req_headers)
                if not resp.is_success:
                    raise MCPClientError(f"MCP server returned HTTP {resp.status_code}: {resp.text[:300]}")

                body = cls.parse_response(resp)
                if "error" in body:
                    err_info = body["error"]
                    raise MCPClientError(f"MCP protocol error ({err_info.get('code')}): {err_info.get('message')}")

                raw_tools = body.get("result", {}).get("tools", [])
                discovered: list[dict[str, Any]] = []

                for t in raw_tools:
                    name = str(t.get("name", "")).strip()
                    if not name:
                        continue

                    description = t.get("description")
                    input_schema = t.get("inputSchema", {})
                    fingerprint = cls.calculate_schema_fingerprint(input_schema)
                    risk_level, requires_approval = cls.infer_tool_risk(name, description)

                    discovered.append({
                        "name": name,
                        "display_name": name.replace("_", " ").title(),
                        "description": description,
                        "input_schema": input_schema,
                        "schema_fingerprint": fingerprint,
                        "risk_level": risk_level,
                        "requires_approval": requires_approval,
                    })

                return discovered

        except httpx.TimeoutException as err:
            raise MCPClientError(f"Connection to MCP server timed out after {timeout_seconds}s.") from err
        except httpx.HTTPError as err:
            raise MCPClientError(f"HTTP communication error connecting to MCP server: {err}") from err

    @classmethod
    async def call_tool(
        cls,
        server_url: str,
        tool_name: str,
        arguments: dict[str, Any],
        auth_token: Optional[str] = None,
        timeout_seconds: float = DEFAULT_MCP_TIMEOUT,
        allow_http_for_testing: bool = False,
    ) -> dict[str, Any]:
        """Dispatch a tool call to the remote MCP server and return sanitized output."""
        validated_url = validate_outbound_url(server_url, allow_http_for_testing=allow_http_for_testing)

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": "MMAIP-MCP-Host/1.0",
        }
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }

        try:
            timeout = httpx.Timeout(timeout_seconds, connect=5.0)
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
                sid = await cls._ensure_session(client, validated_url, headers)
                req_headers = dict(headers)
                if sid:
                    req_headers["mcp-session-id"] = sid

                resp = await client.post(validated_url, json=payload, headers=req_headers)
                if not resp.is_success:
                    raise MCPClientError(f"MCP server execution returned HTTP {resp.status_code}")

                # Check max response size
                content = await resp.aread()
                if len(content) > MAX_MCP_RESPONSE_BYTES:
                    raise MCPClientError(f"MCP response exceeded maximum size limit of {MAX_MCP_RESPONSE_BYTES} bytes.")

                body = cls.parse_response(resp)
                if "error" in body:
                    err_info = body["error"]
                    raise MCPClientError(f"MCP error: {err_info.get('message', 'Unknown error')}")

                result = body.get("result", {})
                content_blocks = result.get("content", [])

                # Extract text representations
                text_outputs: list[str] = []
                for b in content_blocks:
                    if isinstance(b, dict):
                        if b.get("type") == "text":
                            text_outputs.append(str(b.get("text", "")))
                        else:
                            text_outputs.append(json.dumps(b))
                    else:
                        text_outputs.append(str(b))

                merged_text = "\n".join(text_outputs) if text_outputs else json.dumps(result)

                # Prompt-injection / secret leakage defense: sanitize output
                sanitized_output = re.sub(r"(sk-[a-zA-Z0-9_\-]{8,})", "[REDACTED_API_KEY]", merged_text)

                return {
                    "is_error": result.get("isError", False),
                    "content": sanitized_output,
                    "raw_result": result,
                }

        except httpx.TimeoutException as err:
            raise MCPClientError(f"MCP tool '{tool_name}' timed out after {timeout_seconds}s.") from err
        except httpx.HTTPError as err:
            raise MCPClientError(f"MCP call failed: {err}") from err
