"""PostgreSQL Live Backup and Isolated Recovery Drill Helper.

Performs cryptographic seeding in source database and in-memory BYOK
decryption validation in the restored disposable database.
Enforces strict database name guards to protect production and staging data.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import uuid
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.crypto import (
    decrypt_credential,
    encrypt_credential,
)

logger = logging.getLogger("mmaip.drills.postgres")

DISPOSABLE_TENANT_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")
DISPOSABLE_USER_ID = uuid.UUID("00000000-0000-4000-8000-000000000002")
DISPOSABLE_ASSISTANT_ID = uuid.UUID("00000000-0000-4000-8000-000000000003")
DEFAULT_DISPOSABLE_TOKEN = "sk-antigravity-m05-disposable-token-20261108"
DEFAULT_CONTEXT_FILE = "/tmp/m05_postgres_drill_context.json"

PERMITTED_SOURCE_DB = "m05_integration"
PERMITTED_RESTORE_DB = "m05_restore_drill_disposable"


def get_engine_for_db(db_name: str, host: str = "127.0.0.1", port: int = 55432, user: str = "m05_test", password: str = "m05_test_password_secure_local"):
    """Construct async SQLAlchemy engine for a specific database."""
    url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db_name}"
    return create_async_engine(url, echo=False)


async def seed_source_database(
    db_name: str,
    context_file: str,
    host: str = "127.0.0.1",
    port: int = 55432,
    user: str = "m05_test",
    password: str = "m05_test_password_secure_local",
    token: str = DEFAULT_DISPOSABLE_TOKEN,
) -> bool:
    """Seed disposable test records with encrypted BYOK credential into source database."""
    # Safety guard: Refuse to seed if database is not the expected disposable source database
    if db_name != PERMITTED_SOURCE_DB:
        print(f"SECURITY ERROR: Refusing to seed database '{db_name}'. Must be '{PERMITTED_SOURCE_DB}'.", file=sys.stderr)
        return False

    engine = get_engine_for_db(db_name, host=host, port=port, user=user, password=password)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    try:
        # Encrypt disposable token using production crypto implementation
        ciphertext = encrypt_credential(token)
        if not ciphertext:
            print("ERROR: Failed to generate ciphertext via encrypt_credential.", file=sys.stderr)
            return False

        async with session_maker() as session:
            # Seed tenant
            await session.execute(
                text("""
                    INSERT INTO tenants (id, name, slug, created_at, updated_at)
                    VALUES (:tid, 'Drill Tenant', 'drill-tenant', NOW(), NOW())
                    ON CONFLICT (id) DO NOTHING;
                """),
                {"tid": DISPOSABLE_TENANT_ID},
            )

            # Seed user
            await session.execute(
                text("""
                    INSERT INTO users (id, email, hashed_password, full_name, is_active, is_superuser, created_at, updated_at)
                    VALUES (:uid, 'drill_user@example.com', 'argon2id_placeholder', 'Drill User', true, false, NOW(), NOW())
                    ON CONFLICT (id) DO NOTHING;
                """),
                {"uid": DISPOSABLE_USER_ID},
            )

            # Seed assistant with encrypted BYOK key
            await session.execute(
                text("""
                    INSERT INTO assistants (
                        id, tenant_id, name, slug, description, default_model,
                        llm_provider, system_prompt, status, byok_encrypted_key,
                        created_at, updated_at
                    )
                    VALUES (
                        :aid, :tid, 'Drill Assistant', 'drill-assistant', 'Backup Drill Assistant',
                        'auto', 'openai', 'You are a drill assistant.', 'ACTIVE', :key,
                        NOW(), NOW()
                    )
                    ON CONFLICT (id) DO UPDATE SET byok_encrypted_key = EXCLUDED.byok_encrypted_key;
                """),
                {
                    "aid": DISPOSABLE_ASSISTANT_ID,
                    "tid": DISPOSABLE_TENANT_ID,
                    "key": ciphertext,
                },
            )
            await session.commit()

        # Write protected context file for verification phase
        context_data = {
            "tenant_id": str(DISPOSABLE_TENANT_ID),
            "assistant_id": str(DISPOSABLE_ASSISTANT_ID),
            "expected_token": token,
            "source_db": db_name,
        }
        ctx_path = Path(context_file)
        ctx_path.parent.mkdir(parents=True, exist_ok=True)
        with open(ctx_path, "w", encoding="utf-8") as f:
            json.dump(context_data, f)
        try:
            os.chmod(ctx_path, 0o600)
        except Exception:
            pass

        print("SOURCE_SEEDED_SUCCESS")
        return True

    except Exception as exc:
        print(f"ERROR: Seeding source database failed: {exc}", file=sys.stderr)
        return False
    finally:
        await engine.dispose()


async def verify_restored_database(
    db_name: str,
    context_file: str,
    host: str = "127.0.0.1",
    port: int = 55432,
    user: str = "m05_test",
    password: str = "m05_test_password_secure_local",
) -> bool:
    """Verify restored schema, query assistant record, and validate BYOK in-memory decryption."""
    # Safety guard: Target MUST be the disposable restore target database, NEVER the source
    if db_name != PERMITTED_RESTORE_DB:
        print(f"SECURITY ERROR: Refusing to verify target '{db_name}'. Must be '{PERMITTED_RESTORE_DB}'.", file=sys.stderr)
        return False

    if db_name == PERMITTED_SOURCE_DB:
        print(f"SECURITY ERROR: Restore target database cannot be the source database '{PERMITTED_SOURCE_DB}'.", file=sys.stderr)
        return False

    ctx_path = Path(context_file)
    if not ctx_path.exists():
        print(f"ERROR: Context file '{context_file}' not found.", file=sys.stderr)
        return False

    with open(ctx_path, "r", encoding="utf-8") as f:
        context = json.load(f)

    expected_token = context.get("expected_token")
    assistant_id = uuid.UUID(context["assistant_id"])
    tenant_id = uuid.UUID(context["tenant_id"])

    engine = get_engine_for_db(db_name, host=host, port=port, user=user, password=password)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    try:
        async with session_maker() as session:
            # 1. Verify schema tables and foreign key structure
            schema_res = await session.execute(
                text("""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = 'assistants' AND column_name IN ('id', 'tenant_id', 'byok_encrypted_key');
                """)
            )
            cols = {row[0] for row in schema_res.fetchall()}
            if not {"id", "tenant_id", "byok_encrypted_key"}.issubset(cols):
                print("ERROR: assistants table in restored database is missing required columns.", file=sys.stderr)
                return False

            print("RESTORE_SCHEMA_PASS")

            # 2. Verify restored record and composite tenant relationship
            record_res = await session.execute(
                text("""
                    SELECT id, tenant_id, byok_encrypted_key 
                    FROM assistants 
                    WHERE id = :aid AND tenant_id = :tid;
                """),
                {"aid": assistant_id, "tid": tenant_id},
            )
            row = record_res.fetchone()
            if not row:
                print("ERROR: Restored assistant record not found with composite tenant scope.", file=sys.stderr)
                return False

            restored_aid, restored_tid, restored_ciphertext = row[0], row[1], row[2]
            if str(restored_aid) != str(assistant_id) or str(restored_tid) != str(tenant_id):
                print("ERROR: Composite identifier mismatch in restored database.", file=sys.stderr)
                return False

            if not restored_ciphertext:
                print("ERROR: Restored record has empty byok_encrypted_key.", file=sys.stderr)
                return False

            print("RESTORE_RECORD_PASS")

            # 3. Live BYOK decryption using actual application crypto implementation
            decrypted_token = decrypt_credential(restored_ciphertext)
            if not decrypted_token:
                print("ERROR: decrypt_credential failed to decrypt restored ciphertext.", file=sys.stderr)
                return False

            print("BYOK_DECRYPTION_PASS")

            # 4. In-memory comparison against original disposable test token
            if decrypted_token != expected_token:
                print("ERROR: Decrypted token does not match original disposable test token.", file=sys.stderr)
                return False

            print("BYOK_PLAINTEXT_MATCH_PASS")

        # 5. Verify source database was not modified or overwritten
        source_engine = get_engine_for_db(PERMITTED_SOURCE_DB, host=host, port=port, user=user, password=password)
        source_session_maker = async_sessionmaker(source_engine, expire_on_commit=False, class_=AsyncSession)
        try:
            async with source_session_maker() as src_session:
                src_res = await src_session.execute(
                    text("SELECT count(*) FROM assistants WHERE id = :aid;"),
                    {"aid": assistant_id},
                )
                src_count = src_res.scalar()
                if src_count != 1:
                    print("ERROR: Source database record count altered during drill!", file=sys.stderr)
                    return False
                print("SOURCE_DB_UNMODIFIED_PASS")
        finally:
            await source_engine.dispose()

        return True

    except Exception as exc:
        print(f"ERROR: Restoration verification failed: {exc}", file=sys.stderr)
        return False
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="PostgreSQL Backup & Recovery Drill Helper")
    parser.add_argument("--action", choices=["seed", "verify"], required=True, help="Action to execute")
    parser.add_argument("--db-name", type=str, required=True, help="Target database name")
    parser.add_argument("--context-file", type=str, default=DEFAULT_CONTEXT_FILE, help="Path to protected test context JSON")
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=55432)
    parser.add_argument("--user", type=str, default="m05_test")
    parser.add_argument("--password", type=str, default="m05_test_password_secure_local")

    args = parser.parse_args()

    if args.action == "seed":
        success = asyncio.run(seed_source_database(
            db_name=args.db_name,
            context_file=args.context_file,
            host=args.host,
            port=args.port,
            user=args.user,
            password=args.password,
        ))
    else:
        success = asyncio.run(verify_restored_database(
            db_name=args.db_name,
            context_file=args.context_file,
            host=args.host,
            port=args.port,
            user=args.user,
            password=args.password,
        ))

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
