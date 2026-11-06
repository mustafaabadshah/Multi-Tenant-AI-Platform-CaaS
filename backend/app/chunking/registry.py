"""Registry for chunking strategies."""

from app.chunking.base import ChunkingStrategy
from app.chunking.markdown import MarkdownHeaderChunking
from app.chunking.recursive import RecursiveCharacterChunking
from app.chunking.structured import StructuredDocumentChunking
from app.chunking.token import TokenBoundedChunking


class ChunkingStrategyRegistry:
    """Registry managing configurable chunking strategies."""

    def __init__(self) -> None:
        self._strategies: dict[str, ChunkingStrategy] = {
            "recursive": RecursiveCharacterChunking(),
            "markdown": MarkdownHeaderChunking(),
            "token": TokenBoundedChunking(),
            "structured": StructuredDocumentChunking(),
        }

    def register(self, strategy: ChunkingStrategy) -> None:
        self._strategies[strategy.name.lower()] = strategy

    def get_strategy(self, name: str) -> ChunkingStrategy:
        key = name.lower()
        if key not in self._strategies:
            available = ", ".join(self._strategies.keys())
            raise ValueError(f"Unknown chunking strategy '{name}'. Available strategies: {available}")
        return self._strategies[key]

    def list_strategies(self) -> list[str]:
        return list(self._strategies.keys())


_default_chunking_registry = ChunkingStrategyRegistry()


def get_chunking_registry() -> ChunkingStrategyRegistry:
    return _default_chunking_registry
