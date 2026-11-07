from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.knowledge import RetrievalConfig  # noqa: F401


class ProviderConnection(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "provider_connections"

    provider_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # e.g., "omniroute", "local_ollama"
    base_url: Mapped[str] = mapped_column(
        String(255), default="http://localhost:20128/v1", nullable=False
    )
    api_key_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class EmbeddingConfig(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "embedding_configs"

    model_name: Mapped[str] = mapped_column(
        String(100), default="text-embedding-3-small", nullable=False
    )
    dimensions: Mapped[int] = mapped_column(Integer, default=1536, nullable=False)
    batch_size: Mapped[int] = mapped_column(Integer, default=32, nullable=False)


class VectorStoreConfig(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "vector_store_configs"

    store_type: Mapped[str] = mapped_column(
        String(50), default="postgresql_pgvector", nullable=False
    )
    endpoint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    collection_name: Mapped[str] = mapped_column(String(100), nullable=False)

