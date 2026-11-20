# Usage Accounting & Server-Side Quota Enforcement (M07)

## Overview
The Usage & Quota system enforces limits server-side *before* provider invocation occurs, preventing surprise overages and race conditions while recording audit-ready token telemetry.

### Quota Checks: Pre-Invocation Gatekeeping

Before calling any LLM provider adapter:
1. `QuotaService.check_quota(estimated_tokens)` runs inside `AssistantRuntime`.
2. Computes current monthly token consumption:
   $$\text{Monthly Tokens} = \sum \text{total\_tokens} \quad (\text{since 1st of month } 00:00\text{ UTC})$$
3. Checks monthly limit: If `(current_monthly_tokens + estimated_tokens) > monthly_token_limit`, immediately raises `HTTP 429 Too Many Requests`.
4. Computes daily request count: If `today_requests >= daily_request_limit`, immediately raises `HTTP 429 Too Many Requests`.
5. When rejected, **no external LLM API calls are made**.

### Usage Persistence: Post-Generation Accounting

After response completion or streaming termination:
- Persists record in `provider_usage_logs`:
  - `tenant_id`: Strictly isolated.
  - `user_id`: Identifying caller.
  - `assistant_id`: Associated assistant entity.
  - `provider`: Provider key (`groq`, `anthropic`, `gemini`, `openai`, `omniroute`).
  - `model`: Exact model used.
  - `prompt_tokens`: Calculated from input messages.
  - `completion_tokens`: Calculated from generated tokens.
  - `total_tokens`: Sum of prompt and completion tokens.
  - `is_estimated`: Distinguishes provider-reported usage from local heuristics.
