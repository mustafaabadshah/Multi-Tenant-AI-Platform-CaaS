import json
import logging
import os
from collections.abc import AsyncIterator
from typing import Any, Optional

import httpx

from app.llm.base import (
    LLMAuthenticationError,
    LLMConfig,
    LLMConnectionError,
    LLMMessage,
    LLMModelUnavailableError,
    LLMProvider,
    LLMProviderError,
    LLMRateLimitError,
    LLMResponse,
    LLMResponseInvalidError,
    LLMStreamChunk,
    LLMStreamInterruptedError,
    LLMTimeoutError,
    LLMToolCallUnsupportedError,
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

    def _format_messages_payload(self, messages: list[LLMMessage]) -> list[dict[str, Any]]:
        formatted: list[dict[str, Any]] = []
        for m in messages:
            msg: dict[str, Any] = {"role": m.role, "content": m.content}
            if getattr(m, "tool_call_id", None):
                msg["tool_call_id"] = m.tool_call_id
            if getattr(m, "tool_calls", None):
                msg["tool_calls"] = m.tool_calls
            formatted.append(msg)
        return formatted

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
            "messages": self._format_messages_payload(messages),
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
            payload["tool_choice"] = getattr(config, "tool_choice", None) or "auto"

        timeout = httpx.Timeout(connect=10.0, read=config.timeout_seconds, write=10.0, pool=10.0)
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code != 200:
                    self._handle_http_error(resp.status_code, resp.text, headers=resp.headers, model=config.model)

                try:
                    data = resp.json()
                except Exception as json_err:
                    raise LLMResponseInvalidError(
                        f"Provider '{self._name}' returned invalid non-JSON body: {resp.text[:200]}"
                    ) from json_err

                if not isinstance(data, dict):
                    raise LLMResponseInvalidError(
                        f"Provider '{self._name}' returned non-object JSON payload: {type(data).__name__}"
                    )

                if "error" in data:
                    err_obj = data["error"]
                    err_msg = err_obj.get("message") if isinstance(err_obj, dict) else str(err_obj)
                    raise LLMResponseInvalidError(f"Provider '{self._name}' returned error payload: {err_msg}")

                choices = data.get("choices")
                if not isinstance(choices, list) or len(choices) == 0:
                    raise LLMResponseInvalidError(
                        f"Provider '{self._name}' response missing or empty 'choices' list"
                    )

                choice = choices[0]
                if not isinstance(choice, dict):
                    raise LLMResponseInvalidError(
                        f"Provider '{self._name}' returned malformed choice element"
                    )

                message = choice.get("message") or {}
                content = message.get("content") or ""
                usage = data.get("usage") or {}

                tool_calls = None
                raw_tc = message.get("tool_calls")
                if raw_tc and isinstance(raw_tc, list):
                    tool_calls = []
                    for t in raw_tc:
                        if not isinstance(t, dict):
                            continue
                        fn = t.get("function") or {}
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
                        "prompt_tokens": usage.get("prompt_tokens", 0) if isinstance(usage, dict) else 0,
                        "completion_tokens": usage.get("completion_tokens", 0) if isinstance(usage, dict) else 0,
                        "total_tokens": usage.get("total_tokens", 0) if isinstance(usage, dict) else 0,
                    },
                    finish_reason=choice.get("finish_reason", "stop") or "stop",
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
            "messages": self._format_messages_payload(messages),
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
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
            payload["tool_choice"] = getattr(config, "tool_choice", None) or "auto"

        timeout = httpx.Timeout(connect=10.0, read=config.timeout_seconds, write=10.0, pool=10.0)
        accumulated_tool_calls: dict[int, dict[str, Any]] = {}

        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as resp:
                    if resp.status_code != 200:
                        err_body = await resp.aread()
                        self._handle_http_error(
                            resp.status_code,
                            err_body.decode(errors="replace"),
                            headers=resp.headers,
                            model=config.model,
                        )

                    async for line in resp.aiter_lines():
                        line = line.strip()
                        if not line:
                            continue
                        if line.startswith("data:"):
                            data_str = line[5:].strip()
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk_data = json.loads(data_str)
                            except json.JSONDecodeError:
                                continue

                            if not isinstance(chunk_data, dict):
                                continue

                            # Detect mid-stream error events emitted by provider
                            if "error" in chunk_data:
                                err_obj = chunk_data["error"]
                                err_msg = err_obj.get("message") if isinstance(err_obj, dict) else str(err_obj)
                                msg_lower = err_msg.lower()
                                if (
                                    "tool choice is none" in msg_lower
                                    or "tool_use_failed" in msg_lower
                                    or ("tool" in msg_lower and ("not supported" in msg_lower or "unsupported" in msg_lower or "conflict" in msg_lower or "invalid" in msg_lower or "choice" in msg_lower))
                                ):
                                    raise LLMToolCallUnsupportedError(
                                        f"Provider '{self._name}' stream error: {err_msg}"
                                    )
                                raise LLMStreamInterruptedError(
                                    f"Provider '{self._name}' stream error: {err_msg}"
                                )

                            # Capture provider-reported actual token usage if available
                            reported_usage = None
                            if "usage" in chunk_data and isinstance(chunk_data["usage"], dict):
                                u = chunk_data["usage"]
                                reported_usage = {
                                    "prompt_tokens": u.get("prompt_tokens"),
                                    "completion_tokens": u.get("completion_tokens"),
                                    "total_tokens": u.get("total_tokens"),
                                }

                            choices = chunk_data.get("choices")
                            if not choices or not isinstance(choices, list) or len(choices) == 0:
                                # Usage-only final chunk from OpenAI/Groq stream_options
                                if reported_usage:
                                    yield LLMStreamChunk(content_delta="", usage=reported_usage)
                                continue

                            choice = choices[0]
                            if not isinstance(choice, dict):
                                continue

                            delta = choice.get("delta") or {}
                            content_delta = delta.get("content") or ""

                            raw_tool_calls = delta.get("tool_calls")
                            if raw_tool_calls and isinstance(raw_tool_calls, list):
                                for tc_chunk in raw_tool_calls:
                                    if not isinstance(tc_chunk, dict):
                                        continue
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

                            if content_delta or finish_reason or parsed_tool_calls or reported_usage:
                                yield LLMStreamChunk(
                                    content_delta=content_delta,
                                    finish_reason=finish_reason,
                                    tool_calls=parsed_tool_calls,
                                    usage=reported_usage,
                                )
        except httpx.ConnectTimeout as e:
            raise LLMTimeoutError(f"Connection to provider '{self._name}' timed out") from e
        except httpx.ReadTimeout as e:
            raise LLMTimeoutError(f"Read from provider '{self._name}' timed out after {config.timeout_seconds}s") from e
        except httpx.ConnectError as e:
            raise LLMConnectionError(f"Failed to connect to provider '{self._name}' at endpoint") from e
        except (httpx.RemoteProtocolError, httpx.StreamError) as e:
            raise LLMStreamInterruptedError(f"Connection to provider '{self._name}' was interrupted mid-stream: {e}") from e

    def _handle_http_error(
        self,
        status_code: int,
        err_text: str,
        headers: Optional[Any] = None,
        model: Optional[str] = None,
    ):
        """Map HTTP error status codes to normalized LLM exceptions with structured metadata."""
        import re

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
        d_lower = detail.lower()

        if status_code in (401, 403):
            raise LLMAuthenticationError(f"Authentication failed with provider '{self._name}' (HTTP {status_code}){detail}")

        if status_code == 429:
            retry_after: Optional[float] = None
            limit_type: Optional[str] = None

            # 1. Attempt extracting from headers (e.g. Retry-After, x-ratelimit-reset-requests, x-ratelimit-reset-tokens)
            if headers:
                raw_ra = headers.get("retry-after") or headers.get("Retry-After")
                if raw_ra:
                    try:
                        retry_after = float(raw_ra)
                    except ValueError:
                        pass
                if not retry_after:
                    raw_reset = headers.get("x-ratelimit-reset-requests") or headers.get("x-ratelimit-reset-tokens")
                    if raw_reset:
                        try:
                            # Format could be seconds or timestamp
                            val = float(raw_reset)
                            if val < 3600:
                                retry_after = val
                        except ValueError:
                            pass

            # 2. Extract from error body message (e.g. Groq "Please try again in 19.9425s" or "try again in 500ms")
            if not retry_after and err_text:
                m_sec = re.search(r"try again in\s+([0-9.]+)\s*s\b", err_text, re.IGNORECASE)
                if m_sec:
                    try:
                        retry_after = float(m_sec.group(1))
                    except ValueError:
                        pass
                else:
                    m_ms = re.search(r"try again in\s+([0-9.]+)\s*ms\b", err_text, re.IGNORECASE)
                    if m_ms:
                        try:
                            retry_after = round(float(m_ms.group(1)) / 1000.0, 3)
                        except ValueError:
                            pass

            # 3. Classify limit type: TPM (tokens per minute) or RPM (requests per minute)
            if "tpm" in d_lower or "token" in d_lower or "tokens per minute" in d_lower:
                limit_type = "TPM"
            elif "rpm" in d_lower or "requests per minute" in d_lower or ("request" in d_lower and "requested" not in d_lower):
                limit_type = "RPM"

            raise LLMRateLimitError(
                f"Rate limit exceeded on provider '{self._name}' (HTTP 429){detail}",
                retry_after=retry_after,
                limit_type=limit_type,
                model=model,
                provider=self._name,
            )

        if "model" in d_lower and ("not found" in d_lower or "does not exist" in d_lower or "unsupported" in d_lower or "invalid" in d_lower):
            raise LLMModelUnavailableError(
                f"Model unavailable on provider '{self._name}' (HTTP {status_code}){detail}",
                model=model,
                provider=self._name,
            )

        if ("tool" in d_lower or "function" in d_lower) and ("not supported" in d_lower or "unsupported" in d_lower or "choice" in d_lower or "none" in d_lower or "failed" in d_lower or "invalid" in d_lower):
            raise LLMToolCallUnsupportedError(f"Tools unsupported or tool choice conflict on provider '{self._name}' (HTTP {status_code}){detail}")

        if status_code == 404:
            raise LLMModelUnavailableError(
                f"Provider '{self._name}' endpoint or model not found (HTTP 404){detail}",
                model=model,
                provider=self._name,
            )

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

