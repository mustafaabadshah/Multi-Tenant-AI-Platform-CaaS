# Provider Management & BYOK Vault — Product Specification (M07)

## Overview
Provider Management provides a modular, vendor-agnostic foundation for executing AI inferences. Tenants can use the default OmniRoute gateway or bring their own API keys (BYOK) for Groq, Anthropic, Google Gemini, and OpenAI with zero cross-tenant leakage.

---

## 1. Key Features

1. **Provider Directory**:
   - Central catalog showing available inference engines and production models.
   - Capability badges: Streaming, Tool Calling, Vision, Context Window, and Output Limits.

2. **BYOK Secret Vault**:
   - Encrypted storage at rest using authenticated cryptography (Fernet).
   - Secret masking: Plaintext is never returned in API responses or rendered in the DOM after creation.
   - Seamless key rotation: Updating credentials takes effect immediately across active assistants without downtime.
   - Instant revocation: Deactivates compromised keys with a single click.

3. **Usage Accounting & Quota Limits**:
   - Real-time monthly token progress bar (`used / limit`).
   - Daily request tracking with UTC midnight resets.
   - Prompt vs Completion token breakdown.
   - Provider breakdown table showing exact request counts and tokens consumed.
