# BYOK Key Management Security Specification (M07)

## Cryptographic Architecture
Bring Your Own Key (BYOK) credentials allow tenants to run inferences with their own provider subscriptions without exposing secrets to other tenants, frontend browsers, or server log files.

### 1. Storage & Encryption at Rest
- Encryption engine: Authenticated Fernet symmetric encryption (`backend/app/core/crypto.py`).
- Key generation: AES-128-CBC with HMAC-SHA256 authenticated encryption using `SECRET_KEY`.
- Stored fields:
  - `encrypted_api_key`: Base64-encoded encrypted ciphertext.
  - `api_key_masked`: Redacted preview showing only the prefix and suffix (e.g., `sk-ant...5678`).

### 2. Zero Plaintext Exposure Policy
1. Plaintext API keys are **never** returned in GET, POST, or PUT responses.
2. Plaintext is decrypted strictly in memory at invocation time inside `BYOKVaultService.resolve_plaintext_key()`.
3. Error messages and logs are sanitized using `sanitize_error_message()` to strip API keys, Bearer tokens, and secrets.
4. Browser local storage and session storage never receive plaintext keys.

### 3. Key Rotation & Revocation
- **Rotation**: Calling `POST /api/v1/providers/credentials/{id}/rotate` encrypts the new key and immediately updates active inferences without dropping connections.
- **Revocation**: Calling `POST /api/v1/providers/credentials/{id}/revoke` sets `is_active=False` and `status="REVOKED"`, instantly terminating further inferences using that credential.
