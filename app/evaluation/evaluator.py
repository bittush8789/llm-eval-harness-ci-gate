"""Evaluation engine orchestrating RAG invocations, assertions, Ragas metrics, persistence, and reporting."""

import time
import uuid
from typing import Any, Dict, List, Optional
from app.chains.rag_chain import RAGChain
from app.core.config import settings
from app.core.logging import logger
from app.database.connection import get_db_session
from app.database.repository import EvaluationRepository
from app.evaluation.baseline import BaselineComparator, BaselineComparisonSummary
from app.evaluation.dataset_loader import DatasetLoader, TestCaseSchema
from app.evaluation.deterministic_checks import DeterministicChecker
from app.evaluation.quality_gate import QualityGate, QualityGateResult
from app.evaluation.ragas_metrics import RagasEvaluator
from app.evaluation.report_generator import ReportGenerator


class EvaluationEngine:
    """Master orchestrator executing complete end-to-end evaluation cycles."""

    def __init__(
        self,
        dataset_loader: Optional[DatasetLoader] = None,
        rag_chain: Optional[RAGChain] = None,
        ragas_evaluator: Optional[RagasEvaluator] = None,
        quality_gate: Optional[QualityGate] = None,
        report_generator: Optional[ReportGenerator] = None,
        offline: Optional[bool] = None,
    ):
        self.offline = offline if offline is not None else settings.EVALUATION_OFFLINE_MODE
        self.dataset_loader = dataset_loader or DatasetLoader()
        self.rag_chain = rag_chain or RAGChain(offline=self.offline)
        self.ragas_evaluator = ragas_evaluator or RagasEvaluator(offline=self.offline)
        self.quality_gate = quality_gate or QualityGate()
        self.report_generator = report_generator or ReportGenerator()

    def run_evaluation(
        self,
        dataset_version: str = "v1",
        baseline_run_id: Optional[str] = None,
        prompt_version: Optional[str] = None,
        app_model: Optional[str] = None,
        evaluator_model: Optional[str] = None,
        git_commit: Optional[str] = None,
        sync_db: bool = True,
    ) -> Dict[str, Any]:
        """Execute evaluation on the target dataset version and compare with baseline."""
        run_id = f"eval_{uuid.uuid4().hex[:12]}"
        start_time = time.time()
        logger.info(f"Starting evaluation run {run_id} (dataset={dataset_version}, baseline={baseline_run_id})")

        # 1. Load and validate evaluation dataset
        test_cases: List[TestCaseSchema] = self.dataset_loader.load_version(dataset_version)

        # 2. Invoke application chain and collect results
        case_results: List[Dict[str, Any]] = []
        schema_passes = 0
        citation_passes = 0
        refusal_passes = 0
        refusal_cases_total = 0
        all_deterministic_passes = 0

        faithfulness_scores: List[float] = []
        relevancy_scores: List[float] = []
        precision_scores: List[float] = []

        for tc in test_cases:
            t0 = time.time()
            rag_response = self.rag_chain.invoke(question=tc.question, contexts=tc.contexts)
            elapsed_ms = round((time.time() - t0) * 1000.0, 2)

            # Deterministic checks
            det_result = DeterministicChecker.evaluate(rag_response, tc)
            if det_result.checks["schema_validity"].passed:
                schema_passes += 1
            if det_result.checks["citation_presence"].passed:
                citation_passes += 1
            if det_result.passed:
                all_deterministic_passes += 1

            expects_refusal = (
                tc.expected_behavior == "refusal"
                or tc.category == "unanswerable"
                or (tc.category == "adversarial" and not tc.expected_sources)
            )
            if expects_refusal:
                refusal_cases_total += 1
                if det_result.checks["refusal_behavior"].passed:
                    refusal_passes += 1

            # Ragas metric scores
            ragas_res = self.ragas_evaluator.evaluate_case(
                test_case_id=tc.id,
                question=tc.question,
                answer=rag_response.answer,
                contexts=tc.contexts,
                expected_answer=tc.expected_answer,
                is_refusal=rag_response.is_refusal,
                passed_deterministic=det_result.passed,
            )

            faithfulness_scores.append(ragas_res.faithfulness)
            relevancy_scores.append(ragas_res.answer_relevancy)
            precision_scores.append(ragas_res.context_precision)

            case_results.append(
                {
                    "test_case_id": tc.id,
                    "question": tc.question,
                    "generated_answer": rag_response.answer,
                    "cited_sources": rag_response.source_identifiers,
                    "is_refusal": rag_response.is_refusal,
                    "passed_deterministic": det_result.passed,
                    "deterministic_details": {k: v.model_dump() for k, v in det_result.checks.items()},
                    "ragas_faithfulness": ragas_res.faithfulness,
                    "ragas_answer_relevancy": ragas_res.answer_relevancy,
                    "ragas_context_precision": ragas_res.context_precision,
                    "execution_time_ms": elapsed_ms,
                    "error_message": None if det_result.passed else "Deterministic check failure",
                }
            )

        total_cases = len(test_cases)
        avg_faithfulness = round(sum(faithfulness_scores) / max(1, total_cases), 3)
        avg_relevancy = round(sum(relevancy_scores) / max(1, total_cases), 3)
        avg_precision = round(sum(precision_scores) / max(1, total_cases), 3)
        schema_rate = round(schema_passes / max(1, total_cases), 3)
        citation_rate = round(citation_passes / max(1, total_cases), 3)
        refusal_rate = (
            round(refusal_passes / max(1, refusal_cases_total), 3) if refusal_cases_total > 0 else 1.0
        )

        candidate_metrics: Dict[str, float] = {
            "faithfulness": avg_faithfulness,
            "answer_relevance": avg_relevancy,
            "context_precision": avg_precision,
            "citation_validity": citation_rate,
            "refusal_accuracy": refusal_rate,
            "schema_validity": schema_rate,
        }

        # 3. Retrieve baseline run data if available
        baseline_results: Optional[List[Dict[str, Any]]] = None
        baseline_metrics: Optional[Dict[str, float]] = None
        baseline_meta: Optional[Dict[str, Any]] = None

        if sync_db and baseline_run_id:
            try:
                with get_db_session() as session:
                    repo = EvaluationRepository(session)
                    b_run = repo.get_run(baseline_run_id)
                    if b_run:
                        baseline_meta = {
                            "run_id": b_run.run_id,
                            "dataset_version": b_run.dataset_version,
                            "prompt_version": b_run.prompt_version,
                            "prompt_hash": b_run.prompt_hash,
                            "app_model": b_run.app_model,
                            "evaluator_model": b_run.evaluator_model,
                        }
                        baseline_results = [
                            {
                                "test_case_id": r.test_case_id,
                                "generated_answer": r.generated_answer,
                                "cited_sources": r.cited_sources,
                                "passed_deterministic": r.passed_deterministic,
                                "ragas_faithfulness": r.ragas_faithfulness,
                                "ragas_answer_relevancy": r.ragas_answer_relevancy,
                                "ragas_context_precision": r.ragas_context_precision,
                            }
                            for r in b_run.results
                        ]
                        baseline_metrics = {m.metric_name: m.score for m in b_run.metrics}
                    else:
                        logger.warning(f"Baseline run ID '{baseline_run_id}' not found in database.")
            except Exception as dbe:
                logger.warning(f"Unable to query baseline from database: {dbe}")

        candidate_meta = {
            "run_id": run_id,
            "dataset_version": dataset_version,
            "prompt_version": prompt_version or settings.APP_PROMPT_VERSION,
            "prompt_hash": settings.get_prompt_hash(),
            "app_model": app_model or settings.APP_LLM_MODEL,
            "evaluator_model": evaluator_model or settings.EVALUATOR_LLM_MODEL,
            "git_commit": git_commit,
        }

        # 4. Compare with baseline
        baseline_summary: BaselineComparisonSummary = BaselineComparator.compare(
            candidate_run_id=run_id,
            candidate_results=case_results,
            candidate_metrics=candidate_metrics,
            baseline_run_id=baseline_run_id,
            baseline_results=baseline_results,
            baseline_metrics=baseline_metrics,
            candidate_meta=candidate_meta,
            baseline_meta=baseline_meta,
        )

        # 5. Evaluate Quality Gate
        qg_result: QualityGateResult = self.quality_gate.evaluate(
            candidate_metrics=candidate_metrics,
            deterministic_pass_rates={
                "citation_validity": citation_rate,
                "refusal_accuracy": refusal_rate,
                "schema_validity": schema_rate,
            },
            baseline_summary=baseline_summary,
        )

        # 6. Generate and save reports
        report_paths = self.report_generator.save_reports(
            candidate_meta=candidate_meta,
            baseline_meta=baseline_meta,
            quality_gate_result=qg_result,
            baseline_summary=baseline_summary,
            candidate_metrics=candidate_metrics,
        )

        # 7. Persist to PostgreSQL / Database
        if sync_db:
            try:
                with get_db_session() as session:
                    repo = EvaluationRepository(session)
                    # Sync dataset metadata and cases
                    repo.sync_dataset_version(
                        version_tag=dataset_version,
                        test_cases_data=[tc.model_dump() for tc in test_cases],
                    )

                    # Build metrics list for DB
                    metrics_records = []
                    for met_name, score in candidate_metrics.items():
                        thresh = self.quality_gate.minimum_metrics.get(met_name, 0.8)
                        metrics_records.append(
                            {
                                "metric_name": met_name,
                                "score": score,
                                "threshold": thresh,
                                "passed": score >= thresh,
                            }
                        )

                    # Create run and save results
                    repo.create_or_update_run(
                        run_id=run_id,
                        dataset_version=dataset_version,
                        prompt_version=candidate_meta["prompt_version"],
                        prompt_hash=candidate_meta["prompt_hash"],
                        app_model=candidate_meta["app_model"],
                        evaluator_model=candidate_meta["evaluator_model"],
                        passed_quality_gate=qg_result.passed,
                        status="PASSED" if qg_result.passed else "FAILED",
                        baseline_run_id=baseline_run_id,
                        git_commit=git_commit,
                        regression_summary={
                            "new_failures": baseline_summary.new_failures,
                            "recovered": baseline_summary.recovered,
                            "metric_deltas": baseline_summary.metric_deltas,
                        },
                    )

                    repo.save_results_and_metrics(
                        run_id=run_id,
                        results_data=case_results,
                        metrics_data=metrics_records,
                    )
                logger.info(f"Evaluation run {run_id} persisted to database successfully.")
            except Exception as e:
                logger.error(f"Failed to persist evaluation run to database: {e}", exc_info=True)

        duration = round(time.time() - start_time, 2)
        logger.info(
            f"Evaluation {run_id} finished in {duration}s. Quality Gate Passed: {qg_result.passed}."
        )

        return {
            "run_id": run_id,
            "passed_quality_gate": qg_result.passed,
            "failure_reasons": qg_result.failure_reasons,
            "metrics": candidate_metrics,
            "baseline_summary": baseline_summary.model_dump(),
            "report_paths": report_paths,
            "total_cases": total_cases,
            "duration_seconds": duration,
        }
