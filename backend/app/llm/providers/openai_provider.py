import ipaddress
import json
import logging
import os
from collections.abc import AsyncIterator
from typing import Optional
from urllib.parse import urlparse

import httpx

from app.llm.base import (
    LLMAuthenticationError,
    LLMConfig,
    LLMConnectionError,
    LLMMessage,
    LLMProvider,
    LLMProviderError,
    LLMRateLimitError,
    LLMResponse,
    LLMStreamChunk,
    LLMTimeoutError,
)

logger = logging.getLogger("mmaip.llm.openai")


def validate_provider_endpoint(url: str, allow_local: bool = True) -> str:
    """Validate provider endpoint URL against SSRF, cloud metadata addresses, and invalid protocols."""
    if not url or not url.strip():
        raise ValueError("Provider endpoint URL cannot be empty")

    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Invalid URL scheme '{parsed.scheme}'. Only http and https are permitted.")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Invalid provider endpoint: missing hostname")

    # Check for link-local / cloud metadata IPs (e.g. 169.254.169.254)
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_link_local:
            raise ValueError(f"Access to link-local / cloud metadata address '{hostname}' is forbidden.")
        if not allow_local and (ip.is_loopback or ip.is_private):
            raise ValueError(f"Access to private/local address '{hostname}' is forbidden.")
    except ValueError as e:
        if "forbidden" in str(e):
            raise
        # If hostname is not an IP literal, block known cloud metadata hostnames
        if hostname.lower() in ("metadata.google.internal", "instance-data", "metadata"):
            raise ValueError("Access to cloud metadata endpoint is forbidden.")

    return url.rstrip("/")


class OpenAICompatibleLLMProvider(LLMProvider):
    """Universal OpenAI-compatible provider adapter for OmniRoute and OpenAI BYOK."""

    def __init__(self, name: str = "omniroute", default_base_url: Optional[str] = None):
        self._name = name
        self._default_base_url = default_base_url

    @property
    def provider_name(self) -> str:
        return self._name

    def _resolve_base_url(self, config: LLMConfig) -> str:
        raw_url = ""
        if config.base_url:
            raw_url = config.base_url
        elif self._default_base_url:
            raw_url = self._default_base_url
        elif self._name == "omniroute":
            raw_url = os.environ.get("LLM_BASE_URL", "http://localhost:20128/v1")
        else:
            raw_url = "https://api.openai.com/v1"

        return validate_provider_endpoint(raw_url, allow_local=True)

    def _resolve_api_key(self, config: LLMConfig) -> str:
        if config.api_key:
            return config.api_key
        if self._name == "omniroute":
            return os.environ.get("OMNIROUTE_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
        return os.environ.get("OPENAI_API_KEY", "")

    async def generate(self, messages: list[LLMMessage], config: LLMConfig) -> LLMResponse:
        base_url = self._resolve_base_url(config)
        api_key = self._resolve_api_key(config)
        url = f"{base_url}/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        payload = {
            "model": config.model or "auto",
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "stream": False,
        }

        timeout = httpx.Timeout(connect=10.0, read=config.timeout_seconds, write=10.0, pool=10.0)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code != 200:
                    self._handle_http_error(resp.status_code, resp.text)

                data = resp.json()
                choice = data["choices"][0]
                content = choice["message"]["content"] or ""
                usage = data.get("usage", {})

                return LLMResponse(
                    content=content,
                    model=data.get("model", config.model),
                    tokens_used={
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                        "total_tokens": usage.get("total_tokens", 0),
                    },
                    finish_reason=choice.get("finish_reason", "stop"),
                    raw_response=data,
                )
        except httpx.ConnectTimeout as e:
            raise LLMTimeoutError(f"Connection to provider '{self._name}' timed out") from e
        except httpx.ReadTimeout as e:
            raise LLMTimeoutError(f"Read from provider '{self._name}' timed out after {config.timeout_seconds}s") from e
        except httpx.ConnectError as e:
            raise LLMConnectionError(f"Failed to connect to provider '{self._name}' at endpoint") from e

    async def generate_stream(
        self, messages: list[LLMMessage], config: LLMConfig
    ) -> AsyncIterator[LLMStreamChunk]:
        base_url = self._resolve_base_url(config)
        api_key = self._resolve_api_key(config)
        url = f"{base_url}/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        payload = {
            "model": config.model or "auto",
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "stream": True,
        }

        timeout = httpx.Timeout(connect=10.0, read=config.timeout_seconds, write=10.0, pool=10.0)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as resp:
                    if resp.status_code != 200:
                        err_body = await resp.aread()
                        self._handle_http_error(resp.status_code, err_body.decode(errors="replace"))

                    async for line in resp.aiter_lines():
                        line = line.strip()
                        if not line:
                            continue
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk_data = json.loads(data_str)
                                choice = chunk_data["choices"][0]
                                delta = choice.get("delta", {})
                                content_delta = delta.get("content", "")
                                finish_reason = choice.get("finish_reason")
                                if content_delta or finish_reason:
                                    yield LLMStreamChunk(
                                        content_delta=content_delta,
                                        finish_reason=finish_reason,
                                    )
                            except json.JSONDecodeError:
                                continue
        except httpx.ConnectTimeout as e:
            raise LLMTimeoutError(f"Connection to provider '{self._name}' timed out") from e
        except httpx.ReadTimeout as e:
            raise LLMTimeoutError(f"Read from provider '{self._name}' timed out after {config.timeout_seconds}s") from e
        except httpx.ConnectError as e:
            raise LLMConnectionError(f"Failed to connect to provider '{self._name}' at endpoint") from e

    def _handle_http_error(self, status_code: int, err_text: str):
        """Map HTTP error status codes to normalized LLM exceptions."""
        logger.error(f"Provider '{self._name}' returned HTTP {status_code}")
        if status_code in (401, 403):
            raise LLMAuthenticationError(f"Authentication failed with provider '{self._name}' (HTTP {status_code})")
        if status_code == 429:
            raise LLMRateLimitError(f"Rate limit exceeded on provider '{self._name}' (HTTP 429)")
        if status_code == 404:
            raise LLMProviderError(f"Provider '{self._name}' endpoint not found (HTTP 404)")
        raise LLMProviderError(f"Provider '{self._name}' server error (HTTP {status_code})")

    async def validate_key(self, config: LLMConfig) -> bool:
        base_url = self._resolve_base_url(config)
        api_key = self._resolve_api_key(config)
        url = f"{base_url}/models"
        headers = {"Authorization": f"Bearer {api_key}"}

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, headers=headers)
                return resp.status_code == 200
        except Exception as e:
            logger.warning(f"Failed to validate LLM credentials: {e}")
            return False

