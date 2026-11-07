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
        content = self._synthesize_response(messages)
        words = content.split(" ")
        for i, word in enumerate(words):
            token = word + (" " if i < len(words) - 1 else "")
            yield LLMStreamChunk(content_delta=token)
            await asyncio.sleep(0.01)  # Simulate small stream delay

        yield LLMStreamChunk(content_delta="", finish_reason="stop")

    async def validate_key(self, config: LLMConfig) -> bool:
        return True
