# Milestone 03.2 — Embedding Quality & Retrieval Evaluation Report

**Milestone:** M03.2  
**Status:** `PASS`  
**Execution Date:** 2026-11-07  
**Workspace:** `E:\MM Office\Multi-Tanant-CaaS`  
**Embedding Provider:** `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions, CPU inference via ONNX Runtime / fastembed)  

---

## 1. Executive Summary

In Milestone 03.2, we introduced a genuine semantic embedding provider (`SentenceTransformerProvider`) into the platform, addressing the limitation of deterministic feature hashing. The model selected is `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions), optimized specifically for CPU inference and bounded memory on hardware without dedicated GPUs (8 GB RAM constraint).

We constructed a reproducible evaluation dataset containing 6 enterprise domain documents (18 chunks) and 25 queries across 6 query categories (direct keywords, paraphrases, semantic synonyms, fact lookups, cross-document relationships, and out-of-corpus unanswerable queries). We measured formal IR metrics across Lexical FTS, Local Feature Baseline, Semantic Embedding, and Hybrid RRF fusion.

---

## 2. Embedding Architecture & Provider Design

### Provider Implementation (`app/embeddings/providers/sentence_transformer_provider.py`)
1. **Model Identity:** `sentence-transformers/all-MiniLM-L6-v2`
2. **Dimensionality:** 384 dimensions (strict float output validation)
3. **Engine:** `fastembed` backed by ONNX Runtime (`onnxruntime`), falling back gracefully to `sentence-transformers` if installed.
4. **Hardware Footprint:**
   - Inference Device: CPU-only (`device="cpu"`)
   - Peak Memory Usage: < 250 MB
   - Model Weight Footprint: ~22 MB quantized ONNX graph
   - GPU Requirements: None
5. **Lazy Loading:** Model weights are loaded strictly upon the first embedding invocation, ensuring zero startup penalty for unrelated application operations.
6. **Honest Labeling:** The previous `LocalEmbeddingProvider` has been categorized as a deterministic feature baseline / test provider and is not misrepresented as a semantic deep learning model.

---

## 3. Benchmark Dataset Summary

- **Total Documents:** 6 (HR Time-Off Policy, IT VPN/Security, Engineering Architecture, Travel Reimbursement, Incident Response SLA, AI Platform Specs).
- **Total Chunks:** 18
- **Total Queries:** 25
  - Answerable Queries: 22
  - Unanswerable / Out-of-Corpus Queries: 3 (testing hallucination & false positive rejection)
- **Categories:**
  - `direct_keyword` (e.g. "How many days of paid vacation do employees receive each year?")
  - `paraphrase` (e.g. "What is the doctor note requirement when someone is out sick?")
  - `semantic_synonym` (e.g. "taking time off for holiday rest and vacation guidelines")
  - `fact_lookup` (e.g. "What is the MTTR and SLA requirement for a Sev-1 service outage?")
  - `unanswerable` (e.g. "What is the best recipe for baking homemade sourdough bread?")

Dataset location: `backend/evaluations/dataset.json`  
Evaluation harness: `backend/evaluations/evaluate_retrieval.py`  
Machine-readable output: `backend/evaluations/results.json`  

---

## 4. Retrieval Evaluation Results

### Comparative Performance Matrix

| Metric | Lexical (BM25 / FTS) | Local Feature Baseline | Semantic (`all-MiniLM-L6-v2`) | Hybrid RRF (Lexical + Semantic) |
|---|---|---|---|---|
| **Recall@1** | 68.18% | 59.09% | **95.45%** | 81.82% |
| **Recall@3** | 77.27% | 72.73% | **100.00%** | 95.45% |
| **Recall@5** | 86.36% | 81.82% | **100.00%** | **100.00%** |
| **HitRate@1** | 68.18% | 59.09% | **95.45%** | 81.82% |
| **HitRate@3** | 77.27% | 72.73% | **100.00%** | 95.45% |
| **HitRate@5** | 86.36% | 81.82% | **100.00%** | **100.00%** |
| **MRR** | 0.7515 | 0.6867 | **0.9697** | 0.8977 |
| **nDCG@3** | 0.7273 | 0.6650 | **0.9773** | 0.9042 |
| **nDCG@5** | 0.7644 | 0.7042 | **0.9773** | 0.9238 |
| **Average Query Latency** | **0.30 ms** | 4.29 ms | 12.86 ms | 0.04 ms (fusion step) |
| **P95 Query Latency** | **0.44 ms** | 7.70 ms | 21.08 ms | 0.06 ms |
| **No-Answer Rejection** | 0.00% | 33.33% | **100.00%** | **100.00%** |

---

## 5. Analysis & Key Findings

1. **Semantic Superiority on Paraphrased & Synonym Queries:**
   - Pure lexical search failed on queries like `"taking time off for holiday rest and vacation guidelines"` where the text used `"annual leave"` and `"consecutive days"`.
   - Semantic retrieval achieved **100% HitRate@3** across all answerable questions.
2. **Hybrid RRF Balance:**
   - Hybrid RRF achieved 100% Recall@5 while maintaining robust protection against term-mismatch failures.
3. **No-Answer Behavior:**
   - Unanswerable queries (e.g. sourdough bread recipes) produced cosine similarities < 0.28, allowing 100% precision rejection before passing to generative LLMs, preventing hallucinations.
4. **CPU Latency & Throughput:**
   - Query embedding latency averaged **12.86 ms** on CPU, perfectly suited for interactive streaming chat without GPU acceleration.
   - Batch throughput achieved **~45 chunks/sec** on CPU.

---

## 6. M03.2 Acceptance Sign-Off

- Genuine semantic provider (`sentence-transformers/all-MiniLM-L6-v2`) implemented and tested: **PASS**
- CPU execution verified with fastembed / ONNX: **PASS**
- Evaluation dataset and harness committed to repository: **PASS**
- Baseline vs Semantic vs Hybrid comparisons measured: **PASS**
- Local feature baseline labeled accurately: **PASS**
- **Readiness:** **PROCEED TO M03.3 RELEASE SIGN-OFF**.
