# M05 Phase 3 — Retrieval Quality, Hybrid Ranking & Evaluation Correction Report

**Project:** Multi-Tenant AI Platform / CaaS  
**Workspace:** `E:\MM Office\Multi-Tanant-CaaS`  
**Execution Date:** 2026-11-07  
**Auditor:** Senior Information Retrieval Engineer & RAG Evaluation Researcher  
**Status:** **PASS (Benchmark Reconstructed, Denominator Discrepancy Resolved, Hybrid Regression Diagnosed, Machine-Readable Artifacts Generated)**  
**Recommendation:** **A. SEMANTIC RETRIEVAL RECOMMENDED AS DEFAULT**

---

## 1. Executive Summary

This evaluation re-assesses the platform's retrieval capabilities across **Lexical (BM25-style FTS)**, **Semantic (`all-MiniLM-L6-v2` ONNX)**, and **Hybrid (Reciprocal Rank Fusion)** pipelines:

1. **Resolution of the Historical Denominator Discrepancy:**  
   The historical reporting question ("25 queries vs 22 denominator") has been resolved and verified with mathematical rigor. The dataset contains **25 total queries**: **22 answerable queries** evaluated strictly for ranking quality (Recall, Precision, MRR, nDCG) and **3 unanswerable queries** evaluated separately for negative rejection. Computing Recall over unanswerable queries with 0 ground-truth chunks would create a division-by-zero error or artificial score dilution.
2. **Diagnosis of the Hybrid RRF Regression:**  
   Investigated why Hybrid RRF underperformed Semantic-only retrieval (Recall@1 dropped from 95.45% to 81.82%; MRR dropped from 0.9697 to 0.8977). Query-by-query tracing revealed that equal-weighted RRF ($1/(60 + \text{rank})$) allows **lexical noise to demote semantic top-1 hits** on queries involving paraphrasing and domain synonyms (`q02`, `q10`, `q17`, `q21`).
3. **Controlled Experimentation:**  
   Benchmarked 8 fusion parameter variations. Down-weighting lexical contribution ($w_{lex}=0.2, w_{sem}=1.0$) recovers Recall@1 to 95.45% and improves MRR to 0.9773. However, given the zero-overhead simplicity and 95.45% Recall@1 of **Semantic-only retrieval**, it is recommended as the platform's default mode.

---

## 2. Dataset Accounting & Integrity

### A. Dataset Metadata
- **File:** `backend/evaluations/dataset.json`
- **SHA-256 Hash:** `3A636AF79C1FFF32011D2D2D558A60F909BB7381913F1A3966152E987670E6C5`
- **Total Documents:** 6 documents
- **Total Chunks:** 18 chunks (exactly 3 chunks per document)
- **Total Queries:** 25 queries
- **Answerable Queries:** 22 queries (88.0%)
- **Unanswerable / Out-of-Domain Queries:** 3 queries (12.0%)

### B. Query-by-Query Accounting Matrix

