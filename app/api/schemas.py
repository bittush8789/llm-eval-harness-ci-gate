"""Pydantic request and response models for the FastAPI Evaluation API."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check status and connectivity details."""

    status: str = "ok"
    database_connected: bool
    version: str = "0.1.0"
    environment: str
    offline_mode: bool


class EvaluateRequest(BaseModel):
    """Payload to trigger an evaluation execution."""

    dataset_version: str = Field(default="v1", description="Dataset version folder (e.g. 'v1')")
    baseline_run_id: Optional[str] = Field(
        default=None, description="Optional baseline run ID for regression diffing"
    )
    prompt_version: Optional[str] = Field(default=None, description="Optional prompt version override")
    app_model: Optional[str] = Field(default=None, description="Optional target application model")
    evaluator_model: Optional[str] = Field(default=None, description="Optional evaluator judge model")
    offline_mode: Optional[bool] = Field(
        default=None, description="Whether to run in offline deterministic mock mode"
    )
    git_commit: Optional[str] = Field(default=None, description="Optional git commit hash or branch")


class EvaluateResponse(BaseModel):
    """Result summary returned immediately after synchronous evaluation run."""

    run_id: str
    passed_quality_gate: bool
    total_cases: int
    duration_seconds: float
    metrics: Dict[str, float]
    failure_reasons: List[str]
    report_paths: Dict[str, str]


class EvaluationMetricOut(BaseModel):
    """Metric score details."""

    metric_name: str
    score: float
    threshold: float
    passed: bool


class EvaluationResultOut(BaseModel):
    """Per-test-case evaluation details."""

    test_case_id: str
    question: str
    generated_answer: str
    cited_sources: List[str]
    is_refusal: bool
    passed_deterministic: bool
    ragas_faithfulness: Optional[float]
    ragas_answer_relevancy: Optional[float]
    ragas_context_precision: Optional[float]
    execution_time_ms: float
    error_message: Optional[str]


class EvaluationRunSummary(BaseModel):
    """High-level run metadata."""

    run_id: str
    dataset_version: str
    prompt_version: str
    prompt_hash: str
    app_model: str
    evaluator_model: str
    status: str
    passed_quality_gate: bool
    baseline_run_id: Optional[str]
    git_commit: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]


class EvaluationRunDetail(EvaluationRunSummary):
    """Full evaluation run details including results and metrics."""

    metrics: List[EvaluationMetricOut] = []
    results: List[EvaluationResultOut] = []


class TestCaseOut(BaseModel):
    """Test case schema for API listings."""

    id: str
    category: str
    question: str
    expected_behavior: str
    expected_answer: str
    expected_sources: List[str]
    contexts: List[str]
