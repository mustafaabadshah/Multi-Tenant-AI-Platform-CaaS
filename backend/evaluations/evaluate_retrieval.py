"""Benchmark retrieval evaluation suite measuring Recall@K, Precision@K, MRR, nDCG, and Latency."""

import asyncio
import json
import math
import time
from pathlib import Path
from typing import Any

from app.embeddings.base import EmbeddingProviderConfig
from app.embeddings.providers.local_provider import LocalEmbeddingProvider
from app.embeddings.providers.sentence_transformer_provider import SentenceTransformerProvider


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    dot = sum(a * b for a, b in zip(v1, v2))
    n1 = math.sqrt(sum(a * a for a in v1))
    n2 = math.sqrt(sum(b * b for b in v2))
    if n1 < 1e-9 or n2 < 1e-9:
        return 0.0
    return dot / (n1 * n2)


def bm25_lexical_score(query: str, doc: str) -> float:
    """Lightweight lexical BM25-like scorer for local reproducible evaluation."""
    q_tokens = set(query.lower().split())
    d_tokens = doc.lower().split()
    if not d_tokens or not q_tokens:
        return 0.0
    doc_len = len(d_tokens)
    score = 0.0
    for qt in q_tokens:
        tf = d_tokens.count(qt)
        if tf > 0:
            # BM25 term weighting: (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (doc_len / avg_len)))
            score += (tf * 2.2) / (tf + 1.2 * (0.25 + 0.75 * (doc_len / 35.0)))
    return score


