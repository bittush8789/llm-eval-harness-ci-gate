"""Initial database schema for AI evaluation platform.

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-10-15 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Dataset Versions Table
    op.create_table(
        "dataset_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("version_tag", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version_tag"),
    )
    op.create_index(op.f("ix_dataset_versions_version_tag"), "dataset_versions", ["version_tag"], unique=True)

    # 2. Test Cases Table
    op.create_table(
        "test_cases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dataset_version_id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("expected_behavior", sa.String(length=64), nullable=False),
        sa.Column("expected_answer", sa.Text(), nullable=False),
        sa.Column("expected_sources", sa.JSON(), nullable=False),
        sa.Column("contexts", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["dataset_version_id"], ["dataset_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_test_cases_case_id"), "test_cases", ["case_id"], unique=False)

    # 3. Evaluation Runs Table
    op.create_table(
        "evaluation_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("dataset_version", sa.String(length=64), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("prompt_hash", sa.String(length=64), nullable=False),
        sa.Column("app_model", sa.String(length=64), nullable=False),
        sa.Column("evaluator_model", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("passed_quality_gate", sa.Boolean(), nullable=False),
        sa.Column("baseline_run_id", sa.String(length=64), nullable=True),
        sa.Column("git_commit", sa.String(length=64), nullable=True),
        sa.Column("regression_summary", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id"),
    )
    op.create_index(op.f("ix_evaluation_runs_run_id"), "evaluation_runs", ["run_id"], unique=True)

    # 4. Evaluation Results Table
    op.create_table(
        "evaluation_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("test_case_id", sa.String(length=64), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("generated_answer", sa.Text(), nullable=False),
        sa.Column("cited_sources", sa.JSON(), nullable=False),
        sa.Column("is_refusal", sa.Boolean(), nullable=False),
        sa.Column("passed_deterministic", sa.Boolean(), nullable=False),
        sa.Column("deterministic_details", sa.JSON(), nullable=False),
        sa.Column("ragas_faithfulness", sa.Float(), nullable=True),
        sa.Column("ragas_answer_relevancy", sa.Float(), nullable=True),
        sa.Column("ragas_context_precision", sa.Float(), nullable=True),
        sa.Column("execution_time_ms", sa.Float(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["evaluation_runs.run_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_evaluation_results_run_id"), "evaluation_results", ["run_id"], unique=False)
    op.create_index(op.f("ix_evaluation_results_test_case_id"), "evaluation_results", ["test_case_id"], unique=False)

    # 5. Evaluation Metrics Table
    op.create_table(
        "evaluation_metrics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("metric_name", sa.String(length=64), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["evaluation_runs.run_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_evaluation_metrics_run_id"), "evaluation_metrics", ["run_id"], unique=False)


def downgrade() -> None:
    op.drop_table("evaluation_metrics")
    op.drop_table("evaluation_results")
    op.drop_table("evaluation_runs")
    op.drop_table("test_cases")
    op.drop_table("dataset_versions")
