"""FastAPI route handlers for evaluation triggers, run inspections, and reports."""

from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.api.schemas import (
    EvaluateRequest,
    EvaluateResponse,
    EvaluationMetricOut,
    EvaluationResultOut,
    EvaluationRunDetail,
    EvaluationRunSummary,
    HealthResponse,
    TestCaseOut,
)
from app.core.config import settings
from app.core.logging import logger
from app.database.connection import get_db
from app.database.repository import EvaluationRepository
from app.evaluation.dataset_loader import DatasetLoader
from app.evaluation.evaluator import EvaluationEngine

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["Health"])
def health_check(db: Session = Depends(get_db)):
    """Health check endpoint validating service and database status."""
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")

    return HealthResponse(
        status="ok" if db_ok else "degraded",
        database_connected=db_ok,
        version="0.1.0",
        environment=settings.ENVIRONMENT,
        offline_mode=settings.EVALUATION_OFFLINE_MODE,
    )


@router.post(
    "/evaluate",
    response_model=EvaluateResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Evaluation"],
)
def run_evaluation_endpoint(payload: EvaluateRequest):
    """Trigger synchronous evaluation against a specified dataset version and baseline."""
    try:
        engine = EvaluationEngine(offline=payload.offline_mode)
        result = engine.run_evaluation(
            dataset_version=payload.dataset_version,
            baseline_run_id=payload.baseline_run_id,
            prompt_version=payload.prompt_version,
            app_model=payload.app_model,
            evaluator_model=payload.evaluator_model,
            git_commit=payload.git_commit,
            sync_db=True,
        )
        return EvaluateResponse(
            run_id=result["run_id"],
            passed_quality_gate=result["passed_quality_gate"],
            total_cases=result["total_cases"],
            duration_seconds=result["duration_seconds"],
            metrics=result["metrics"],
            failure_reasons=result["failure_reasons"],
            report_paths=result["report_paths"],
        )
    except FileNotFoundError as fnfe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(fnfe))
    except Exception as e:
        logger.error(f"Evaluation trigger failed: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/evaluations", response_model=List[EvaluationRunSummary], tags=["Evaluation"])
def list_evaluations(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """Retrieve historical evaluation runs ordered by creation timestamp."""
    repo = EvaluationRepository(db)
    runs = repo.list_runs(limit=limit, offset=offset)
    return [
        EvaluationRunSummary(
            run_id=r.run_id,
            dataset_version=r.dataset_version,
            prompt_version=r.prompt_version,
            prompt_hash=r.prompt_hash,
            app_model=r.app_model,
            evaluator_model=r.evaluator_model,
            status=r.status,
            passed_quality_gate=r.passed_quality_gate,
            baseline_run_id=r.baseline_run_id,
            git_commit=r.git_commit,
            created_at=r.created_at,
            completed_at=r.completed_at,
        )
        for r in runs
    ]


@router.get("/evaluations/{run_id}", response_model=EvaluationRunDetail, tags=["Evaluation"])
def get_evaluation_detail(run_id: str, db: Session = Depends(get_db)):
    """Retrieve full evaluation run details including test case outcomes and metric scores."""
    repo = EvaluationRepository(db)
    run = repo.get_run(run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found.")

    return EvaluationRunDetail(
        run_id=run.run_id,
        dataset_version=run.dataset_version,
        prompt_version=run.prompt_version,
        prompt_hash=run.prompt_hash,
        app_model=run.app_model,
        evaluator_model=run.evaluator_model,
        status=run.status,
        passed_quality_gate=run.passed_quality_gate,
        baseline_run_id=run.baseline_run_id,
        git_commit=run.git_commit,
        created_at=run.created_at,
        completed_at=run.completed_at,
        metrics=[
            EvaluationMetricOut(
                metric_name=m.metric_name,
                score=m.score,
                threshold=m.threshold,
                passed=m.passed,
            )
            for m in run.metrics
        ],
        results=[
            EvaluationResultOut(
                test_case_id=res.test_case_id,
                question=res.question,
                generated_answer=res.generated_answer,
                cited_sources=res.cited_sources or [],
                is_refusal=res.is_refusal,
                passed_deterministic=res.passed_deterministic,
                ragas_faithfulness=res.ragas_faithfulness,
                ragas_answer_relevancy=res.ragas_answer_relevancy,
                ragas_context_precision=res.ragas_context_precision,
                execution_time_ms=res.execution_time_ms,
                error_message=res.error_message,
            )
            for res in run.results
        ],
    )


@router.get("/evaluations/{run_id}/report", tags=["Evaluation"])
def get_evaluation_report(
    run_id: str,
    format: str = Query(default="markdown", pattern="^(markdown|json)$"),
):
    """Retrieve generated regression report for an evaluation run in Markdown or JSON format."""
    reports_dir = Path(__file__).resolve().parent.parent.parent / "reports"
    ext = "md" if format == "markdown" else "json"
    file_path = reports_dir / f"regression_report_{run_id}.{ext}"

    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report file not found for run '{run_id}'.",
        )

    content = file_path.read_text(encoding="utf-8")
    media_type = "text/markdown" if format == "markdown" else "application/json"
    return Response(content=content, media_type=media_type)


@router.get("/test-cases", response_model=List[TestCaseOut], tags=["Datasets"])
def list_test_cases(version: str = Query(default="v1")):
    """List available evaluation test cases for the specified dataset version."""
    try:
        loader = DatasetLoader()
        cases = loader.load_version(version)
        return [
            TestCaseOut(
                id=c.id,
                category=c.category,
                question=c.question,
                expected_behavior=c.expected_behavior,
                expected_answer=c.expected_answer,
                expected_sources=c.expected_sources,
                contexts=c.contexts,
            )
            for c in cases
        ]
    except FileNotFoundError as fnfe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(fnfe))
