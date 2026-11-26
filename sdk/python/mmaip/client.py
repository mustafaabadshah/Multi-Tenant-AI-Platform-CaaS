"""Python Client Implementation for Multi-Tenant AI Platform."""

import json
from collections.abc import Generator
from typing import Any, Optional

import httpx


class MMAIPError(Exception):
    """Base exception for all MMAIP SDK errors."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class MMAIPClient:
    """Synchronous and streaming client for the Multi-Tenant AI Platform Developer API."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "http://localhost:8000/api/v1",
        timeout: float = 30.0,
    ):
        if not api_key:
            raise MMAIPError("API key is required to initialize MMAIPClient")
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "mmaip-python-sdk/0.1.0",
        }

    def list_assistants(self) -> list[dict[str, Any]]:
        """List all assistants accessible to the authenticated API key."""
        url = f"{self.base_url}/developer/assistants"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, headers=self._headers())
            if not resp.is_success:
                raise MMAIPError(f"Failed to list assistants: {resp.text}", resp.status_code)
            return resp.json()

    def stream_chat(
        self,
        assistant_id: str,
        message: str,
        conversation_id: Optional[str] = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Stream assistant response tokens and citations via Server-Sent Events (SSE)."""
        url = f"{self.base_url}/developer/assistants/{assistant_id}/chat"
        payload = {
            "message": message,
            "conversation_id": conversation_id,
        }

        with httpx.Client(timeout=self.timeout) as client:
            with client.stream("POST", url, headers=self._headers(), json=payload) as response:
                if not response.is_success:
                    err_msg = response.read().decode("utf-8", errors="ignore")
                    raise MMAIPError(f"Chat stream failed ({response.status_code}): {err_msg}", response.status_code)

                buffer = ""
                for chunk in response.iter_text():
                    buffer += chunk
                    while "\n\n" in buffer:
                        block, buffer = buffer.split("\n\n", 1)
                        if not block.strip():
                            continue

                        event_type = "message"
                        data_str = ""
                        for line in block.split("\n"):
                            if line.startswith("event:"):
                                event_type = line[6:].strip()
                            elif line.startswith("data:"):
                                data_str += line[5:].strip()

                        if data_str:
                            try:
                                yield {"event": event_type, "data": json.loads(data_str)}
                            except Exception:
                                yield {"event": event_type, "data": {"raw": data_str}}
