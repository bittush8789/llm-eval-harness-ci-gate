"""End-to-end evaluation tests verifying full evaluation workflow in offline CI mode."""

import pytest
from app.evaluation.evaluator import EvaluationEngine


def test_full_evaluation_cycle_offline():
    """Verify full offline evaluation flow on version v1 without external network calls."""
    engine = EvaluationEngine(offline=True)

    result = engine.run_evaluation(
        dataset_version="v1",
        baseline_run_id=None,
        prompt_version="v1.0.0",
        app_model="mock-gemini-1.5-flash",
        evaluator_model="mock-gemini-1.5-pro",
        sync_db=False,  # Skip DB sync for isolated test
    )

    assert result["run_id"].startswith("eval_")
    assert result["total_cases"] >= 20
    assert result["passed_quality_gate"] is True
    assert result["metrics"]["faithfulness"] >= 0.85
    assert result["metrics"]["citation_validity"] == 1.0
    assert result["metrics"]["refusal_accuracy"] == 1.0
    assert "markdown_path" in result["report_paths"]
    assert "json_path" in result["report_paths"]
