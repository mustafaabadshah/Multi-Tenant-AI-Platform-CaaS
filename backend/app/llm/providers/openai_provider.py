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
    LLMProviderError,
    LLMRateLimitError,
    LLMResponse,
    LLMStreamChunk,
    LLMTimeoutError,
)
from app.llm.endpoint_validation import (
    validate_custom_provider_endpoint,
    validate_provider_endpoint,
)

logger = logging.getLogger("mmaip.llm.openai")


class OpenAICompatibleLLMProvider(LLMProvider):
    """Universal OpenAI-compatible provider adapter for OmniRoute, Groq, and OpenAI BYOK."""

    def __init__(
        self,
        name: str = "omniroute",
        default_base_url: Optional[str] = None,
        default_api_key_env: Optional[str] = None,
    ):
        self._name = name
        self._default_base_url = default_base_url
        self._default_api_key_env = default_api_key_env

    @property
    def provider_name(self) -> str:
        return self._name

    def _resolve_base_url(self, config: LLMConfig) -> str:
        # Tenant/BYOK supplied URLs never get localhost privileges and must
        # pass the custom-endpoint feature gate.
        if config.base_url:
            return validate_custom_provider_endpoint(config.base_url)

        # OmniRoute is the operator-controlled built-in gateway. Only this
        # provider may use a loopback/private operator-configured endpoint.
        if self._name == "omniroute":
            raw_url = (
                self._default_base_url
                or os.environ.get("LLM_BASE_URL")
                or "http://localhost:20128/v1"
            )
            return validate_provider_endpoint(raw_url, allow_local=True)

        if self._default_base_url:
            return validate_provider_endpoint(self._default_base_url, allow_local=False)
        if self._name == "groq":
            return validate_provider_endpoint(
                "https://api.groq.com/openai/v1", allow_local=False
            )
        return validate_provider_endpoint("https://api.openai.com/v1", allow_local=False)

    def _resolve_api_key(self, config: LLMConfig) -> str:
        if config.api_key:
            return config.api_key
        if self._default_api_key_env:
            env_val = os.environ.get(self._default_api_key_env)
            if env_val:
                return env_val
        if self._name == "omniroute":
            return os.environ.get("OMNIROUTE_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
        return os.environ.get("OPENAI_API_KEY", "")

    async def generate(self, messages: list[LLMMessage], config: LLMConfig) -> LLMResponse:
        api_key = self._resolve_api_key(config)
        if not api_key:
            raise LLMAuthenticationError(f"No API key configured for provider '{self._name}'. Please configure your BYOK key or environment credentials.")
        base_url = self._resolve_base_url(config)
        url = f"{base_url}/chat/completions"

        extra_h = getattr(config, "extra_headers", {}) or {}
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            **extra_h,
        }
        payload = {
            "model": config.model or "auto",
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "stream": False,
        }
        if config.tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.get("name"),
                        "description": t.get("description") or "",
                        "parameters": t.get("input_schema") or {"type": "object", "properties": {}},
                    },
                }
                for t in config.tools
            ]

        timeout = httpx.Timeout(connect=10.0, read=config.timeout_seconds, write=10.0, pool=10.0)
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code != 200:
                    self._handle_http_error(resp.status_code, resp.text)

                data = resp.json()
                choice = data["choices"][0]
                content = choice["message"].get("content") or ""
                usage = data.get("usage", {})

                tool_calls = None
                raw_tc = choice["message"].get("tool_calls")
                if raw_tc:
                    tool_calls = []
                    for t in raw_tc:
                        fn = t.get("function", {})
                        try:
                            args = json.loads(fn.get("arguments", "{}"))
                        except Exception:
                            args = {"raw": fn.get("arguments", "")}
                        tool_calls.append({
                            "id": t.get("id"),
                            "name": fn.get("name"),
                            "arguments": args,
                        })

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
                    tool_calls=tool_calls,
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
        api_key = self._resolve_api_key(config)
        if not api_key:
            raise LLMAuthenticationError(f"No API key configured for provider '{self._name}'. Please configure your BYOK key or environment credentials.")
        base_url = self._resolve_base_url(config)
        url = f"{base_url}/chat/completions"

        extra_h = getattr(config, "extra_headers", {}) or {}
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            **extra_h,
        }
        payload = {
            "model": config.model or "auto",
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "stream": True,
        }
        if config.tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.get("name"),
                        "description": t.get("description") or "",
                        "parameters": t.get("input_schema") or {"type": "object", "properties": {}},
                    },
                }
                for t in config.tools
            ]

        timeout = httpx.Timeout(connect=10.0, read=config.timeout_seconds, write=10.0, pool=10.0)
        accumulated_tool_calls: dict[int, dict[str, Any]] = {}

        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
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

                                raw_tool_calls = delta.get("tool_calls")
                                if raw_tool_calls:
                                    for tc_chunk in raw_tool_calls:
                                        idx = tc_chunk.get("index", 0)
                                        if idx not in accumulated_tool_calls:
                                            accumulated_tool_calls[idx] = {
                                                "id": tc_chunk.get("id", f"call_{idx}"),
                                                "name": tc_chunk.get("function", {}).get("name", ""),
                                                "arguments_str": "",
                                            }
                                        fn = tc_chunk.get("function", {})
                                        if fn.get("name"):
                                            accumulated_tool_calls[idx]["name"] = fn["name"]
                                        if fn.get("arguments"):
                                            accumulated_tool_calls[idx]["arguments_str"] += fn["arguments"]

                                finish_reason = choice.get("finish_reason")
                                parsed_tool_calls = None
                                if finish_reason == "tool_calls" or (finish_reason and accumulated_tool_calls):
                                    parsed_tool_calls = []
                                    for idx, tc in sorted(accumulated_tool_calls.items()):
                                        try:
                                            parsed_args = json.loads(tc["arguments_str"]) if tc["arguments_str"] else {}
                                        except json.JSONDecodeError:
                                            parsed_args = {"raw": tc["arguments_str"]}
                                        parsed_tool_calls.append({
                                            "id": tc["id"],
                                            "name": tc["name"],
                                            "arguments": parsed_args,
                                        })

                                if content_delta or finish_reason or parsed_tool_calls:
                                    yield LLMStreamChunk(
                                        content_delta=content_delta,
                                        finish_reason=finish_reason,
                                        tool_calls=parsed_tool_calls,
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
        detail = ""
        try:
            parsed = json.loads(err_text)
            if isinstance(parsed, dict) and "error" in parsed:
                err_obj = parsed["error"]
                if isinstance(err_obj, dict) and "message" in err_obj:
                    detail = f": {err_obj['message']}"
                elif isinstance(err_obj, str):
                    detail = f": {err_obj}"
            elif isinstance(parsed, dict) and "detail" in parsed:
                detail = f": {parsed['detail']}"
        except Exception:
            if err_text:
                detail = f": {err_text[:200]}"

        logger.error(f"Provider '{self._name}' returned HTTP {status_code}{detail}")
        if status_code in (401, 403):
            raise LLMAuthenticationError(f"Authentication failed with provider '{self._name}' (HTTP {status_code}){detail}")
        if status_code == 429:
            raise LLMRateLimitError(f"Rate limit exceeded on provider '{self._name}' (HTTP 429){detail}")
        if status_code == 404:
            raise LLMProviderError(f"Provider '{self._name}' error (HTTP 404){detail or ' endpoint or model not found'}")
        raise LLMProviderError(f"Provider '{self._name}' server error (HTTP {status_code}){detail}")

    async def validate_key(self, config: LLMConfig) -> bool:
        api_key = self._resolve_api_key(config)
        if not api_key:
            return False
        base_url = self._resolve_base_url(config)
        url = f"{base_url}/models"
        headers = {"Authorization": f"Bearer {api_key}"}

        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
                resp = await client.get(url, headers=headers)
                return resp.status_code == 200
        except Exception as e:
            logger.warning(f"Failed to validate LLM credentials: {e}")
            return False

