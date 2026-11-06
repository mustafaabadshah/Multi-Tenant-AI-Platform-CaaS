-- PostgreSQL Initialization Script for MM AI Platform
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Notice for optional pgvector extension:
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_available_extensions WHERE name = 'vector'
    ) THEN
        CREATE EXTENSION IF NOT EXISTS "vector";
        RAISE NOTICE 'pgvector extension installed successfully.';
    ELSE
        RAISE NOTICE 'pgvector extension not present in base image, continuing with relational core.';
    END IF;
END $$;