| Query ID | Category | Query Text | Answerable | Target Chunk | Evaluation Track |
|---|---|---|---|---|---|
| `q01` | direct_keyword | How many days of paid vacation do employees receive each year? | Yes | `chunk-hr-1` | Ranking Metrics |
| `q02` | paraphrase | What is the doctor note requirement when someone is out sick? | Yes | `chunk-hr-2` | Ranking Metrics |
| `q03` | semantic_synonym | Can unused holiday time be carried over to the following year? | Yes | `chunk-hr-3` | Ranking Metrics |
| `q04` | direct_keyword | What hardware authentication is required for remote network connection? | Yes | `chunk-it-1` | Ranking Metrics |
| `q05` | paraphrase | What kind of cryptographic keys are required to connect to production jump servers? | Yes | `chunk-it-2` | Ranking Metrics |
| `q06` | fact_lookup | How quickly must an employee report a misplaced or stolen company laptop? | Yes | `chunk-it-3` | Ranking Metrics |
| `q07` | direct_keyword | Which version of Python and SQLAlchemy is standard for backend services? | Yes | `chunk-eng-1` | Ranking Metrics |
| `q08` | semantic_synonym | How is multi-tenant database isolation enforced in SQL queries and schemas? | Yes | `chunk-eng-2` | Ranking Metrics |
| `q09` | fact_lookup | How many code reviews are needed before merging a feature into main? | Yes | `chunk-eng-3` | Ranking Metrics |
| `q10` | direct_keyword | What is the deadline for submitting travel expense claims? | Yes | `chunk-fin-1` | Ranking Metrics |
| `q11` | fact_lookup | What is the daily meal budget when traveling internationally for business? | Yes | `chunk-fin-2` | Ranking Metrics |
| `q12` | semantic_synonym | How much money per mile is paid when driving your personal car for company work? | Yes | `chunk-fin-3` | Ranking Metrics |
| `q13` | direct_keyword | What is the response time requirement for a Sev-1 service outage? | Yes | `chunk-inc-1` | Ranking Metrics |
| `q14` | paraphrase | What is the update frequency and SLA for major feature degradation? | Yes | `chunk-inc-2` | Ranking Metrics |
| `q15` | fact_lookup | When must a blameless post-mortem draft be published following an incident? | Yes | `chunk-inc-3` | Ranking Metrics |
| `q16` | semantic_synonym | How does the platform combine lexical search and vector similarity scores? | Yes | `chunk-ai-1` | Ranking Metrics |
| `q17` | semantic_synonym | What optical character recognition tool is used when PDFs have no selectable text? | Yes | `chunk-ai-2` | Ranking Metrics |
| `q18` | direct_keyword | How are customer third-party LLM credentials protected at rest? | Yes | `chunk-ai-3` | Ranking Metrics |
| `q19` | semantic_synonym | taking time off for holiday rest and vacation guidelines | Yes | `chunk-hr-1` | Ranking Metrics |
| `q20` | paraphrase | What happens if my vacation days exceed the rollover limit on New Year's Eve? | Yes | `chunk-hr-3` | Ranking Metrics |
| `q21` | fact_lookup | Can employees buy beer or wine during business travel? | Yes | `chunk-fin-2` | Ranking Metrics |
| `q22` | paraphrase | What are the rules for hard drive encryption on employee computers? | Yes | `chunk-it-3` | Ranking Metrics |
| `q23` | unanswerable | What is the best recipe for baking homemade sourdough bread? | No | *(None)* | Rejection Accuracy |
| `q24` | unanswerable | Does the company allow cryptocurrency mining in the office data center? | No | *(None)* | Rejection Accuracy |
| `q25` | unanswerable | What is the tuition reimbursement policy for master degree programs? | No | *(None)* | Rejection Accuracy |

---

## 3. Metric Formulations & Confidence Intervals

All ranking metrics are computed over the $N=22$ answerable query subset. 95% Confidence Intervals are calculated using the **Wilson Score Interval**:

$$\text{Wilson Interval} = \frac{p + \frac{z^2}{2N} \pm z\sqrt{\frac{p(1-p)}{N} + \frac{z^2}{4N^2}}}{1 + \frac{z^2}{N}}$$

where $z = 1.96$ and $p = \frac{\text{Hits}}{N}$.

- **Recall@K:** Proportion of relevant chunks retrieved in top $K$ candidates ($|\text{Relevant}| = 1$ in this benchmark).
- **Mean Reciprocal Rank (MRR):** Average reciprocal rank $\frac{1}{N} \sum_{i=1}^N \frac{1}{\text{rank}_i}$, where unretrieved queries yield $\text{rank} = \infty \implies \text{reciprocal} = 0$.
- **nDCG@3 / nDCG@5:** Normalized Discounted Cumulative Gain against ideal binary ranking.

---

## 4. Evaluated Results & Comparisons

| Metric | Lexical (BM25 FTS) | Semantic (`all-MiniLM-L6-v2`) | Hybrid RRF ($k=60$) | Semantic Advantage |
|---|---|---|---|---|
| **Recall@1 (Hits/22)** | 15/22 (68.18%) | **21/22 (95.45%)** | 18/22 (81.82%) | **+13.63% over Hybrid** |
| 95% Wilson CI (R@1) | [47.32%, 83.64%] | **[78.20%, 99.19%]** | [61.48%, 92.69%] | Statistically higher lower bound |
| **Recall@3 (Hits/22)** | 17/22 (77.27%) | **22/22 (100.00%)** | 21/22 (95.45%) | **+4.55% over Hybrid** |
| 95% Wilson CI (R@3) | [56.56%, 89.88%] | **[85.13%, 100.00%]** | [78.20%, 99.19%] | Perfect recall at K=3 |
| **Recall@5 (Hits/22)** | 19/22 (86.36%) | **22/22 (100.00%)** | 22/22 (100.00%) | Parity |
| **MRR** | 0.7515 | **0.9697** | 0.8977 | **+0.0720 over Hybrid** |
| **nDCG@3** | 0.7273 | **0.9773** | 0.9042 | **+0.0731 over Hybrid** |
| **Negative Query Rejection** | 0/3 (0.00%)* | **3/3 (100.00%)** | **3/3 (100.00%)** | Reliable thresholding (<0.40) |
| **Median Latency (p50)** | **0.26 ms** | 12.59 ms | 12.89 ms | Semantic is well within SLA (<20ms) |

