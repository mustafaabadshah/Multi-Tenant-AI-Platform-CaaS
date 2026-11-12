from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    PROJECT_NAME: str = "Multi-Tenant AI Platform-CaaS"
    API_V1_STR: str = "/api/v1"

    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_URL: str = "http://localhost:8000"
    ALLOWED_ORIGINS: str = ""
    ALLOW_DEV_LAN_ORIGINS: bool = False  # Explicit opt-in: enable LAN regex in development only
    CORS_ORIGIN_REGEX: str = r"^https://mmaip-frontend(-[a-zA-Z0-9_-]+)?\.vercel\.app$"

    # Security & JWT
    SECRET_KEY: str = "dev-secret-key-change-me-in-production-min-32-bytes-long"
    PREVIOUS_SECRET_KEYS: str = ""  # Comma-separated previous secret keys for seamless decryption during key rotation
    SECRET_ENCRYPTION_KEY: str = ""  # Dedicated Fernet key material for BYOK secrets; falls back to SECRET_KEY when unset
    JWT_SECRET: str = "dev-jwt-secret-key-change-me-in-production-min-32-bytes"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database & Connection Pooling
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/mmaip_dev"
    DATABASE_SYNC_URL: str = "postgresql://postgres:postgres@localhost:5432/mmaip_dev"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_async_database_url(cls, v: str) -> str:
        if isinstance(v, str):
            if v.startswith("postgres://"):
                return v.replace("postgres://", "postgresql+asyncpg://", 1)
            elif v.startswith("postgresql://") and not v.startswith("postgresql+"):
                return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    @field_validator("DATABASE_SYNC_URL", mode="before")
    @classmethod
    def assemble_sync_database_url(cls, v: str) -> str:
        if isinstance(v, str) and v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql://", 1)
        return v

    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800

    # Storage & Upload Limits
    STORAGE_BACKEND: str = "local"
    STORAGE_PATH: str = "./data/storage"
    S3_BUCKET_NAME: str | None = None
    S3_ENDPOINT_URL: str | None = None
    S3_ACCESS_KEY_ID: str | None = None
    S3_SECRET_ACCESS_KEY: str | None = None
    S3_REGION_NAME: str = "us-east-1"
    MAX_FILE_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MB
    MAX_FILES_PER_REQUEST: int = 10
    MAX_EXTRACTED_TEXT_SIZE_BYTES: int = 20 * 1024 * 1024  # 20 MB
    MAX_ARCHIVE_EXPANSION_BYTES: int = 100 * 1024 * 1024  # 100 MB
    MAX_PROCESSING_DURATION_SECONDS: int = 600
    MAX_DOCUMENT_PAGES: int = 1000

    # OCR Settings
    OCR_ENABLED_DEFAULT: bool = False
    OCR_DEFAULT_PROVIDER: str = "tesseract"
    OCR_DEFAULT_LANGUAGE: str = "eng"
    TESSERACT_CMD: str | None = None
    BADHO_OCR_API_KEY: str | None = None
    BADHO_OCR_API_URL: str | None = None

    # Optional Providers / Cache
    REDIS_URL: str = "redis://localhost:6379/0"
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str | None = None
    QDRANT_COLLECTION_NAME: str = "mmaip_knowledge_chunks"
    PHOENIX_ENABLED: bool = False

    # OmniRoute Gateway Settings
    LLM_BASE_URL: str = "http://localhost:20128/v1"
    OMNIROUTE_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    LLM_DEFAULT_MODEL: str = "auto"

    # Embeddings & Vector Stores (Milestone 03)
    DEFAULT_RETRIEVAL_MODE: str = "hybrid"  # "lexical", "semantic", "hybrid"
    DEFAULT_VECTOR_STORE: str = "pgvector"  # "pgvector", "qdrant", "fts"
    DEFAULT_EMBEDDING_PROVIDER: str = "omniroute"  # "omniroute", "openai", "local", "mock"
    DEFAULT_EMBEDDING_MODEL: str = "text-embedding-3-small"
    DEFAULT_EMBEDDING_DIMENSIONS: int = 1536
    EMBEDDING_BATCH_SIZE: int = 32
    EMBEDDING_TIMEOUT_SECONDS: int = 30
    EMBEDDING_MAX_RETRIES: int = 3
    RRF_K_CONSTANT: int = 60
    RERANKING_ENABLED_DEFAULT: bool = False
    ENCRYPTION_KEY: str | None = None
    MAX_EMBEDDING_TOKENS_PER_REQUEST: int = 8192
    MAX_TOP_K: int = 50


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
