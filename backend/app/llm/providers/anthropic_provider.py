"""Anthropic Claude Messages API Provider Adapter."""

import json
import logging
import os
from collections.abc import AsyncIterator
from typing import Optional

import httpx

from app.llm.base import (
    LLMAuthenticationError,
    LLMConfig,
    LLMConnectionError,
    LLMMessage,
    LLMProvider,
    LLMRateLimitError,
    LLMResponse,
    LLMStreamChunk,
    LLMTimeoutError,
)
from app.llm.endpoint_validation import (
    validate_custom_provider_endpoint,
    validate_provider_endpoint,
)

logger = logging.getLogger("mmaip.llm.anthropic")

ANTHROPIC_DEFAULT_BASE_URL = "https://api.anthropic.com/v1"
ANTHROPIC_API_VERSION = "2023-06-01"


class AnthropicLLMProvider(LLMProvider):
    """Adapter for Anthropic Claude 3.5 Sonnet, Haiku, and Opus models."""

    def __init__(self, default_base_url: str = ANTHROPIC_DEFAULT_BASE_URL):
        self._default_base_url = default_base_url

    @property
    def provider_name(self) -> str:
        return "anthropic"

    def _resolve_api_key(self, config: LLMConfig) -> Optional[str]:
        return config.api_key or os.environ.get("ANTHROPIC_API_KEY")

    def _resolve_base_url(self, config: LLMConfig) -> str:
        if config.base_url:
            return validate_custom_provider_endpoint(config.base_url)
        return validate_provider_endpoint(self._default_base_url, allow_local=False)

    def _format_payload(self, messages: list[LLMMessage], config: LLMConfig, stream: bool = False) -> dict:
        system_parts = []
        anthropic_messages = []

        for m in messages:
            if m.role == "system":
                system_parts.append(m.content)
            else:
                anthropic_messages.append({"role": m.role, "content": m.content})

        # Anthropic requires at least one user message
        if not anthropic_messages:
            anthropic_messages = [{"role": "user", "content": "Hello"}]

        payload = {
            "model": config.model if config.model and config.model != "auto" else "claude-3-5-sonnet-20241022",
            "max_tokens": config.max_tokens or 1024,
            "temperature": config.temperature,
            "messages": anthropic_messages,
            "stream": stream,
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)

        return payload

    def _get_headers(self, api_key: str) -> dict[str, str]:
        return {
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_API_VERSION,
            "content-type": "application/json",
        }

    async def generate(self, messages: list[LLMMessage], config: LLMConfig) -> LLMResponse:
        api_key = self._resolve_api_key(config)
        if not api_key:
            raise LLMAuthenticationError("Anthropic API key is required but not configured.")

        base_url = self._resolve_base_url(config)
        url = f"{base_url.rstrip('/')}/messages"
        headers = self._get_headers(api_key)
        payload = self._format_payload(messages, config, stream=False)

        try:
            async with httpx.AsyncClient(timeout=config.timeout_seconds, follow_redirects=False) as client:
                resp = await client.post(url, headers=headers, json=payload)

            if resp.status_code == 401 or resp.status_code == 403:
                raise LLMAuthenticationError("Anthropic authentication failed. Invalid API key.")
            elif resp.status_code == 429:
                raise LLMRateLimitError("Anthropic rate limit exceeded. Please back off.")
            elif resp.status_code >= 500:
                raise LLMConnectionError(f"Anthropic server error (HTTP {resp.status_code})")
            elif not resp.is_success:
                raise LLMConnectionError(f"Anthropic returned HTTP {resp.status_code}: {resp.text}")

            data = resp.json()
            # Extract content from Claude response: content blocks
            content = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    content += block.get("text", "")

            usage = data.get("usage", {})
            tokens_used = {
                "prompt_tokens": usage.get("input_tokens", 0),
                "completion_tokens": usage.get("output_tokens", 0),
                "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            }

            return LLMResponse(
                content=content,
                model=data.get("model", config.model),
                tokens_used=tokens_used,
                finish_reason=data.get("stop_reason", "stop"),
                raw_response=data,
            )

        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"Anthropic request timed out after {config.timeout_seconds}s") from exc
        except httpx.ConnectError as exc:
            raise LLMConnectionError(f"Failed to connect to Anthropic endpoint: {exc}") from exc

    async def generate_stream(
        self, messages: list[LLMMessage], config: LLMConfig
    ) -> AsyncIterator[LLMStreamChunk]:
        api_key = self._resolve_api_key(config)
        if not api_key:
            raise LLMAuthenticationError("Anthropic API key is required but not configured.")

        base_url = self._resolve_base_url(config)
        url = f"{base_url.rstrip('/')}/messages"
        headers = self._get_headers(api_key)
        payload = self._format_payload(messages, config, stream=True)

        try:
            async with httpx.AsyncClient(timeout=config.timeout_seconds, follow_redirects=False) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as resp:
                    if resp.status_code == 401 or resp.status_code == 403:
                        raise LLMAuthenticationError("Anthropic authentication failed. Invalid API key.")
                    elif resp.status_code == 429:
                        raise LLMRateLimitError("Anthropic rate limit exceeded.")
                    elif not resp.is_success:
                        err_text = await resp.aread()
                        raise LLMConnectionError(f"Anthropic streaming failed: HTTP {resp.status_code} - {err_text.decode('utf-8', errors='ignore')}")

                    async for line in resp.aiter_lines():
                        line = line.strip()
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[len("data: "):]
                        if data_str == "[DONE]":
                            break

                        try:
                            event_data = json.loads(data_str)
                            event_type = event_data.get("type")
                            if event_type == "content_block_delta":
                                delta = event_data.get("delta", {})
                                if delta.get("type") == "text_delta":
                                    yield LLMStreamChunk(content_delta=delta.get("text", ""))
                            elif event_type == "message_delta":
                                stop_reason = event_data.get("delta", {}).get("stop_reason")
                                if stop_reason:
                                    yield LLMStreamChunk(content_delta="", finish_reason=stop_reason)
                        except json.JSONDecodeError:
                            continue

        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"Anthropic streaming timed out after {config.timeout_seconds}s") from exc
        except httpx.ConnectError as exc:
            raise LLMConnectionError(f"Failed to connect to Anthropic streaming endpoint: {exc}") from exc

    async def validate_key(self, config: LLMConfig) -> bool:
        """Validate Anthropic API key via lightweight messages request."""
        api_key = self._resolve_api_key(config)
        if not api_key:
            return False
        base_url = self._resolve_base_url(config)
        url = f"{base_url.rstrip('/')}/messages"
        headers = self._get_headers(api_key)
        test_payload = {
            "model": "claude-3-5-haiku-20241022",
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "ping"}],
        }

        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
                res = await client.post(url, headers=headers, json=test_payload)
                return res.status_code == 200
        except Exception as exc:
            logger.warning(f"Anthropic key validation network failure: {exc}")
            return False
