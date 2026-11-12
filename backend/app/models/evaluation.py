"""SQLAlchemy 2.0 models for AI Assistant Evaluation, Datasets, and Benchmarking."""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.assistant import Assistant
    from app.models.tenant import Tenant
    from app.models.user import User


class EvalDataset(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """Evaluation benchmark dataset containing curated test questions and ground-truth references."""

    __tablename__ = "eval_datasets"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
    creator: Mapped[Optional["User"]] = relationship("User")
    items: Mapped[list["EvalDatasetItem"]] = relationship(
        "EvalDatasetItem",
        back_populates="dataset",
        cascade="all, delete-orphan",
        order_by="EvalDatasetItem.created_at",
    )
    runs: Mapped[list["EvalRun"]] = relationship("EvalRun", back_populates="dataset")


class EvalDatasetItem(Base, UUIDPrimaryKeyMixin):
    """Individual question, expected answer, and expected document/chunk references."""

    __tablename__ = "eval_dataset_items"

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("eval_datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    expected_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expected_chunk_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    is_unanswerable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_adversarial: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    item_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    dataset: Mapped["EvalDataset"] = relationship("EvalDataset", back_populates="items")


class EvalRun(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    """Execution run of an evaluation dataset against a specific assistant."""

    __tablename__ = "eval_runs"

    assistant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assistants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("eval_datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="PENDING",
        nullable=False,
        index=True,
    )  # PENDING, RUNNING, COMPLETED, FAILED, CANCELLED
    eval_type: Mapped[str] = mapped_column(
        String(50),
        default="deterministic",
        nullable=False,
    )  # deterministic, llm_judge, hybrid
    judge_provider: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    judge_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    metrics_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
    assistant: Mapped["Assistant"] = relationship("Assistant")
    dataset: Mapped["EvalDataset"] = relationship("EvalDataset", back_populates="runs")
    creator: Mapped[Optional["User"]] = relationship("User")
    results: Mapped[list["EvalRunResult"]] = relationship(
        "EvalRunResult",
        back_populates="run",
        cascade="all, delete-orphan",
    )


class EvalRunResult(Base, UUIDPrimaryKeyMixin):
    """Detailed scores and retrieved sources for a single question evaluation item."""

    __tablename__ = "eval_run_results"

    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("eval_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("eval_dataset_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    generated_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retrieved_chunks: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    citations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    recall_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    mrr_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    faithfulness_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    citation_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    run: Mapped["EvalRun"] = relationship("EvalRun", back_populates="results")
    item: Mapped["EvalDatasetItem"] = relationship("EvalDatasetItem")
