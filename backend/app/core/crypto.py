"""Secret encryption and masking utilities for BYOK API keys and credentials."""

import base64
import hashlib
import logging
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.core.config import settings

logger = logging.getLogger("mmaip.security")


def derive_fernet_key(key_material: str) -> bytes:
    """Derive a consistent 32-byte URL-safe base64 key from arbitrary string key material."""
    raw_key = key_material.encode("utf-8")
    digest = hashlib.sha256(raw_key).digest()
    return base64.urlsafe_b64encode(digest)


def get_active_fernet_key() -> bytes:
    """Get the active encryption key derived from settings.SECRET_KEY."""
    return derive_fernet_key(settings.SECRET_KEY)


def get_previous_fernet_keys() -> list[bytes]:
    """Get previous encryption keys derived from settings.PREVIOUS_SECRET_KEYS."""
    raw = getattr(settings, "PREVIOUS_SECRET_KEYS", "") or ""
    keys: list[bytes] = []
    for item in raw.split(","):
        cleaned = item.strip()
        if cleaned:
            keys.append(derive_fernet_key(cleaned))
    return keys


# Backward compatibility aliases
_get_fernet_key = get_active_fernet_key



def get_multi_fernet(
    primary_key: Optional[bytes] = None,
    fallback_keys: Optional[list[bytes]] = None,
) -> MultiFernet:
    """Construct a MultiFernet instance using primary key and optional fallback keys."""
    primary = primary_key or get_active_fernet_key()
    fallbacks = fallback_keys if fallback_keys is not None else get_previous_fernet_keys()
    fernet_instances = [Fernet(primary)] + [Fernet(k) for k in fallbacks]
    return MultiFernet(fernet_instances)


def encrypt_secret(plaintext: str, key: Optional[bytes] = None) -> str:
    """Encrypt a sensitive string (e.g., API key) using AES/Fernet."""
    if not plaintext:
        return ""
    target_key = key or get_active_fernet_key()
    f = Fernet(target_key)
    encrypted_bytes = f.encrypt(plaintext.encode("utf-8"))
    return encrypted_bytes.decode("utf-8")


def decrypt_secret(
    ciphertext: Optional[str],
    multi_fernet: Optional[MultiFernet] = None,
    custom_key: Optional[bytes] = None,
) -> Optional[str]:
    """Decrypt a ciphertext back to plaintext using MultiFernet. Returns None if empty or invalid."""
    if not ciphertext:
        return None
    try:
        if custom_key:
            f = Fernet(custom_key)
            decrypted_bytes = f.decrypt(ciphertext.encode("utf-8"))
            return decrypted_bytes.decode("utf-8")

        mf = multi_fernet or get_multi_fernet()
        decrypted_bytes = mf.decrypt(ciphertext.encode("utf-8"))
        return decrypted_bytes.decode("utf-8")
    except (InvalidToken, Exception) as exc:
        logger.error(f"Failed to decrypt secret: {exc}")
        return None



# Canonical API aliases
decrypt_credential = decrypt_secret
encrypt_credential = encrypt_secret



def rotate_secret(
    ciphertext: str,
    primary_key: Optional[bytes] = None,
    fallback_keys: Optional[list[bytes]] = None,
) -> str:
    """Rotate a ciphertext token so it is encrypted with the primary key.

    Uses MultiFernet.rotate() to decrypt with whichever key matches and re-encrypt
    with the primary key without exposing plaintext.
    """
    if not ciphertext:
        return ""
    mf = get_multi_fernet(primary_key=primary_key, fallback_keys=fallback_keys)
    rotated_bytes = mf.rotate(ciphertext.encode("utf-8"))
    return rotated_bytes.decode("utf-8")


def verify_secret_rotation(
    old_ciphertext: str,
    new_ciphertext: str,
    primary_key: Optional[bytes] = None,
    fallback_keys: Optional[list[bytes]] = None,
) -> bool:
    """Verify that old_ciphertext and new_ciphertext decrypt to the exact same plaintext.

    Plaintext values are compared in memory and never logged, printed, or stored.
    """
    mf_old = get_multi_fernet(primary_key=primary_key, fallback_keys=fallback_keys)
    primary = primary_key or get_active_fernet_key()
    f_new = Fernet(primary)

    try:
        old_plain = mf_old.decrypt(old_ciphertext.encode("utf-8"))
        new_plain = f_new.decrypt(new_ciphertext.encode("utf-8"))
        return old_plain == new_plain
    except Exception as exc:
        logger.error(f"Rotation verification failed: {exc}")
        return False


def mask_secret(secret: Optional[str]) -> str:
    """Return a masked representation of a secret (e.g. 'sk-1...89ab')."""
    if not secret:
        return ""
    if len(secret) <= 8:
        return "********"
    prefix = secret[:4]
    suffix = secret[-4:]
    return f"{prefix}....{suffix}"
