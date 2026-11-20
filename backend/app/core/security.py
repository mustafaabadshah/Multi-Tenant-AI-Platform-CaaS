import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import settings

# Initialize Argon2id password hasher with secure defaults
ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MiB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2id."""
    return ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against an Argon2id hash."""
    try:
        return ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(hashed_password: str) -> bool:
    """Check if hash parameters are outdated."""
    try:
        return ph.check_needs_rehash(hashed_password)
    except Exception:
        return True


def generate_session_token() -> str:
    """Return a high-entropy, cryptographically secure raw refresh token."""
    return secrets.token_urlsafe(32)


def hash_session_token(raw_token: str) -> str:
    """Return the SHA-256 hex digest for server-side lookup of a refresh token."""
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()


def create_access_token(
    subject: str,
    claims: dict[str, Any] | None = None,
    session_id: str | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a short-lived access JWT token with unique JTI and session binding."""
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode: dict[str, Any] = {
        "jti": str(uuid.uuid4()),
        "sub": str(subject),
        "iat": now,
        "exp": expire,
        "type": "access",
        "iss": "mmaip-auth",
        "aud": "mmaip-platform",
    }
    if session_id:
        to_encode["sid"] = str(session_id)
    if claims:
        to_encode.update(claims)

    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt



def create_refresh_token(
    subject: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a long-lived refresh JWT token."""
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode: dict[str, Any] = {
        "sub": str(subject),
        "iat": now,
        "exp": expire,
        "type": "refresh",
    }

    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_aud": False},
        )
        return payload
    except jwt.PyJWTError:
        return None

