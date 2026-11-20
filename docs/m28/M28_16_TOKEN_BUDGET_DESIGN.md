# M28.16 — Disciplined Context Assembly, Token Budgeting & Anti-Hallucination Guardrails

**Milestone:** M28.16  
**Component:** Assistant Runtime Context (`backend/app/assistant_runtime/context.py`, `runtime.py`)  
**Status:** IMPLEMENTED & LOCAL TEST VERIFIED (`20/20 PASS`)  
**Target Invariant:** Strict Free-Tier Quota Adherence, Zero Hallucinated Citations on Empty Context  

---

## 1. Problem Definition & Operational Context

In free-tier multi-provider environments (such as Groq's 8,000 TPM limit or Render's resource constraints), naive context assembly creates two fatal failure modes:
1. **Token Exhaustion (HTTP 429):** Injecting unbounded candidate chunks pushes single requests past the rate-limit window.
2. **Ghost Grounding & Hallucinated Citations:** When no documents are attached to an assistant or when candidate retrieval returns 0 chunks, generic prompt instructions (e.g., "always cite factual assertions with [1]") force LLMs to fabricate bracket citations `[1]`, `[2]` and recall phantom knowledge from conversation history or generic system prompt examples.

---

## 2. Architecture & Budget Specifications

### 2.1 Conservative Token Estimation
`estimate_tokens(text: str) -> int`:
```python
def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, int(len(text) / 3.3))
```
*Rationale:* Traditional rule-of-thumb `len(text) / 4` undercounts tokens for JSON, technical code, math formulas, and punctuation-dense academic texts by 15–25%. The 3.3 ratio ensures context budgets do not leak over strict provider thresholds.

### 2.2 Tiered Token Allocation Policy

| Category | Max Token Budget | Truncation / Drop Strategy |
|---|---|---|
| **System Base Persona** | ~400 tokens | Fixed core prompt & instructions |
| **Knowledge Base (RAG)** | 1,200 tokens | Candidate chunks added by rank; dropped once budget is reached |
| **Academic Research (arXiv)** | 400 tokens | Top 2 preprints max; abstracts capped at 650 chars |
| **Conversation History** | ~350 tokens | Last 4 messages (2 turns); older turns pruned |
| **User Input & Tools** | ~250 tokens | Current turn query & function signatures |
| **Total Prompt Budget** | **~2,600 tokens** | Safe for Groq 8,000 TPM window (leaves 5,400 TPM headroom) |

### 2.3 Anti-Hallucination & Empty KB Grounding Rules
In `backend/app/assistant_runtime/context.py`:
- **When Knowledge Base blocks exist ($> 0$):**
  - Injects `<KNOWLEDGE_BASE_CONTEXT>` container with provenance metadata (`[1] title (p. X, chunk Y)`).
  - Instructs assistant to cite factual statements with numeric bracket badges matching source blocks.
- **When Knowledge Base blocks do NOT exist ($= 0$):**
  - Completely omits `<KNOWLEDGE_BASE_CONTEXT>` XML tags.
  - Injects mandatory negative constraint:
    > `"NO KNOWLEDGE BASE SOURCES ATTACHED: There are NO internal documents or uploaded knowledge bases connected for this conversation. NEVER generate bracket citation badges like [1], [2], or phantom source references. If the user asks what documents or study materials are available, state clearly and honestly that no documents or knowledge bases are currently connected."`
  - Removed all hardcoded domain-specific examples (such as "solar irradiance forecasting") from generic behavioral templates to prevent accidental memory anchoring.

### 2.4 Educational Assessment & Quiz Formatting Standards
Added explicit formatting directives:
- When generating quizzes, tests, or assessments:
  - Do NOT cram questions, options, and answers into a single horizontal markdown table.
  - Format each question cleanly with its number, question stem, and options (A, B, C, D) on separate indented lines.
  - Separate multiple question types (Multiple Choice, True/False, Short Answer) into dedicated sections.
  - Provide an organized **Answer Key & Explanations** section at the bottom citing exact source pages.

### 2.5 Cross-Turn URL Retention Engine
In `backend/app/assistant_runtime/runtime.py`:
- Increased message lookup window from 10 to 25 messages (`limit(25)`).
- Implemented regular expression URL harvesting across full conversation history (`re.findall(r'https?://[^\s<>"]+')`).
- When user references previously shared links (e.g. "what was that W3Schools link" or "refer back to the link I sent"), the runtime injects an explicit contextual bridge referencing the discovered URLs.
