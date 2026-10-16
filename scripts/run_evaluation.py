"""CLI runner for executing evaluation suites and enforcing CI quality gates."""

import argparse
import json
import sys
from pathlib import Path
from app.core.config import settings
from app.core.logging import logger
from app.database.connection import init_db
from app.evaluation.evaluator import EvaluationEngine


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Run AI Evaluation & Regression Testing Suite with Quality Gate Enforcement"
    )
    parser.add_argument(
        "--dataset-version",
        default="v1",
        help="Dataset version directory under datasets/ (default: v1)",
    )
    parser.add_argument(
        "--baseline-run-id",
        default=None,
        help="Baseline run ID to compare against for regression detection",
    )
    parser.add_argument(
        "--prompt-version",
        default=None,
        help="Prompt version tag (defaults to settings.APP_PROMPT_VERSION)",
    )
    parser.add_argument(
        "--app-model",
        default=None,
        help="Target application model override (e.g. gemini-3.8-flash)",
    )
    parser.add_argument(
        "--evaluator-model",
        default=None,
        help="Evaluator judge model override (e.g. gemini-3.8-pro)",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        default=False,
        help="Force offline mode using deterministic mock models (no API calls)",
    )
    parser.add_argument(
        "--git-commit",
        default=None,
        help="Associated git commit hash or branch name",
    )
    parser.add_argument(
        "--output-json",
        default=None,
        help="Optional file path to output execution summary JSON",
    )

    args = parser.parse_args()

    # Look for baseline run ID in baseline_lock.json if not passed explicitly
    baseline_id = args.baseline_run_id
    if not baseline_id:
        lock_file = Path("evaluation/baseline_lock.json")
        if lock_file.is_file():
            try:
                with open(lock_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    baseline_id = data.get("baseline_run_id")
                    if baseline_id:
                        logger.info(f"Loaded baseline run ID from {lock_file}: {baseline_id}")
            except Exception as e:
                logger.warning(f"Could not read baseline lock file: {e}")

    # Ensure DB initialized
    try:
        init_db()
    except Exception as e:
        logger.warning(f"Database table verification: {e}")

    engine = EvaluationEngine(offline=args.offline or settings.EVALUATION_OFFLINE_MODE)

    logger.info("==================================================================")
    logger.info("           AI EVALUATION & REGRESSION TESTING RUNNER              ")
    logger.info("==================================================================")

    result = engine.run_evaluation(
        dataset_version=args.dataset_version,
        baseline_run_id=baseline_id,
        prompt_version=args.prompt_version,
        app_model=args.app_model,
        evaluator_model=args.evaluator_model,
        git_commit=args.git_commit,
        sync_db=True,
    )

    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

    print("\n" + "=" * 60)
    print(f"EVALUATION RUN COMPLETE: {result['run_id']}")
    print("=" * 60)
    print(f"Quality Gate Status : {'PASSED (0)' if result['passed_quality_gate'] else 'FAILED (1)'}")
    print(f"Total Cases Tested  : {result['total_cases']}")
    print(f"Duration            : {result['duration_seconds']}s")
    print(f"Markdown Report     : {result['report_paths']['markdown_path']}")
    print(f"JSON Report         : {result['report_paths']['json_path']}")
    print("\nMetrics Summary:")
    for k, v in result["metrics"].items():
        print(f"  - {k:<22}: {v:.3f}")

    if result["failure_reasons"]:
        print("\nQuality Gate Failure Reasons:")
        for r in result["failure_reasons"]:
            print(f"  [X] {r}")

    print("=" * 60 + "\n")

    # Enforce non-zero exit code on quality gate failure
    if not result["passed_quality_gate"]:
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