*\*Note on Lexical Negative Rejection: Lexical scoring without a length/IDF baseline frequently yields non-zero scores on partial stopword/common term overlaps unless an explicit minimum term frequency cutoff is applied.*

---

## 5. Investigation of the Hybrid RRF Regression

### A. Root Cause Analysis
Reciprocal Rank Fusion computes:
$$\text{RRF}(d) = \sum_{r \in \{\text{lex}, \text{sem}\}} \frac{1}{k + \text{rank}_r(d)}$$

When $w_{lex} = w_{sem} = 1.0$ and $k=60$:
1. A relevant chunk that is semantic rank 1 ($1/61 \approx 0.01639$) but lexical rank 12 ($1/72 \approx 0.01389$) receives an RRF score of $0.03028$.
2. An irrelevant chunk that happens to rank high in lexical due to matching common terms (e.g. lexical rank 2, $1/62 \approx 0.01613$) and has moderate semantic similarity (e.g. rank 4, $1/64 \approx 0.01562$) achieves an RRF score of $0.03175$.
3. **Outcome:** The irrelevant chunk outscores the ground-truth chunk ($0.03175 > 0.03028$).

### B. Query-by-Query Regression Trace

Tracing the 4 regressed queries:

1. **`q02` [paraphrase]:**
   - *Query:* "What is the doctor note requirement when someone is out sick?"
   - *Target Chunk (`chunk-hr-2`):* Uses the phrase *"official medical practitioner certificate"*.
   - *Semantic Rank:* **1** (recognized medical practitioner certificate as doctor note).
   - *Lexical Rank:* **12** (no exact token match for "doctor" or "note").
   - *Result:* Hybrid demoted the relevant chunk to **Rank 4**.
2. **`q10` [direct_keyword]:**
   - *Query:* "What is the deadline for submitting travel expense claims?"
   - *Target Chunk (`chunk-fin-1`):* Mentions submission deadline of 30 days.
   - *Semantic Rank:* **1**.
   - *Lexical Rank:* **6** (lexical matched "travel" and "expense" equally in meal policy `chunk-fin-2` and mileage `chunk-fin-3`).
   - *Result:* Hybrid demoted target to **Rank 2**.
3. **`q17` [semantic_synonym]:**
   - *Query:* "What optical character recognition tool is used when PDFs have no selectable text?"
   - *Target Chunk (`chunk-ai-2`):* Mentions *"Tesseract OCR is invoked for scanned pages"*.
   - *Semantic Rank:* **1**.
   - *Lexical Rank:* **4**.
   - *Result:* Hybrid demoted target to **Rank 2**.
4. **`q21` [fact_lookup]:**
   - *Query:* "Can employees buy beer or wine during business travel?"
   - *Target Chunk (`chunk-fin-2`):* Mentions *"Alcohol purchases are non-reimbursable unless authorized"*.
   - *Semantic Rank:* **1** (understood beer/wine as alcohol).
   - *Lexical Rank:* **5**.
   - *Result:* Hybrid demoted target to **Rank 2**.

### C. The Single Improved Query
- **`q18` [direct_keyword]:**
  - *Query:* "How are customer third-party LLM credentials protected at rest?"
  - *Semantic Rank:* **3** | *Lexical Rank:* **1** (exact keyword overlap for "credentials protected at rest").
  - *Hybrid Rank:* **1** (RRF successfully boosted target to Rank 1).

---

## 6. Controlled Fusion Experiments

Evaluated weighted RRF variations where $\text{RRF}(d) = \frac{w_{lex}}{k + \text{rank}_{lex}} + \frac{w_{sem}}{k + \text{rank}_{sem}}$:

| Configuration | Recall@1 | Recall@3 | MRR | nDCG@3 |
|---|---|---|---|---|
| Standard RRF ($k=60, w_{lex}=1.0, w_{sem}=1.0$) | 81.82% | 95.45% | 0.8977 | 0.9042 |
| Standard RRF ($k=20, w_{lex}=1.0, w_{sem}=1.0$) | 81.82% | 95.45% | 0.8977 | 0.9042 |
| Standard RRF ($k=100, w_{lex}=1.0, w_{sem}=1.0$) | 81.82% | 95.45% | 0.8977 | 0.9042 |
| Weighted RRF ($k=60, w_{lex}=0.5, w_{sem}=1.0$) | 90.91% | 100.00% | 0.9545 | 0.9664 |
| Weighted RRF ($k=60, w_{lex}=0.3, w_{sem}=1.0$) | 90.91% | 100.00% | 0.9545 | 0.9664 |
| **Weighted RRF ($k=60, w_{lex}=0.2, w_{sem}=1.0$)** | **95.45%** | **100.00%** | **0.9773** | **0.9832** |
| **Semantic Only (Baseline)** | **95.45%** | **100.00%** | **0.9697** | **0.9773** |

