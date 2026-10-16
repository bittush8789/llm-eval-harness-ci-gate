"""Repository layer for database transactions, runs, results, and metrics."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.logging import logger
from app.database.models import (
    DatasetVersionModel,
    EvaluationMetricModel,
    EvaluationResultModel,
    EvaluationRunModel,
    TestCaseModel,
)


class EvaluationRepository:
    """Encapsulates all persistence operations for the evaluation platform."""

    def __init__(self, session: Session):
        self.session = session

    def sync_dataset_version(
        self, version_tag: str, test_cases_data: List[Dict[str, Any]], description: Optional[str] = None
    ) -> DatasetVersionModel:
        """Register or update a versioned dataset and its test cases."""
        stmt = select(DatasetVersionModel).where(DatasetVersionModel.version_tag == version_tag)
        dataset_ver = self.session.execute(stmt).scalar_one_or_none()

        if not dataset_ver:
            dataset_ver = DatasetVersionModel(
                version_tag=version_tag,
                description=description or f"Dataset version {version_tag}",
            )
            self.session.add(dataset_ver)
            self.session.flush()

        # Check existing test case IDs
        existing_cases = {tc.case_id: tc for tc in dataset_ver.test_cases}
        for item in test_cases_data:
            case_id = item["id"]
            if case_id in existing_cases:
                tc = existing_cases[case_id]
                tc.category = item.get("category", tc.category)
                tc.question = item.get("question", tc.question)
                tc.expected_behavior = item.get("expected_behavior", tc.expected_behavior)
                tc.expected_answer = item.get("expected_answer", tc.expected_answer)
                tc.expected_sources = item.get("expected_sources", tc.expected_sources)
                tc.contexts = item.get("contexts", tc.contexts)
            else:
                tc = TestCaseModel(
                    dataset_version_id=dataset_ver.id,
                    case_id=case_id,
                    category=item.get("category", "normal"),
                    question=item.get("question", ""),
                    expected_behavior=item.get("expected_behavior", "answer_grounded"),
                    expected_answer=item.get("expected_answer", ""),
                    expected_sources=item.get("expected_sources", []),
                    contexts=item.get("contexts", []),
                )
                tc.dataset_version = dataset_ver
                self.session.add(tc)

        self.session.flush()
        return dataset_ver

    def create_or_update_run(
        self,
        run_id: str,
        dataset_version: str,
        prompt_version: str,
        prompt_hash: str,
        app_model: str,
        evaluator_model: str,
        passed_quality_gate: bool,
        status: str = "COMPLETED",
        baseline_run_id: Optional[str] = None,
        git_commit: Optional[str] = None,
        regression_summary: Optional[Dict[str, Any]] = None,
    ) -> EvaluationRunModel:
        """Idempotently create or update an evaluation run record."""
        stmt = select(EvaluationRunModel).where(EvaluationRunModel.run_id == run_id)
        run = self.session.execute(stmt).scalar_one_or_none()

        now = datetime.now(timezone.utc)
        if not run:
            run = EvaluationRunModel(
                run_id=run_id,
                dataset_version=dataset_version,
                prompt_version=prompt_version,
                prompt_hash=prompt_hash,
                app_model=app_model,
                evaluator_model=evaluator_model,
                status=status,
                passed_quality_gate=passed_quality_gate,
                baseline_run_id=baseline_run_id,
                git_commit=git_commit,
                regression_summary=regression_summary,
                created_at=now,
                completed_at=now,
            )
            self.session.add(run)
        else:
            run.dataset_version = dataset_version
            run.prompt_version = prompt_version
            run.prompt_hash = prompt_hash
            run.app_model = app_model
            run.evaluator_model = evaluator_model
            run.status = status
            run.passed_quality_gate = passed_quality_gate
            run.baseline_run_id = baseline_run_id
            run.git_commit = git_commit
            run.regression_summary = regression_summary
            run.completed_at = now

        self.session.flush()
        return run

    def save_results_and_metrics(
        self,
        run_id: str,
        results_data: List[Dict[str, Any]],
        metrics_data: List[Dict[str, Any]],
    ) -> None:
        """Persist individual test case results and aggregate metric evaluations."""
        # Clean existing results if retrying a run
        existing_results = self.session.execute(
            select(EvaluationResultModel).where(EvaluationResultModel.run_id == run_id)
        ).scalars().all()
        for r in existing_results:
            self.session.delete(r)

        existing_metrics = self.session.execute(
            select(EvaluationMetricModel).where(EvaluationMetricModel.run_id == run_id)
        ).scalars().all()
        for m in existing_metrics:
            self.session.delete(m)

        for res in results_data:
            result_row = EvaluationResultModel(
                run_id=run_id,
                test_case_id=res["test_case_id"],
                question=res["question"],
                generated_answer=res["generated_answer"],
                cited_sources=res.get("cited_sources", []),
                is_refusal=res.get("is_refusal", False),
                passed_deterministic=res.get("passed_deterministic", True),
                deterministic_details=res.get("deterministic_details", {}),
                ragas_faithfulness=res.get("ragas_faithfulness"),
                ragas_answer_relevancy=res.get("ragas_answer_relevancy"),
                ragas_context_precision=res.get("ragas_context_precision"),
                execution_time_ms=res.get("execution_time_ms", 0.0),
                error_message=res.get("error_message"),
            )
            self.session.add(result_row)

        for met in metrics_data:
            metric_row = EvaluationMetricModel(
                run_id=run_id,
                metric_name=met["metric_name"],
                score=met["score"],
                threshold=met["threshold"],
                passed=met["passed"],
            )
            self.session.add(metric_row)

        self.session.flush()

    def get_run(self, run_id: str) -> Optional[EvaluationRunModel]:
        """Retrieve evaluation run by unique run_id with results and metrics."""
        stmt = select(EvaluationRunModel).where(EvaluationRunModel.run_id == run_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def list_runs(self, limit: int = 50, offset: int = 0) -> List[EvaluationRunModel]:
        """List historical evaluation runs ordered by creation time descending."""
        stmt = (
            select(EvaluationRunModel)
            .order_by(EvaluationRunModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self.session.execute(stmt).scalars().all())

    def get_latest_successful_run(self) -> Optional[EvaluationRunModel]:
        """Fetch the most recent evaluation run that passed quality gates."""
        stmt = (
            select(EvaluationRunModel)
            .where(EvaluationRunModel.passed_quality_gate.is_(True))
            .order_by(EvaluationRunModel.created_at.desc())
            .limit(1)
        )
        return self.session.execute(stmt).scalar_one_or_none()
