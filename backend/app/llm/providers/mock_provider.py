"""Mock LLM Provider for deterministic offline testing and end-to-end RAG verification."""

import asyncio
from collections.abc import AsyncIterator

from app.llm.base import (
    LLMConfig,
    LLMMessage,
    LLMProvider,
    LLMResponse,
    LLMStreamChunk,
)


class MockLLMProvider(LLMProvider):
    """Deterministic offline LLM provider simulating streaming generation and citation generation."""

    def __init__(self, name: str = "mock"):
        self._name = name

    @property
    def provider_name(self) -> str:
        return self._name

    def _synthesize_response(self, messages: list[LLMMessage]) -> str:
        tool_results = [m for m in messages if m.role == "tool"]
        if tool_results:
            return f"The tool execution result is: {tool_results[-1].content}. Based on this result, your request has been processed successfully."

        # Check if knowledge context was injected in messages
        system_content = next((m.content for m in messages if m.role == "system"), "")
        user_content = next((m.content for m in reversed(messages) if m.role == "user"), "")

        if (
            "<KNOWLEDGE_BASE_CONTEXT>" in system_content
            or "KNOWLEDGE BASE CONTEXT" in system_content
            or "Retrieved Sources" in system_content
        ):
            return (
                f"Based on the provided documentation, {user_content.rstrip('?')} is explicitly "
                "supported by verified internal policy [1]. Please refer to the cited documentation for full details."
            )
        else:
            return (
                f"I understand your inquiry regarding '{user_content}'. However, no relevant internal "
                "knowledge sources were found in the connected knowledge bases to ground this specific answer."
            )

    async def generate(self, messages: list[LLMMessage], config: LLMConfig) -> LLMResponse:
        content = self._synthesize_response(messages)
        return LLMResponse(
            content=content,
            model=config.model or "mock-gpt",
            tokens_used={
                "prompt_tokens": sum(len(m.content.split()) for m in messages),
                "completion_tokens": len(content.split()),
                "total_tokens": sum(len(m.content.split()) for m in messages) + len(content.split()),
            },
            finish_reason="stop",
        )

    async def generate_stream(
        self, messages: list[LLMMessage], config: LLMConfig
    ) -> AsyncIterator[LLMStreamChunk]:
        user_content = next((m.content for m in reversed(messages) if m.role == "user"), "")
        tool_results = [m for m in messages if m.role == "tool"]

        # Deterministic Tool Calling simulation when tools are configured and haven't run yet
        if config.tools and not tool_results:
            tool_names = [t.get("name") for t in config.tools]
            if "calculator" in tool_names and any(op in user_content for op in ("+", "-", "*", "/", "calculate", "calc")):
                yield LLMStreamChunk(
                    content_delta="",
                    finish_reason="tool_calls",
                    tool_calls=[{
                        "id": "call_mock_calc",
                        "name": "calculator",
                        "arguments": {"expression": "25 * 4"},
                    }],
                )
                return
            elif "weather_lookup" in tool_names and ("weather" in user_content.lower() or "temperature" in user_content.lower()):
                city = "Tokyo" if "tokyo" in user_content.lower() else "San Francisco"
                yield LLMStreamChunk(
                    content_delta="",
                    finish_reason="tool_calls",
                    tool_calls=[{
                        "id": "call_mock_weather",
                        "name": "weather_lookup",
                        "arguments": {"city": city},
                    }],
                )
                return
            elif any(kw in user_content.lower() for kw in ("action", "transfer", "ticket", "send", "mutate", "delete", "tool")):
                matching_tool = next(
                    (name for name in tool_names if name in user_content.lower() or any(p in user_content.lower() for p in name.split("_") if len(p) > 2)),
                    tool_names[-1] if tool_names else "generic_tool",
                )
                yield LLMStreamChunk(
                    content_delta="",
                    finish_reason="tool_calls",
                    tool_calls=[{
                        "id": "call_mock_action",
                        "name": matching_tool,
                        "arguments": {"action": "execute", "details": user_content},
                    }],
                )
                return


        content = self._synthesize_response(messages)
        words = content.split(" ")
        for i, word in enumerate(words):
            token = word + (" " if i < len(words) - 1 else "")
            yield LLMStreamChunk(content_delta=token)
            await asyncio.sleep(0.01)  # Simulate small stream delay

        yield LLMStreamChunk(content_delta="", finish_reason="stop")


    async def validate_key(self, config: LLMConfig) -> bool:
        return True
