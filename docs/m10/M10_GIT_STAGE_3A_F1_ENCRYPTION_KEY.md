# M10 Git Stage 3A - F1 Remediation: Dedicated BYOK Encryption Key

## Scope

Applies the recommendation for Defect F1 in `M10_GIT_STAGE_3_SECURITY_REVIEW.md`.
This work belongs to remediation **Group C** (M10 remediation/security configuration)
in `M10_GIT_STAGE_1_CHANGE_CLASSIFICATION.md`.

No encryption algorithm changes: Fernet and the SHA-256 key-derivation helper are
untouched; only the source of the active key material changes.

## Root cause

- `SECRET_ENCRYPTION_KEY` was documented in `.env.production.example` and generated
  by `render.yaml`, but `Settings` never declared it. Because settings use
  `extra="ignore"`, the environment value was silently discarded.
- `get_active_fernet_key()` derived the active Fernet key only from `SECRET_KEY`.
- Consequently, setting or rotating `SECRET_ENCRYPTION_KEY` had no effect, and the
  runbooks that instruct rotating it described a non-functional operation.

## Severity

**Medium - pre-existing configuration/operability defect.** It predates the M10
remediation (introduced with the M05 deployment blueprint) and is not a
tenant-isolation break or an authentication bypass. BYOK secrets were still
encrypted, but under `SECRET_KEY`-derived material. The risk is operational:
false confidence that a dedicated BYOK key was configured or rotated, and
ciphertext continuing to depend on `SECRET_KEY`.

## Smallest safe fix

1. `backend/app/core/config.py`: declare `SECRET_ENCRYPTION_KEY: str = ""` in the
   security block.
2. `backend/app/core/crypto.py`: `get_active_fernet_key()` uses
   `settings.SECRET_ENCRYPTION_KEY` when non-empty, otherwise falls back to
   `settings.SECRET_KEY`. `get_previous_fernet_keys()` semantics are unchanged
   (comma-separated `PREVIOUS_SECRET_KEYS`); only its docstring wording changed.
3. No other behavior changes: `encrypt_secret`, `decrypt_secret`,
   `rotate_secret`, `verify_secret_rotation`, aliases, and multi-key handling are
   untouched.
4. `.env.production.example`: comment clarified only; the value remains empty.

Because the setting defaults to empty, deployments that never set it keep the
exact previous key derivation, so existing ciphertext remains decryptable.

## Backward compatibility and rotation procedure

Existing rows are encrypted under `derive_fernet_key(SECRET_KEY)`. Leaving
`SECRET_ENCRYPTION_KEY` empty preserves that derivation exactly.

To enable a dedicated key on existing data:

1. Add the old key material (the current `SECRET_KEY` value, plus any other prior
   material, comma-separated) to `PREVIOUS_SECRET_KEYS` **before** switching.
2. Set `SECRET_ENCRYPTION_KEY` to the new dedicated value.
3. Deploy. `MultiFernet` decrypts legacy ciphertext through the fallback keys and
   writes new ciphertext under the dedicated active key.
4. Optionally run the batch rotation/verification path, then remove the old
   material from `PREVIOUS_SECRET_KEYS` once all records are re-encrypted.

Rotating a dedicated key later follows the same pattern: move the old
`SECRET_ENCRYPTION_KEY` value into `PREVIOUS_SECRET_KEYS` first. Never commit real
key material; templates keep empty/placeholder values.

## Tests

`backend/tests/test_remediation_encryption_key.py` (3 tests):

1. **Default fallback:** unset `SECRET_ENCRYPTION_KEY` -> active key equals
   `derive_fernet_key(settings.SECRET_KEY)`; encrypt/decrypt roundtrip equals the
   plaintext.
2. **Dedicated key:** active key equals `derive_fernet_key(dedicated)` and differs
   from the `SECRET_KEY`-derived key; roundtrip works.
3. **Rotation path:** ciphertext encrypted under the `SECRET_KEY`-derived key is
   decrypted through `get_multi_fernet()` after switching to the dedicated key
   with the old material in `PREVIOUS_SECRET_KEYS`.

Tests monkeypatch the `settings` singleton from `app.core.config`; monkeypatch
restores attributes automatically.

Verification performed for this change:

- `python -m compileall -q app` -> exit 0
- `pytest tests/test_remediation_encryption_key.py tests/test_quota_and_byok_policy.py tests/test_m07_knowledge_and_providers.py -q --tb=short` -> see session report for the exact result line
- `pip check` -> see session report

## Files changed

- `backend/app/core/config.py` - added `SECRET_ENCRYPTION_KEY` setting.
- `backend/app/core/crypto.py` - active-key selection and docstrings.
- `backend/tests/test_remediation_encryption_key.py` - new tests (3).
- `.env.production.example` - comment clarification only; value still empty.
- `docs/m10/M10_GIT_STAGE_3A_F1_ENCRYPTION_KEY.md` - this document.

Separately in the same working tree, migration
`backend/alembic/versions/0010_m10_remediation_schema_alignment.py` received
wording/default corrections (PART 1 of the task); that is not part of F1.

## Residual risk

- Enabling `SECRET_ENCRYPTION_KEY` without first adding the old `SECRET_KEY`
  material to `PREVIOUS_SECRET_KEYS` makes previously stored BYOK ciphertext
  undecryptable (fail-closed; decrypt errors are logged, secrets are not).
- Re-encryption is not automatic: `MultiFernet` rotates on write/rotation calls,
  so old material must remain in `PREVIOUS_SECRET_KEYS` until all rows are
  re-encrypted.
- The legacy `ENCRYPTION_KEY` setting remains unused by the crypto layer; it was
  out of scope for this fix.