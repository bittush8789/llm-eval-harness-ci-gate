"""Bootstrap script to execute or designate an initial baseline evaluation run."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from app.core.config import settings
from app.core.logging import logger
from app.database.connection import get_db_session, init_db
from app.database.repository import EvaluationRepository
from app.evaluation.evaluator import EvaluationEngine


def main():
    parser = argparse.ArgumentParser(
        description="Bootstrap or designate the reference baseline evaluation run."
    )
    parser.add_argument(
        "--dataset-version",
        default="v1",
        help="Dataset version to use for baseline initialization (default: v1)",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        default=False,
        help="Execute offline using mock models",
    )
    parser.add_argument(
        "--from-run-id",
        default=None,
        help="Designate an existing historical run ID as the new baseline",
    )
    parser.add_argument(
        "--lock-file",
        default="evaluation/baseline_lock.json",
        help="Path to baseline lock file (default: evaluation/baseline_lock.json)",
    )

    args = parser.parse_args()
    init_db()

    lock_path = Path(args.lock_file)
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    if args.from_run_id:
        target_run_id = args.from_run_id
        with get_db_session() as session:
            repo = EvaluationRepository(session)
            run = repo.get_run(target_run_id)
            if not run:
                raise ValueError(f"Run ID '{target_run_id}' not found in database.")
            dataset_version = run.dataset_version
            prompt_version = run.prompt_version
        logger.info(f"Designating existing run {target_run_id} as baseline.")
    else:
        logger.info("Executing initial baseline evaluation run...")
        engine = EvaluationEngine(offline=args.offline or settings.EVALUATION_OFFLINE_MODE)
        result = engine.run_evaluation(
            dataset_version=args.dataset_version,
            baseline_run_id=None,
            sync_db=True,
        )
        target_run_id = result["run_id"]
        dataset_version = args.dataset_version
        prompt_version = settings.APP_PROMPT_VERSION

    baseline_data = {
        "baseline_run_id": target_run_id,
        "dataset_version": dataset_version,
        "prompt_version": prompt_version,
        "prompt_hash": settings.get_prompt_hash(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "note": "Reference baseline for regression testing quality gates",
    }

    with open(lock_path, "w", encoding="utf-8") as f:
        json.dump(baseline_data, f, indent=2)

    print("\n" + "=" * 60)
    print("BASELINE INITIALIZATION SUCCESSFUL")
    print("=" * 60)
    print(f"Locked Baseline Run ID : {target_run_id}")
    print(f"Dataset Version        : {dataset_version}")
    print(f"Prompt Version         : {prompt_version}")
    print(f"Baseline Lock Saved To : {lock_path}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
