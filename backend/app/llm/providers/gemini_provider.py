"""Google Gemini Generative Language API Provider Adapter."""

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

logger = logging.getLogger("mmaip.llm.gemini")

GEMINI_DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


class GeminiLLMProvider(LLMProvider):
    """Adapter for Google Gemini 1.5 Pro, Flash, and Gemini 2.0 models."""

    def __init__(self, default_base_url: str = GEMINI_DEFAULT_BASE_URL):
        self._default_base_url = default_base_url

    @property
    def provider_name(self) -> str:
        return "gemini"

    def _resolve_api_key(self, config: LLMConfig) -> Optional[str]:
        return config.api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

    def _resolve_model(self, model: str) -> str:
        if not model or model == "auto":
            return "gemini-1.5-flash"
        return model

    def _format_payload(self, messages: list[LLMMessage], config: LLMConfig) -> dict:
        system_text = ""
        contents = []

        for m in messages:
            if m.role == "system":
                system_text += m.content + "\n"
            else:
                role = "user" if m.role == "user" else "model"
                contents.append({"role": role, "parts": [{"text": m.content}]})

        if not contents:
            contents = [{"role": "user", "parts": [{"text": "Hello"}]}]

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": config.temperature,
                "maxOutputTokens": config.max_tokens or 1024,
            },
        }
        if system_text.strip():
            payload["systemInstruction"] = {
                "parts": [{"text": system_text.strip()}]
            }

        return payload

    async def generate(self, messages: list[LLMMessage], config: LLMConfig) -> LLMResponse:
        api_key = self._resolve_api_key(config)
        if not api_key:
            raise LLMAuthenticationError("Gemini API key is required but not configured.")

        model = self._resolve_model(config.model)
        base_url = config.base_url or self._default_base_url
        url = f"{base_url.rstrip('/')}/models/{model}:generateContent"
        headers = {
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        }
        payload = self._format_payload(messages, config)

        try:
            async with httpx.AsyncClient(timeout=config.timeout_seconds) as client:
                resp = await client.post(url, headers=headers, json=payload)

            if resp.status_code in (400, 401, 403):
                err_data = resp.json().catch(lambda: {}) if hasattr(resp, "json") else {}
                err_msg = err_data.get("error", {}).get("message", "Invalid Gemini API key or credentials.")
                raise LLMAuthenticationError(f"Gemini authentication failed: {err_msg}")
            elif resp.status_code == 429:
                raise LLMRateLimitError("Gemini quota or rate limit exceeded.")
            elif not resp.is_success:
                raise LLMConnectionError(f"Gemini error (HTTP {resp.status_code}): {resp.text}")

            data = resp.json()
            candidates = data.get("candidates", [])
            content = ""
            finish_reason = "stop"
            if candidates:
                cand = candidates[0]
                finish_reason = cand.get("finishReason", "stop")
                parts = cand.get("content", {}).get("parts", [])
                content = "".join(p.get("text", "") for p in parts)

            usage = data.get("usageMetadata", {})
            tokens_used = {
                "prompt_tokens": usage.get("promptTokenCount", 0),
                "completion_tokens": usage.get("candidatesTokenCount", 0),
                "total_tokens": usage.get("totalTokenCount", 0),
            }

            return LLMResponse(
                content=content,
                model=model,
                tokens_used=tokens_used,
                finish_reason=finish_reason,
                raw_response=data,
            )

        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"Gemini request timed out after {config.timeout_seconds}s") from exc
        except httpx.ConnectError as exc:
            raise LLMConnectionError(f"Failed to connect to Gemini endpoint: {exc}") from exc

    async def generate_stream(
        self, messages: list[LLMMessage], config: LLMConfig
    ) -> AsyncIterator[LLMStreamChunk]:
        api_key = self._resolve_api_key(config)
        if not api_key:
            raise LLMAuthenticationError("Gemini API key is required but not configured.")

        model = self._resolve_model(config.model)
        base_url = config.base_url or self._default_base_url
        url = f"{base_url.rstrip('/')}/models/{model}:streamGenerateContent?alt=sse"
        headers = {
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        }
        payload = self._format_payload(messages, config)

        try:
            async with httpx.AsyncClient(timeout=config.timeout_seconds) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as resp:
                    if resp.status_code in (401, 403):
                        raise LLMAuthenticationError("Gemini authentication failed. Invalid API key.")
                    elif resp.status_code == 429:
                        raise LLMRateLimitError("Gemini quota or rate limit exceeded.")
                    elif not resp.is_success:
                        err_bytes = await resp.aread()
                        raise LLMConnectionError(f"Gemini streaming failed: HTTP {resp.status_code} - {err_bytes.decode('utf-8', errors='ignore')}")

                    async for line in resp.aiter_lines():
                        line = line.strip()
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[len("data: "):]
                        if data_str == "[DONE]":
                            break

                        try:
                            event_data = json.loads(data_str)
                            candidates = event_data.get("candidates", [])
                            if candidates:
                                parts = candidates[0].get("content", {}).get("parts", [])
                                text_delta = "".join(p.get("text", "") for p in parts)
                                if text_delta:
                                    yield LLMStreamChunk(content_delta=text_delta)
                        except json.JSONDecodeError:
                            continue

        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"Gemini streaming timed out after {config.timeout_seconds}s") from exc
        except httpx.ConnectError as exc:
            raise LLMConnectionError(f"Failed to connect to Gemini streaming endpoint: {exc}") from exc

    async def validate_key(self, config: LLMConfig) -> bool:
        """Validate Gemini API key against /models endpoint."""
        api_key = self._resolve_api_key(config)
        if not api_key:
            return False
        base_url = config.base_url or self._default_base_url
        url = f"{base_url.rstrip('/')}/models"
        headers = {"x-goog-api-key": api_key}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url, headers=headers)
                return res.status_code == 200
        except Exception as exc:
            logger.warning(f"Gemini key validation network failure: {exc}")
            return False
