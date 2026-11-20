# M26.4 — Performance, Observability & Operational Hardening Report

## 1. Executive Summary
Phase M26.4 measured system resource consumption, cold-start characteristics, and privacy-preserving observability metrics across multimodal workloads.

---

## 2. Resource & Latency Measurements (Local Bounded Workload)

| Operation | Workload | Latency / Metric | Resource Note |
|---|---|---|---|
| **Multi-page PDF Parsing** | 3-page synthetic PDF (PyMuPDF) | ~18 ms | CPU-only, minimal memory (< 5 MB) |
| **DOCX Parsing** | 2-section DOCX (python-docx) | ~12 ms | Memory-mapped buffer |
| **Chunk Extraction & DB Commit** | 3 chunks with token counting | ~35 ms | Indexed on `conversation_id`, `tenant_id` |
| **Attachment Search Query** | BM25 lexical overlap query | ~4.2 ms | Scoped by tenant and conversation |
| **Full Regression Suite** | 670 backend test cases | 818.69 s (~13.6 min) | 652 passed, 18 skipped |
| **Frontend Production Build** | Next.js 16.4.5 (Turbopack) | 5.5 s build, 12.6 s TS | 22 static pages generated |

---

## 3. Free-Tier Cloud Resilience & Failure Behavior
- **Render Idle Spin-Down:** Cold starts on Render Free typically take 25–45 seconds. The frontend features a warm-up retry interceptor and persistent status banner.
- **Neon Scale-to-Zero:** Neon staging database branch `br-tiny-wind-arvfyx75` suspends on inactivity. SQLAlchemy async engine is configured with connection recycling and pre-ping (`pool_pre_ping=True`).
- **SSE Stream Robustness:** If a client network connection drops during SSE streaming, `abortControllerRef` terminates the client reader cleanly, and the server aborts the generator without dangling locks.

---

## 4. Privacy-Preserving Observability
- **Trace Schema:** Traces capture execution spans (`attachment_upload`, `attachment_search`, `stream_message`, `tool_call`) with `duration_ms`, `status`, and `token_usage`.
- **METADATA_ONLY Privacy:** Document binary content, audio waveforms, and raw spoken transcripts are never stored in observability logs or traces. Only character counts, token estimates, and metadata flags are recorded.
