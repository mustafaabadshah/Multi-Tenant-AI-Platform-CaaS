# Assistant Configuration Architecture

## 1. Unified Configuration Schema

The platform maintains a single underlying configuration model for both Simple and Advanced modes. Switching between configuration modes in the UI never discards, resets, or desynchronizes settings.

```
                      +-----------------------------+
                      | AssistantConfigurationModel |
                      +-----------------------------+
                      |                             |
    Simple Mode       | - name                      |       Advanced Mode
  ----------------->  | - description               |  <-------------------
  • Response Style    | - template_id & version     |  • Top-K Chunks (1-15)
  • Audience Level    | - audience_level            |  • Temperature (0-1)
  • Citation Style    | - response_style            |  • Output Tokens (64-4096)
  • Uncertainty       | - uncertainty_behavior      |  • Retrieval Mode
  • Custom Persona    | - citation_style            |    (Hybrid, Semantic, Lexical)
                      | - system_prompt             |  • LLM Provider & Model
                      | - llm_provider              |
                      | - default_model             |
                      | - temperature               |
                      | - max_tokens                |
                      | - retrieval_mode            |
                      | - top_k                     |
                      | - knowledge_base_ids        |
                      +-----------------------------+
```

---

## 2. Behavioral Parameters

- **`audience_level`**: Adjusts cognitive complexity, vocabulary, and prerequisite depth (`beginner`, `intermediate`, `advanced`, `undergraduate`, `expert`).
- **`response_style`**: Controls communicative tone (`socratic`, `academic`, `balanced`, `professional`, `concise`, `creative`).
- **`uncertainty_behavior`**:
  - `admit`: Explicitly states when knowledge bases do not contain requested information; prohibits fabricated facts.
  - `clarify`: Prompts the user with targeted clarifying questions before providing an answer.
- **`citation_style`**:
  - `strict`: Every declarative claim derived from documents must be tagged with explicit bracketed index chips `[1]`.
  - `relaxed`: Summarizes context naturally without strict claim-level indexing.

---

## 3. Storage & Relational Scoping

Assistant configuration is stored in the PostgreSQL/SQLite `assistants` table with strict composite foreign keys:
- Primary Key: `UUID`
- Partitioning / Scope: `tenant_id`
- Composite Foreign Keys:
  - `assistant_knowledge_bases` link table includes `(assistant_id, knowledge_base_id, tenant_id)` composite constraints to prevent cross-tenant knowledge association.