*Findings:* Tuning the rank constant $k$ alone has zero effect on top-1 ordering in this corpus. However, down-weighting the lexical contribution ($w_{lex} \approx 0.2$) restores 95.45% Recall@1 while capturing the lexical benefit of `q18`, achieving peak MRR (0.9773).

---

## 7. No-Answer Evaluation & Rejection Boundaries

Critical distinction between two platform boundaries:
1. **Retrieval Rejection (Evaluated):** The retrieval engine does not return high-confidence irrelevant chunks for out-of-domain queries (`q23`: sourdough bread, `q24`: cryptocurrency mining, `q25`: tuition reimbursement). With cosine similarity threshold $\tau = 0.40$, negative queries achieved **100% rejection accuracy (3/3)**.
2. **Assistant Answer Abstention (Runtime):** The LLM assistant acknowledges missing context and abstains from hallucinating answers based on system prompt guardrails.

---

## 8. Latency & Resource Consumption (CPU-Only)

Measured on Windows 11 host (Intel Core i3-7100U, 8 GB RAM):

| Retrieval Stage | Avg Latency | Median (p50) | p95 Latency | Memory Footprint |
|---|---|---|---|---|
| **Lexical Search (BM25)** | 0.32 ms | 0.26 ms | 0.84 ms | <1 MB |
| **Semantic Embedding (`all-MiniLM-L6-v2`)** | 15.50 ms | 12.59 ms | 24.12 ms | ~22 MB ONNX model |
| **RRF Fusion Combination** | 0.04 ms | 0.03 ms | 0.12 ms | <0.1 MB |
| **Total Hybrid End-to-End** | 15.86 ms | 12.88 ms | 25.08 ms | ~23 MB total |

*Assessment:* Semantic retrieval on CPU runs comfortably under the 50ms interactive threshold (median 12.59ms) without GPU requirements.

---

## 9. Final Strategic Recommendation

### Decision: **A. SEMANTIC RETRIEVAL RECOMMENDED AS DEFAULT**

**Rationale:**
1. **Accuracy:** Semantic retrieval delivers **95.45% Recall@1**, **100.00% Recall@3**, and **0.9697 MRR**, significantly outperforming standard equal-weighted Hybrid RRF (81.82% Recall@1, 0.8977 MRR).
2. **Operational Simplicity:** Avoids dual-query overhead (PostgreSQL FTS + Vector DB + Fusion logic) for standard organizational search.
3. **Vocabulary Robustness:** Enterprise knowledge queries predominantly feature paraphrasing, informal language, and synonyms that pure lexical search consistently ranks poorly.
4. **Hybrid Retained as Configurable Option:** Hybrid retrieval remains fully supported in [`RetrievalService`](file:///E:/MM%20Office/Multi-Tanant-CaaS/backend/app/retrieval/service.py) for tenants whose specific domain documents require exact serial number or code identifier matching.

---

## 10. Generated Artifacts Inventory

- [`artifacts/evaluations/m05_staging_readiness/04_retrieval_evaluation.md`](file:///E:/MM%20Office/Multi-Tanant-CaaS/artifacts/evaluations/m05_staging_readiness/04_retrieval_evaluation.md)
- [`artifacts/evaluations/m05_staging_readiness/results/retrieval_dataset_audit.json`](file:///E:/MM%20Office/Multi-Tanant-CaaS/artifacts/evaluations/m05_staging_readiness/results/retrieval_dataset_audit.json)
- [`artifacts/evaluations/m05_staging_readiness/results/retrieval_metrics.json`](file:///E:/MM%20Office/Multi-Tanant-CaaS/artifacts/evaluations/m05_staging_readiness/results/retrieval_metrics.json)
- [`artifacts/evaluations/m05_staging_readiness/results/retrieval_raw_results.json`](file:///E:/MM%20Office/Multi-Tanant-CaaS/artifacts/evaluations/m05_staging_readiness/results/retrieval_raw_results.json)
- [`artifacts/evaluations/m05_staging_readiness/results/retrieval_latency.json`](file:///E:/MM%20Office/Multi-Tanant-CaaS/artifacts/evaluations/m05_staging_readiness/results/retrieval_latency.json)
- [`artifacts/evaluations/m05_staging_readiness/results/hybrid_experiments.json`](file:///E:/MM%20Office/Multi-Tanant-CaaS/artifacts/evaluations/m05_staging_readiness/results/hybrid_experiments.json)

---

## 11. Phase Boundary Stop Condition

Per M05 instructions, execution has stopped here. **Phase 4 (Tenant Isolation, Resource ACL, and Assistant Security) has not been started.**

Awaiting your review and approval before proceeding to Phase 4.
