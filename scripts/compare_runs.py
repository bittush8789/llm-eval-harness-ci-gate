"""CLI utility to compare two arbitrary historical evaluation runs."""

import argparse
import sys
from app.core.logging import logger
from app.database.connection import get_db_session, init_db
from app.database.repository import EvaluationRepository
from app.evaluation.baseline import BaselineComparator
from app.evaluation.quality_gate import QualityGate
from app.evaluation.report_generator import ReportGenerator


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Compare two evaluation runs and detect quality regressions.")
    parser.add_argument("--candidate", required=True, help="Candidate run ID")
    parser.add_argument("--baseline", required=True, help="Baseline run ID")
    parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Report output format (default: markdown)",
    )
    parser.add_argument("--output-file", default=None, help="Optional path to write output report")

    args = parser.parse_args()
    init_db()

    with get_db_session() as session:
        repo = EvaluationRepository(session)
        cand_run = repo.get_run(args.candidate)
        base_run = repo.get_run(args.baseline)

        if not cand_run:
            logger.error(f"Candidate run '{args.candidate}' not found.")
            sys.exit(1)
        if not base_run:
            logger.error(f"Baseline run '{args.baseline}' not found.")
            sys.exit(1)

        cand_results = [
            {
                "test_case_id": r.test_case_id,
                "question": r.question,
                "generated_answer": r.generated_answer,
                "cited_sources": r.cited_sources or [],
                "passed_deterministic": r.passed_deterministic,
                "ragas_faithfulness": r.ragas_faithfulness,
                "ragas_answer_relevancy": r.ragas_answer_relevancy,
                "ragas_context_precision": r.ragas_context_precision,
            }
            for r in cand_run.results
        ]
        base_results = [
            {
                "test_case_id": r.test_case_id,
                "question": r.question,
                "generated_answer": r.generated_answer,
                "cited_sources": r.cited_sources or [],
                "passed_deterministic": r.passed_deterministic,
                "ragas_faithfulness": r.ragas_faithfulness,
                "ragas_answer_relevancy": r.ragas_answer_relevancy,
                "ragas_context_precision": r.ragas_context_precision,
            }
            for r in base_run.results
        ]

        cand_metrics = {m.metric_name: m.score for m in cand_run.metrics}
        base_metrics = {m.metric_name: m.score for m in base_run.metrics}

        cand_meta = {
            "run_id": cand_run.run_id,
            "dataset_version": cand_run.dataset_version,
            "prompt_version": cand_run.prompt_version,
            "prompt_hash": cand_run.prompt_hash,
            "app_model": cand_run.app_model,
            "evaluator_model": cand_run.evaluator_model,
        }
        base_meta = {
            "run_id": base_run.run_id,
            "dataset_version": base_run.dataset_version,
            "prompt_version": base_run.prompt_version,
            "prompt_hash": base_run.prompt_hash,
            "app_model": base_run.app_model,
            "evaluator_model": base_run.evaluator_model,
        }

        baseline_summary = BaselineComparator.compare(
            candidate_run_id=cand_run.run_id,
            candidate_results=cand_results,
            candidate_metrics=cand_metrics,
            baseline_run_id=base_run.run_id,
            baseline_results=base_results,
            baseline_metrics=base_metrics,
            candidate_meta=cand_meta,
            baseline_meta=base_meta,
        )

        quality_gate = QualityGate()
        qg_result = quality_gate.evaluate(
            candidate_metrics=cand_metrics,
            deterministic_pass_rates={},
            baseline_summary=baseline_summary,
        )

        generator = ReportGenerator()
        if args.format == "markdown":
            report_str = generator.generate_markdown_report(
                candidate_meta=cand_meta,
                baseline_meta=base_meta,
                quality_gate_result=qg_result,
                baseline_summary=baseline_summary,
                candidate_metrics=cand_metrics,
            )
        else:
            import json
            report_dict = generator.generate_json_report(
                candidate_meta=cand_meta,
                baseline_meta=base_meta,
                quality_gate_result=qg_result,
                baseline_summary=baseline_summary,
                candidate_metrics=cand_metrics,
            )
            report_str = json.dumps(report_dict, indent=2)

        if args.output_file:
            with open(args.output_file, "w", encoding="utf-8") as f:
                f.write(report_str)
            logger.info(f"Comparison report saved to {args.output_file}")
        else:
            print(report_str)


if __name__ == "__main__":
    main()
