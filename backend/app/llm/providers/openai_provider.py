"""OpenAI-compatible LLM provider adapter supporting OmniRoute gateway and OpenAI BYOK."""

import json
import logging
import os
from collections.abc import AsyncIterator
from typing import Optional

import httpx

from app.core.config import settings
from app.llm.base import (
    LLMConfig,
    LLMMessage,
    LLMProvider,
    LLMResponse,
    LLMStreamChunk,
)

logger = logging.getLogger("mmaip.llm.openai")


class OpenAICompatibleLLMProvider(LLMProvider):
    """Universal OpenAI-compatible provider adapter for OmniRoute and OpenAI BYOK."""

    def __init__(self, name: str = "omniroute", default_base_url: Optional[str] = None):
        self._name = name
        self._default_base_url = default_base_url

    @property
    def provider_name(self) -> str:
        return self._name

    def _resolve_base_url(self, config: LLMConfig) -> str:
        if config.base_url:
            return config.base_url.rstrip("/")
        if self._default_base_url:
            return self._default_base_url.rstrip("/")
        if self._name == "omniroute":
            return os.environ.get("LLM_BASE_URL", "http://localhost:20128/v1").rstrip("/")
        return "https://api.openai.com/v1"

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

        async with httpx.AsyncClient(timeout=config.timeout_seconds) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                logger.error(f"LLM request failed with status {resp.status_code}: {resp.text}")
                raise RuntimeError(f"LLM generation failed: HTTP {resp.status_code}")

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

        async with httpx.AsyncClient(timeout=config.timeout_seconds) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as resp:
                if resp.status_code != 200:
                    err_body = await resp.aread()
                    logger.error(f"Streaming LLM failed with status {resp.status_code}: {err_body.decode()}")
                    raise RuntimeError(f"Streaming LLM failed: HTTP {resp.status_code}")

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
