"""Unit tests for baseline comparison, diff categorization, and deltas."""

from app.evaluation.baseline import BaselineComparator


def test_baseline_comparison_categories():
    """Verify categorization of new failures, recoveries, unchanged cases, and added/removed cases."""
    candidate_results = [
        {"test_case_id": "TC-1", "generated_answer": "ans1", "passed_deterministic": False, "ragas_faithfulness": 0.70},
        {"test_case_id": "TC-2", "generated_answer": "ans2", "passed_deterministic": True, "ragas_faithfulness": 0.95},
        {"test_case_id": "TC-3", "generated_answer": "ans3", "passed_deterministic": True, "ragas_faithfulness": 0.90},
        {"test_case_id": "TC-4", "generated_answer": "ans4", "passed_deterministic": False, "ragas_faithfulness": 0.60},
        {"test_case_id": "TC-ADDED", "generated_answer": "ans_add", "passed_deterministic": True},
    ]

    baseline_results = [
        {"test_case_id": "TC-1", "generated_answer": "ans1_base", "passed_deterministic": True, "ragas_faithfulness": 0.92},
        {"test_case_id": "TC-2", "generated_answer": "ans2_base", "passed_deterministic": False, "ragas_faithfulness": 0.65},
        {"test_case_id": "TC-3", "generated_answer": "ans3_base", "passed_deterministic": True, "ragas_faithfulness": 0.91},
        {"test_case_id": "TC-4", "generated_answer": "ans4_base", "passed_deterministic": False, "ragas_faithfulness": 0.62},
        {"test_case_id": "TC-REMOVED", "generated_answer": "ans_rem", "passed_deterministic": True},
    ]

    candidate_metrics = {"faithfulness": 0.85}
    baseline_metrics = {"faithfulness": 0.82}

    summary = BaselineComparator.compare(
        candidate_run_id="cand_1",
        candidate_results=candidate_results,
        candidate_metrics=candidate_metrics,
        baseline_run_id="base_1",
        baseline_results=baseline_results,
        baseline_metrics=baseline_metrics,
    )

    assert "TC-1" in summary.new_failures
    assert "TC-2" in summary.recovered
    assert "TC-3" in summary.unchanged_passes
    assert "TC-4" in summary.unchanged_failures
    assert "TC-ADDED" in summary.added_cases
    assert "TC-REMOVED" in summary.removed_cases
    assert summary.metric_deltas.get("faithfulness") == 0.03


def test_baseline_comparison_missing_baseline():
    """Verify missing baseline produces informative warnings and does not crash."""
    candidate_results = [
        {"test_case_id": "TC-1", "generated_answer": "ans1", "passed_deterministic": True},
    ]

    summary = BaselineComparator.compare(
        candidate_run_id="cand_1",
        candidate_results=candidate_results,
        candidate_metrics={"faithfulness": 0.9},
        baseline_run_id=None,
    )

    assert len(summary.warnings) > 0
    assert "No baseline run" in summary.warnings[0]
    assert len(summary.unchanged_passes) == 1


def test_baseline_citation_diff():
    """Verify added and removed citations are calculated properly."""
    candidate_results = [
        {
            "test_case_id": "TC-1",
            "generated_answer": "ans",
            "cited_sources": ["s1", "s2"],
            "passed_deterministic": True,
        }
    ]
    baseline_results = [
        {
            "test_case_id": "TC-1",
            "generated_answer": "ans_base",
            "cited_sources": ["s2", "s3"],
            "passed_deterministic": True,
        }
    ]

    summary = BaselineComparator.compare(
        candidate_run_id="cand_1",
        candidate_results=candidate_results,
        candidate_metrics={},
        baseline_run_id="base_1",
        baseline_results=baseline_results,
        baseline_metrics={},
    )

    tc1_diff = summary.case_comparisons[0].citation_diff
    assert tc1_diff["added"] == ["s1"]
    assert tc1_diff["removed"] == ["s3"]
