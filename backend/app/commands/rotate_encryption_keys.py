"""BYOK Encryption Key Rotation Utility

Safely rotates AES-128-CBC/Fernet encrypted secrets across tenant retrieval configurations.
Ensures zero-downtime transition, verification in memory, and clean rollback on error.
"""

import argparse
import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import (
    derive_fernet_key,
    get_active_fernet_key,
    get_previous_fernet_keys,
    rotate_secret,
    verify_secret_rotation,
)
from app.database.session import async_session_maker
from app.models.knowledge import RetrievalConfig

logger = logging.getLogger("mmaip.key_rotation")


@dataclass
class KeyRotationResult:
    total_records_examined: int = 0
    records_rotated: int = 0
    records_verified: int = 0
    records_skipped_empty: int = 0
    failed_rotations: int = 0
    success: bool = False


async def rotate_tenant_byok_secrets(
    session: AsyncSession,
    primary_key: Optional[bytes] = None,
    fallback_keys: Optional[list[bytes]] = None,
) -> KeyRotationResult:
    """Rotate all encrypted BYOK credentials in the database to the primary encryption key.

    Requirements enforced:
    - Never exposes plaintext in logs or exceptions.
    - Decrypts with fallback keys and re-encrypts with primary key using MultiFernet.
    - Verifies re-encrypted ciphertext in memory before committing.
    - Idempotent: Can be run multiple times safely.
    """
    active_key = primary_key or get_active_fernet_key()
    previous = fallback_keys if fallback_keys is not None else get_previous_fernet_keys()

    result = KeyRotationResult()

    stmt = select(RetrievalConfig).where(RetrievalConfig.encrypted_api_key.is_not(None))
    res = await session.execute(stmt)
    configs = res.scalars().all()

    for config in configs:
        result.total_records_examined += 1
        raw_ciphertext = config.encrypted_api_key
        if not raw_ciphertext:
            result.records_skipped_empty += 1
            continue

        try:
            rotated = rotate_secret(
                raw_ciphertext,
                primary_key=active_key,
                fallback_keys=previous,
            )

            # In-memory cryptographic roundtrip verification
            verified = verify_secret_rotation(
                old_ciphertext=raw_ciphertext,
                new_ciphertext=rotated,
                primary_key=active_key,
                fallback_keys=previous,
            )

            if not verified:
                result.failed_rotations += 1
                logger.error(
                    f"Rotation verification failed for config_id={config.id}, tenant_id={config.tenant_id}"
                )
                continue

            config.encrypted_api_key = rotated
            result.records_rotated += 1
            result.records_verified += 1
        except Exception as exc:
            result.failed_rotations += 1
            logger.error(
                f"Error rotating secret for config_id={config.id}: {type(exc).__name__}"
            )

    if result.failed_rotations == 0:
        await session.commit()
        result.success = True
        logger.info(
            f"Key rotation successful. Examined={result.total_records_examined}, "
            f"Rotated={result.records_rotated}, Verified={result.records_verified}"
        )
    else:
        await session.rollback()
        result.success = False
        logger.error(
            f"Key rotation aborted due to {result.failed_rotations} failures. Transaction rolled back."
        )

    return result


async def main():
    parser = argparse.ArgumentParser(description="Rotate BYOK encryption keys in the database.")
    parser.add_argument(
        "--new-key",
        type=str,
        default=None,
        help="Optional new SECRET_KEY string material (defaults to settings.SECRET_KEY)",
    )
    parser.add_argument(
        "--previous-keys",
        type=str,
        default=None,
        help="Optional comma-separated previous SECRET_KEY strings",
    )
    args = parser.parse_args()

    primary_key = derive_fernet_key(args.new_key) if args.new_key else None
    fallback_keys = (
        [derive_fernet_key(k.strip()) for k in args.previous_keys.split(",") if k.strip()]
        if args.previous_keys
        else None
    )

    async with async_session_maker() as session:
        result = await rotate_tenant_byok_secrets(
            session=session,
            primary_key=primary_key,
            fallback_keys=fallback_keys,
        )
        print(f"Key Rotation Complete: Success={result.success}, Rotated={result.records_rotated}")


if __name__ == "__main__":
    asyncio.run(main())
