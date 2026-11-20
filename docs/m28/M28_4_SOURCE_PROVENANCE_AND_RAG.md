# M28.4 Source Provenance & Grounded RAG Context

## 1. Overview

In grounded LLM interaction, distinguishing between raw digital text, optical character recognition derived text, and web resources is vital for user trust and citation verifiability. M28.4 introduces transparent source provenance across the RAG retrieval pipeline and conversational context assembly.

## 2. Provenance Architecture

```
                                  [Document / Web Chunk]
                                            │
                             ┌──────────────┴──────────────┐
                             ▼                             ▼
                    `ocr_derived: True`            `ocr_derived: False`
                             │                             │
                      Tag: `[OCR Derived]`                 │
                             │                             │
                             └──────────────┬──────────────┘
                                            ▼
                               [build_rag_context()]
                                            │
               ┌────────────────────────────┴────────────────────────────┐
               ▼                                                         ▼
     [Web / Single-Page Source]                                 [Paginated PDF Document]
     `page_number: None`                                        `page_number: int`
     Citation: `[Source: URL / Title [OCR Derived]]`           Citation: `[Source: Title (p. N) [OCR Derived]]`
```

## 3. Context Construction Implementation

In `backend/app/assistant_runtime/context.py`, `build_rag_context` inspects both the chunk-level `page_number` and the metadata `ocr_derived` field:

```python
ocr_label = " [OCR Derived]" if result.metadata.get("ocr_derived") else ""

if result.page_number is not None:
    page_info = f" (p. {result.page_number})"
else:
    page_info = ""

header = f"[Source: {source_name}{page_info}{ocr_label}]"
```

### Key Grounding Rules Enforced:
1. **No False Page Numbers:** Webpages, HTML articles, and single images do not default to `(p. 1)`. When `page_number` is `None`, the citation header simply displays the domain or title cleanly.
2. **Explicit OCR Labeling:** When content is derived via OCR from scanned PDF pages or raster images, `[OCR Derived]` is appended to the citation tag, notifying the LLM and the user that minor OCR artifacts or layout ambiguities could exist.
3. **Conversation Isolation:** Temporary conversation-scoped web contexts remain isolated per conversation session and are never exposed across tenant boundaries.
