"""Unit tests for embedding providers, registry, batching, idempotency, and chunk hashing."""

import pytest

from app.embeddings import (
    EmbeddingProviderConfig,
    compute_chunk_content_hash,
    get_embedding_registry,
)
from app.embeddings.providers.local_provider import LocalEmbeddingProvider
from app.embeddings.providers.mock_provider import MockEmbeddingProvider


@pytest.mark.asyncio
async def test_embedding_registry_discovery():
    registry = get_embedding_registry()
    providers = registry.list_providers()
    provider_names = {p["name"] for p in providers}
    assert "omniroute" in provider_names
    assert "mock" in provider_names
    assert "local" in provider_names
    assert "sentence-transformers" in provider_names


@pytest.mark.asyncio
async def test_sentence_transformer_cpu_provider():
    from app.embeddings.providers.sentence_transformer_provider import SentenceTransformerProvider

    provider = SentenceTransformerProvider()
    cfg = EmbeddingProviderConfig(
        provider_name="sentence-transformers",
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        dimensions=384,
    )
    res = await provider.embed_text("Enterprise Multi-Tenant Knowledge Base", cfg)
    assert len(res.vector) == 384
    assert res.dimensions == 384
    assert any(x != 0.0 for x in res.vector)
    # Validate finite values
    assert all(-10.0 <= x <= 10.0 for x in res.vector)

    # Batch embedding test
    batch_res = await provider.embed_batch(
        ["Engineering documentation guidelines", "Human resources onboarding handbook"],
        cfg,
    )
    assert len(batch_res.embeddings) == 2
    assert len(batch_res.embeddings[0]) == 384
    assert len(batch_res.embeddings[1]) == 384



@pytest.mark.asyncio
async def test_mock_embedding_provider_deterministic_dimensions():
    provider = MockEmbeddingProvider()
    cfg_1536 = EmbeddingProviderConfig(provider_name="mock", model_name="mock-embedding-v1", dimensions=1536)
    res_1536 = await provider.embed_text("Antigravity retrieval platform", cfg_1536)
    assert len(res_1536.vector) == 1536
    assert res_1536.dimensions == 1536

    # Test identical input produces identical vectors
    res_duplicate = await provider.embed_text("Antigravity retrieval platform", cfg_1536)
    assert res_1536.vector == res_duplicate.vector

    # Test small dimensions
    cfg_384 = EmbeddingProviderConfig(provider_name="mock", model_name="mock-embedding-small", dimensions=384)
    res_384 = await provider.embed_text("Antigravity retrieval platform", cfg_384)
    assert len(res_384.vector) == 384
    assert res_384.dimensions == 384


@pytest.mark.asyncio
async def test_local_cpu_embedding_provider():
    provider = LocalEmbeddingProvider()
    cfg = EmbeddingProviderConfig(provider_name="local", model_name="local-feature-projection", dimensions=384)
    res = await provider.embed_text("Enterprise Multi-Tenant Knowledge Base", cfg)
    assert len(res.vector) == 384
    # Ensure vector is non-zero
    assert any(x != 0.0 for x in res.vector)


@pytest.mark.asyncio
async def test_batch_embedding_preserves_order():
    provider = MockEmbeddingProvider()
    cfg = EmbeddingProviderConfig(provider_name="mock", model_name="mock-embedding-v1", dimensions=128, batch_size=2)
    texts = [
        "First chunk about engineering",
        "Second chunk about human resources",
        "Third chunk about financial accounting",
    ]
    batch_res = await provider.embed_batch(texts, cfg)
    assert len(batch_res.embeddings) == 3
    assert batch_res.dimensions == 128

    # Verify order matches single calls
    single_0 = await provider.embed_text(texts[0], cfg)
    assert batch_res.embeddings[0] == single_0.vector


def test_chunk_content_hashing_stability():
    text_a = "Policy paragraph 1"
    text_b = "Policy paragraph 2"

    hash_a1 = compute_chunk_content_hash(text_a, "text-embedding-3-small", 1536)
    hash_a2 = compute_chunk_content_hash(text_a, "text-embedding-3-small", 1536)
    hash_b = compute_chunk_content_hash(text_b, "text-embedding-3-small", 1536)
    hash_model_change = compute_chunk_content_hash(text_a, "text-embedding-3-large", 3072)

    # Identical content + model + dims yields identical hash
    assert hash_a1 == hash_a2
    # Distinct content yields distinct hash
    assert hash_a1 != hash_b
    # Model/dimension change invalidates hash
    assert hash_a1 != hash_model_change
