# Retrieval Playground Architecture (M07)

## Design Principles
The Retrieval Playground provides an interactive testing sandbox that executes the real production retrieval pipeline without mock scoring.

### API Contract: `POST /api/v1/retrieval/playground`

#### Request Payload:
```json
{
  "knowledge_base_id": "uuid",
  "query": "string (1-1000 chars)",
  "mode": "hybrid | semantic | lexical",
  "top_k": 5,
  "similarity_threshold": 0.5
}
```

#### Response Structure:
```json
{
  "query": "...",
  "knowledge_base_id": "uuid",
  "retrieval_mode": "hybrid",
  "vector_store": "fts | pgvector | qdrant",
  "latency_ms": 14.8,
  "total_results": 3,
  "results": [
    {
      "chunk_id": "uuid",
      "document_id": "uuid",
      "document_title": "Handbook.pdf",
      "rank": 1,
      "sparse_score": 0.082,
      "dense_score": 0.892,
      "score": 0.942,
      "retrieval_source": "hybrid",
      "content": "...",
      "page_number": 2,
      "heading_path": "Chapter 2 > Policy"
    }
  ]
}
```

### Truthful Score Reporting
- Sparse score: PostgreSQL `ts_rank_cd` full-text search score.
- Dense score: Vector cosine similarity score.
- Reciprocal Rank Fusion: Combined rank score according to RRF standard formula:
  $$\text{RRF Score} = \sum_{m \in M} \frac{1}{k + \text{rank}_m}$$
- Latency: Exact measurement in milliseconds via `time.perf_counter()`.
