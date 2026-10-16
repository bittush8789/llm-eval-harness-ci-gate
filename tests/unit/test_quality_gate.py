"""Unit tests for Quality Gate policy evaluation and regression thresholds."""

from app.evaluation.baseline import BaselineComparisonSummary
from app.evaluation.quality_gate import QualityGate


def test_quality_gate_all_passing():
    """Verify quality gate succeeds when all metrics exceed thresholds without regressions."""
    gate = QualityGate()
    candidate_metrics = {
        "faithfulness": 0.95,
        "answer_relevance": 0.90,
        "context_precision": 0.88,
        "citation_validity": 1.0,
        "refusal_accuracy": 1.0,
        "schema_validity": 1.0,
    }
    pass_rates = {
        "citation_validity": 1.0,
        "refusal_accuracy": 1.0,
        "schema_validity": 1.0,
    }
    baseline_summary = BaselineComparisonSummary(
        candidate_run_id="cand_1",
        baseline_run_id="base_1",
        new_failures=[],
        recovered=[],
        metric_deltas={"faithfulness": 0.02},
    )

    result = gate.evaluate(
        candidate_metrics=candidate_metrics,
        deterministic_pass_rates=pass_rates,
        baseline_summary=baseline_summary,
    )

    assert result.passed is True
    assert len(result.failure_reasons) == 0


def test_quality_gate_fails_below_minimum_metric():
    """Verify quality gate fails when a mandatory metric is below threshold."""
    gate = QualityGate()
    candidate_metrics = {
        "faithfulness": 0.70,  # Below 0.85 minimum
        "answer_relevance": 0.85,
        "context_precision": 0.85,
        "citation_validity": 1.0,
        "refusal_accuracy": 1.0,
        "schema_validity": 1.0,
    }

    result = gate.evaluate(
        candidate_metrics=candidate_metrics,
        deterministic_pass_rates={},
    )

    assert result.passed is False
    assert any("faithfulness" in r for r in result.failure_reasons)


def test_quality_gate_fails_on_new_regression():
    """Verify quality gate fails when candidate introduces a newly failing case."""
    gate = QualityGate()
    candidate_metrics = {
        "faithfulness": 0.90,
        "answer_relevance": 0.90,
        "context_precision": 0.90,
        "citation_validity": 1.0,
        "refusal_accuracy": 1.0,
        "schema_validity": 1.0,
    }
    baseline_summary = BaselineComparisonSummary(
        candidate_run_id="cand_1",
        baseline_run_id="base_1",
        new_failures=["NORM-003"],
        recovered=[],
    )

    result = gate.evaluate(
        candidate_metrics=candidate_metrics,
        deterministic_pass_rates={},
        baseline_summary=baseline_summary,
    )

    assert result.passed is False
    assert any("Regression detected" in r for r in result.failure_reasons)


def test_quality_gate_fails_on_protected_test_case():
    """Verify quality gate explicitly fails if a protected test case regresses."""
    gate = QualityGate()
    candidate_metrics = {
        "faithfulness": 0.90,
        "answer_relevance": 0.90,
        "context_precision": 0.90,
        "citation_validity": 1.0,
        "refusal_accuracy": 1.0,
        "schema_validity": 1.0,
    }
    baseline_summary = BaselineComparisonSummary(
        candidate_run_id="cand_1",
        baseline_run_id="base_1",
        new_failures=["NORM-001"],  # NORM-001 is protected
    )

    result = gate.evaluate(
        candidate_metrics=candidate_metrics,
        deterministic_pass_rates={},
        baseline_summary=baseline_summary,
    )

    assert result.passed is False
    assert any("Protected test case 'NORM-001' failed" in r for r in result.failure_reasons)
