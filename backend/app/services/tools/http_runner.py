"""Safe HTTP tool execution runner with SSRF prevention and payload bounding."""

import logging
from typing import Any, Optional

import httpx

from app.services.tools.ssrf import validate_outbound_url

logger = logging.getLogger("mmaip.tools.http_runner")

DEFAULT_TIMEOUT_SECONDS = 15
DEFAULT_MAX_RESPONSE_BYTES = 1048576  # 1 MB


class ToolExecutionError(RuntimeError):
    """Raised when a tool execution fails due to network, validation, or timeout errors."""
    pass


async def execute_custom_http_tool(
    endpoint_url: str,
    method: str = "POST",
    headers: Optional[dict[str, str]] = None,
    query_params: Optional[dict[str, Any]] = None,
    body: Optional[Any] = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    allow_http_for_testing: bool = False,
) -> dict[str, Any]:
    """Execute a validated outbound HTTP tool request safely."""
    # 1. SSRF & URL Validation
    validated_url = validate_outbound_url(endpoint_url, allow_http_for_testing=allow_http_for_testing)

    clean_method = method.upper().strip()
    if clean_method not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
        raise ToolExecutionError(f"HTTP method '{clean_method}' is not supported.")

    effective_headers = {
        "User-Agent": "MMAIP-ToolRunner/1.0",
        "Accept": "application/json, text/plain",
    }
    if headers:
        effective_headers.update(headers)

    timeout = httpx.Timeout(min(timeout_seconds, 30.0), connect=5.0)

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            req = client.build_request(
                clean_method,
                validated_url,
                headers=effective_headers,
                params=query_params or {},
                json=body if isinstance(body, (dict, list)) else None,
                content=str(body) if body is not None and not isinstance(body, (dict, list)) else None,
            )

            # Cap request size
            if req.content and len(req.content) > max_response_bytes:
                raise ToolExecutionError("Request payload exceeds maximum allowed size.")

            response = await client.send(req)

            # Check response size
            content = await response.aread()
            if len(content) > max_response_bytes:
                raise ToolExecutionError(
                    f"Tool response size ({len(content)} bytes) exceeds maximum limit ({max_response_bytes} bytes)."
                )

            # Parse JSON if applicable, otherwise return plain text
            try:
                parsed_json = response.json()
                result_data = parsed_json
            except Exception:
                result_data = content.decode("utf-8", errors="replace")

            return {
                "status_code": response.status_code,
                "is_success": response.is_success,
                "data": result_data,
            }

    except httpx.TimeoutException as err:
        raise ToolExecutionError(f"Tool request timed out after {timeout_seconds}s.") from err
    except httpx.RequestError as err:
        raise ToolExecutionError(f"Tool request failed: {type(err).__name__}") from err
