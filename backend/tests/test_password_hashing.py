from app.core.security import hash_password, verify_password


def test_argon2id_hashing():
    plain = "SuperSecurePass123!"
    hashed = hash_password(plain)

    assert hashed != plain
    assert hashed.startswith("$argon2id$")
    assert verify_password(plain, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_argon2id_different_salts():
    plain = "Password123!"
    hash1 = hash_password(plain)
    hash2 = hash_password(plain)

    # Different salts must yield different hashes
    assert hash1 != hash2
    assert verify_password(plain, hash1) is True
    assert verify_password(plain, hash2) is True
