"""Secret encryption and masking utilities for BYOK API keys and credentials."""

import base64
import hashlib
import logging
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

logger = logging.getLogger("mmaip.security")


def _get_fernet_key() -> bytes:
    """Derive a consistent 32-byte URL-safe base64 key from SECRET_KEY."""
    raw_key = settings.SECRET_KEY.encode("utf-8")
    digest = hashlib.sha256(raw_key).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a sensitive string (e.g., API key) using AES/Fernet."""
    if not plaintext:
        return ""
    key = _get_fernet_key()
    f = Fernet(key)
    encrypted_bytes = f.encrypt(plaintext.encode("utf-8"))
    return encrypted_bytes.decode("utf-8")


def decrypt_secret(ciphertext: Optional[str]) -> Optional[str]:
    """Decrypt a ciphertext back to plaintext. Returns None if empty or invalid."""
    if not ciphertext:
        return None
    try:
        key = _get_fernet_key()
        f = Fernet(key)
        decrypted_bytes = f.decrypt(ciphertext.encode("utf-8"))
        return decrypted_bytes.decode("utf-8")
    except (InvalidToken, Exception) as exc:
        logger.error(f"Failed to decrypt secret: {exc}")
        return None


def mask_secret(secret: Optional[str]) -> str:
    """Return a masked representation of a secret (e.g. 'sk-1...89ab')."""
    if not secret:
        return ""
    if len(secret) <= 8:
        return "********"
    prefix = secret[:4]
    suffix = secret[-4:]
    return f"{prefix}....{suffix}"
