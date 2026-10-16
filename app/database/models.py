"""SQLAlchemy 2.x database models for evaluation runs, results, test cases, and metrics."""

from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy entities."""
    pass


class DatasetVersionModel(Base):
    """Versioned evaluation dataset group."""

    __tablename__ = "dataset_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version_tag: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    test_cases: Mapped[List["TestCaseModel"]] = relationship(
        "TestCaseModel", back_populates="dataset_version", cascade="all, delete-orphan"
    )


class TestCaseModel(Base):
    """Individual evaluation test case definition."""

    __tablename__ = "test_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_version_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dataset_versions.id", ondelete="CASCADE"), nullable=False
    )
    case_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    expected_behavior: Mapped[str] = mapped_column(String(64), nullable=False)
    expected_answer: Mapped[str] = mapped_column(Text, nullable=False)
    expected_sources: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    contexts: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    dataset_version: Mapped["DatasetVersionModel"] = relationship(
        "DatasetVersionModel", back_populates="test_cases"
    )


class EvaluationRunModel(Base):
    """Top-level record for an evaluation execution."""

    __tablename__ = "evaluation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    dataset_version: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    app_model: Mapped[str] = mapped_column(String(64), nullable=False)
    evaluator_model: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="COMPLETED", nullable=False)
    passed_quality_gate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    baseline_run_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    git_commit: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    regression_summary: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    results: Mapped[List["EvaluationResultModel"]] = relationship(
        "EvaluationResultModel", back_populates="run", cascade="all, delete-orphan"
    )
    metrics: Mapped[List["EvaluationMetricModel"]] = relationship(
        "EvaluationMetricModel", back_populates="run", cascade="all, delete-orphan"
    )


class EvaluationResultModel(Base):
    """Detailed result per test case evaluated in a run."""

    __tablename__ = "evaluation_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("evaluation_runs.run_id", ondelete="CASCADE"), nullable=False, index=True
    )
    test_case_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    generated_answer: Mapped[str] = mapped_column(Text, nullable=False)
    cited_sources: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    is_refusal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    passed_deterministic: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    deterministic_details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    ragas_faithfulness: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ragas_answer_relevancy: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ragas_context_precision: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    execution_time_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    run: Mapped["EvaluationRunModel"] = relationship("EvaluationRunModel", back_populates="results")


class EvaluationMetricModel(Base):
    """Aggregate metric scores and gate status for a run."""

    __tablename__ = "evaluation_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("evaluation_runs.run_id", ondelete="CASCADE"), nullable=False, index=True
    )
    metric_name: Mapped[str] = mapped_column(String(64), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    run: Mapped["EvaluationRunModel"] = relationship("EvaluationRunModel", back_populates="metrics")
