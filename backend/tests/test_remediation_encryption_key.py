"""F1 remediation tests: dedicated BYOK encryption key wiring and rotation fallback."""

from app.core.config import settings
from app.core.crypto import (
    decrypt_secret,
    derive_fernet_key,
    encrypt_secret,
    get_active_fernet_key,
    get_multi_fernet,
)


def test_default_fallback_to_secret_key(monkeypatch):
    """Unset SECRET_ENCRYPTION_KEY keeps deriving the active key from SECRET_KEY."""
    monkeypatch.setattr(settings, "SECRET_ENCRYPTION_KEY", "")

    assert get_active_fernet_key() == derive_fernet_key(settings.SECRET_KEY)
    assert decrypt_secret(encrypt_secret("sk-test-default")) == "sk-test-default"


def test_dedicated_encryption_key(monkeypatch):
    """A non-empty SECRET_ENCRYPTION_KEY replaces SECRET_KEY as active key material."""
    dedicated = "dedicated-byok-encryption-key-material"
    monkeypatch.setattr(settings, "SECRET_ENCRYPTION_KEY", dedicated)

    active = get_active_fernet_key()
    assert active == derive_fernet_key(dedicated)
    assert active != derive_fernet_key(settings.SECRET_KEY)
    assert decrypt_secret(encrypt_secret("sk-test-dedicated")) == "sk-test-dedicated"


def test_rotation_path_with_previous_key_material(monkeypatch):
    """Ciphertext under the SECRET_KEY-derived key decrypts after switching to the dedicated key."""
    plaintext = "sk-test-rotation"
    monkeypatch.setattr(settings, "SECRET_ENCRYPTION_KEY", "")
    legacy_ciphertext = encrypt_secret(plaintext)

    dedicated = "dedicated-byok-encryption-key-material"
    monkeypatch.setattr(settings, "SECRET_ENCRYPTION_KEY", dedicated)
    monkeypatch.setattr(settings, "PREVIOUS_SECRET_KEYS", settings.SECRET_KEY)

    assert get_active_fernet_key() == derive_fernet_key(dedicated)
    assert decrypt_secret(legacy_ciphertext, multi_fernet=get_multi_fernet()) == plaintext
