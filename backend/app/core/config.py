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
    PROJECT_NAME: str = "MM AI Platform"
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

    # Storage
    STORAGE_BACKEND: str = "local"
    STORAGE_PATH: str = "./data/storage"

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


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
