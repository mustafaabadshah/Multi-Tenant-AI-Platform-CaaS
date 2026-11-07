from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    PROJECT_NAME: str = "Multi-Tenant AI Platform-CaaS"
    API_V1_STR: str = "/api/v1"

    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_URL: str = "http://localhost:8000"

    # Security & JWT
    SECRET_KEY: str = "dev-secret-key-change-me-in-production-min-32-bytes-long"
    JWT_SECRET: str = "dev-jwt-secret-key-change-me-in-production-min-32-bytes"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/mmaip_dev"
    DATABASE_SYNC_URL: str = "postgresql://postgres:postgres@localhost:5432/mmaip_dev"

    # Storage & Upload Limits
    STORAGE_BACKEND: str = "local"
    STORAGE_PATH: str = "./data/storage"
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