def rrf_fuse(
    lexical_ranked: list[str],
    semantic_ranked: list[str],
    k: int = 60,
) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion combination of lexical and semantic rankings."""
    scores: dict[str, float] = {}
    for rank, chunk_id in enumerate(lexical_ranked):
        scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)
    for rank, chunk_id in enumerate(semantic_ranked):
        scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)

    sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return sorted_results


def calculate_metrics(
    ranked_chunks: list[str],
    relevant_chunks: list[str],
    k_values: list[int] = [1, 3, 5],
) -> dict[str, float]:
    """Calculate Recall@K, Precision@K, MRR, nDCG@K, HitRate@K."""
    if not relevant_chunks:
        return {}

    rel_set = set(relevant_chunks)
    metrics: dict[str, float] = {}

    # MRR
    rr = 0.0
    for idx, cid in enumerate(ranked_chunks):
        if cid in rel_set:
            rr = 1.0 / (idx + 1)
            break
    metrics["mrr"] = rr

    for k in k_values:
        top_k = ranked_chunks[:k]
        hits = sum(1 for cid in top_k if cid in rel_set)

        metrics[f"hit_rate@{k}"] = 1.0 if hits > 0 else 0.0
        metrics[f"recall@{k}"] = hits / len(rel_set)
        metrics[f"precision@{k}"] = hits / k

        # nDCG@K
        dcg = 0.0
        for i, cid in enumerate(top_k):
            rel = 1.0 if cid in rel_set else 0.0
            dcg += rel / math.log2(i + 2)
        idcg = sum(1.0 / math.log2(i + 2) for i in range(min(len(rel_set), k)))
        metrics[f"ndcg@{k}"] = (dcg / idcg) if idcg > 0 else 0.0

    return metrics


async def run_evaluation():
    dataset_path = Path(__file__).parent / "dataset.json"
    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Flatten all chunks
    all_chunks = []
    for doc in data["documents"]:
        for chunk in doc["chunks"]:
            all_chunks.append({
                "id": chunk["id"],
                "doc_id": doc["id"],
                "title": doc["title"],
                "content": chunk["content"],
            })

    print(f"Loaded {len(data['documents'])} documents with {len(all_chunks)} chunks.")
    print(f"Loaded {len(data['queries'])} evaluation queries.")

    # 1. Initialize Embedding Providers
    st_provider = SentenceTransformerProvider()
    st_cfg = EmbeddingProviderConfig(
        provider_name="sentence-transformers",
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        dimensions=384,
    )
    local_provider = LocalEmbeddingProvider()
    local_cfg = EmbeddingProviderConfig(
        provider_name="local",
        model_name="local-feature-projection",
        dimensions=384,
    )

    # Measure chunk embedding throughput
    texts = [c["content"] for c in all_chunks]

    t0 = time.perf_counter()
    st_chunk_embs = await st_provider.embed_batch(texts, st_cfg)
    st_embed_time = time.perf_counter() - t0
    st_throughput = len(texts) / st_embed_time

    local_chunk_embs = await local_provider.embed_batch(texts, local_cfg)

    # Pre-embed map
    chunk_st_vectors = {all_chunks[i]["id"]: st_chunk_embs.embeddings[i] for i in range(len(all_chunks))}
    chunk_local_vectors = {all_chunks[i]["id"]: local_chunk_embs.embeddings[i] for i in range(len(all_chunks))}

    # Evaluation structures
    methods = ["Lexical (BM25/FTS)", "Local Feature Baseline", "Semantic (all-MiniLM-L6-v2)", "Hybrid RRF (Lexical+Semantic)"]
    method_metrics: dict[str, list[dict[str, float]]] = {m: [] for m in methods}
    method_latencies: dict[str, list[float]] = {m: [] for m in methods}
    no_answer_results: dict[str, list[bool]] = {m: [] for m in methods}

    for q in data["queries"]:
        query_text = q["query"]
        relevant = q["relevant_chunk_ids"]
        is_answerable = q["answerable"]

        # Method 1: Lexical (BM25 / FTS)
        t_start = time.perf_counter()
        lexical_scores = [(c["id"], bm25_lexical_score(query_text, c["content"])) for c in all_chunks]
        lexical_sorted = sorted(lexical_scores, key=lambda x: x[1], reverse=True)
        lexical_ranked = [x[0] for x in lexical_sorted]
        method_latencies["Lexical (BM25/FTS)"].append((time.perf_counter() - t_start) * 1000)

        # Method 2: Local Feature Baseline
        t_start = time.perf_counter()
        q_local_emb = await local_provider.embed_text(query_text, local_cfg)
        local_scores = [(c["id"], cosine_similarity(q_local_emb.vector, chunk_local_vectors[c["id"]])) for c in all_chunks]
        local_sorted = sorted(local_scores, key=lambda x: x[1], reverse=True)
        local_ranked = [x[0] for x in local_sorted]
        method_latencies["Local Feature Baseline"].append((time.perf_counter() - t_start) * 1000)

        # Method 3: Semantic (all-MiniLM-L6-v2)
        t_start = time.perf_counter()
        q_st_emb = await st_provider.embed_text(query_text, st_cfg)
        st_scores = [(c["id"], cosine_similarity(q_st_emb.vector, chunk_st_vectors[c["id"]])) for c in all_chunks]
        st_sorted = sorted(st_scores, key=lambda x: x[1], reverse=True)
        st_ranked = [x[0] for x in st_sorted]
        method_latencies["Semantic (all-MiniLM-L6-v2)"].append((time.perf_counter() - t_start) * 1000)

        # Method 4: Hybrid RRF
        t_start = time.perf_counter()
        hybrid_sorted = rrf_fuse(lexical_ranked, st_ranked, k=60)
        hybrid_ranked = [x[0] for x in hybrid_sorted]
        method_latencies["Hybrid RRF (Lexical+Semantic)"].append((time.perf_counter() - t_start) * 1000)

        # Metrics computation
        all_ranked_by_method = {
            "Lexical (BM25/FTS)": (lexical_ranked, lexical_sorted[0][1]),
            "Local Feature Baseline": (local_ranked, local_sorted[0][1]),
            "Semantic (all-MiniLM-L6-v2)": (st_ranked, st_sorted[0][1]),
            "Hybrid RRF (Lexical+Semantic)": (hybrid_ranked, hybrid_sorted[0][1]),
        }

        if is_answerable:
            for m_name in methods:
                ranked, _ = all_ranked_by_method[m_name]
                m = calculate_metrics(ranked, relevant)
                method_metrics[m_name].append(m)
        else:
            # Check no-answer behavior: does the top score stay low?
            # Lexical: top score == 0.0; Semantic: cosine < 0.45; Local: cosine < 0.25
            for m_name in methods:
                _, top_score = all_ranked_by_method[m_name]
                if m_name == "Lexical (BM25/FTS)":
                    no_answer_detected = (top_score < 0.1)
                elif m_name == "Semantic (all-MiniLM-L6-v2)":
                    no_answer_detected = (top_score < 0.40)
                else:
                    no_answer_detected = (top_score < 0.30)
                no_answer_results[m_name].append(no_answer_detected)

    # Aggregate metrics
    summary: dict[str, Any] = {
        "dataset_summary": {
            "num_documents": len(data["documents"]),
            "num_chunks": len(all_chunks),
            "num_queries": len(data["queries"]),
            "answerable_queries": sum(1 for q in data["queries"] if q["answerable"]),
            "unanswerable_queries": sum(1 for q in data["queries"] if not q["answerable"]),
        },
        "performance": {
            "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
            "dimensions": 384,
            "device": "CPU",
            "batch_embed_throughput_chunks_per_sec": round(st_throughput, 2),
            "total_embed_time_sec": round(st_embed_time, 4),
        },
        "methods": {},
    }

    print("\n================== RETRIEVAL EVALUATION RESULTS ==================")
    for m_name in methods:
        metric_list = method_metrics[m_name]
        avg_m: dict[str, float] = {}
        for key in ["hit_rate@1", "hit_rate@3", "hit_rate@5", "recall@1", "recall@3", "recall@5", "precision@1", "precision@3", "precision@5", "mrr", "ndcg@3", "ndcg@5"]:
            vals = [m[key] for m in metric_list if key in m]
            avg_m[key] = round(sum(vals) / len(vals), 4) if vals else 0.0

        latencies = method_latencies[m_name]
        avg_lat = sum(latencies) / len(latencies)
        p95_lat = sorted(latencies)[int(len(latencies) * 0.95)]

        na_vals = no_answer_results[m_name]
        na_acc = (sum(1 for v in na_vals if v) / len(na_vals)) if na_vals else 1.0

        summary["methods"][m_name] = {
            "metrics": avg_m,
            "latency_avg_ms": round(avg_lat, 2),
            "latency_p95_ms": round(p95_lat, 2),
            "no_answer_accuracy": round(na_acc, 2),
        }

        print(f"\n--- {m_name} ---")
        print(f"  Recall@1: {avg_m['recall@1']:.2%} | Recall@3: {avg_m['recall@3']:.2%} | Recall@5: {avg_m['recall@5']:.2%}")
        print(f"  HitRate@1: {avg_m['hit_rate@1']:.2%} | HitRate@3: {avg_m['hit_rate@3']:.2%} | HitRate@5: {avg_m['hit_rate@5']:.2%}")
        print(f"  MRR: {avg_m['mrr']:.4f} | nDCG@3: {avg_m['ndcg@3']:.4f} | nDCG@5: {avg_m['ndcg@5']:.4f}")
        print(f"  Latency Avg: {avg_lat:.2f}ms | Latency P95: {p95_lat:.2f}ms")
        print(f"  No-Answer Rejection Accuracy: {na_acc:.2%}")

    out_file = Path(__file__).parent / "results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"\nResults successfully written to {out_file}")


if __name__ == "__main__":
    asyncio.run(run_evaluation())
