"""Baseline comparison engine detecting regressions, recoveries, and metric deltas."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.core.logging import logger


class TestCaseComparison(BaseModel):
    """Side-by-side comparison of a single test case across baseline and candidate runs."""

    __test__ = False
    case_id: str
    status: str = Field(
        description="Outcome: new_failure, recovered, unchanged_pass, unchanged_fail, added, removed"
    )
    candidate_passed: bool
    baseline_passed: Optional[bool] = None
    candidate_answer: str
    baseline_answer: Optional[str] = None
    candidate_citations: List[str] = Field(default_factory=list)
    baseline_citations: List[str] = Field(default_factory=list)
    faithfulness_delta: Optional[float] = None
    answer_relevancy_delta: Optional[float] = None
    context_precision_delta: Optional[float] = None
    citation_diff: Dict[str, List[str]] = Field(default_factory=dict)
    notes: Optional[str] = None


class BaselineComparisonSummary(BaseModel):
    """Aggregated comparison report between candidate run and baseline run."""

    candidate_run_id: str
    baseline_run_id: Optional[str] = None
    total_candidate_cases: int = 0
    total_baseline_cases: int = 0
    new_failures: List[str] = Field(default_factory=list)
    recovered: List[str] = Field(default_factory=list)
    unchanged_passes: List[str] = Field(default_factory=list)
    unchanged_failures: List[str] = Field(default_factory=list)
    added_cases: List[str] = Field(default_factory=list)
    removed_cases: List[str] = Field(default_factory=list)
    metric_deltas: Dict[str, float] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    case_comparisons: List[TestCaseComparison] = Field(default_factory=list)


class BaselineComparator:
    """Performs regression analysis by matching test cases across evaluation runs."""

    @classmethod
    def compare(
        cls,
        candidate_run_id: str,
        candidate_results: List[Dict[str, Any]],
        candidate_metrics: Dict[str, float],
        baseline_run_id: Optional[str] = None,
        baseline_results: Optional[List[Dict[str, Any]]] = None,
        baseline_metrics: Optional[Dict[str, float]] = None,
        candidate_meta: Optional[Dict[str, Any]] = None,
        baseline_meta: Optional[Dict[str, Any]] = None,
    ) -> BaselineComparisonSummary:
        """Compare candidate run against baseline run."""
        summary = BaselineComparisonSummary(
            candidate_run_id=candidate_run_id,
            baseline_run_id=baseline_run_id,
            total_candidate_cases=len(candidate_results),
            total_baseline_cases=len(baseline_results or []),
        )

        # Handle missing baseline explicitly
        if not baseline_run_id or baseline_results is None:
            summary.warnings.append(
                "No baseline run provided or found. All candidate test cases evaluated without regression baselining."
            )
            for cand in candidate_results:
                passed = cand.get("passed_deterministic", True)
                summary.case_comparisons.append(
                    TestCaseComparison(
                        case_id=cand["test_case_id"],
                        status="added" if not baseline_run_id else "candidate_only",
                        candidate_passed=passed,
                        candidate_answer=cand["generated_answer"],
                        candidate_citations=cand.get("cited_sources", []),
                        notes="Evaluated without baseline run",
                    )
                )
                if passed:
                    summary.unchanged_passes.append(cand["test_case_id"])
                else:
                    summary.new_failures.append(cand["test_case_id"])
            return summary

        # Check configuration compatibility warnings
        if candidate_meta and baseline_meta:
            if candidate_meta.get("dataset_version") != baseline_meta.get("dataset_version"):
                summary.warnings.append(
                    f"Dataset version mismatch: Candidate uses '{candidate_meta.get('dataset_version')}', "
                    f"Baseline used '{baseline_meta.get('dataset_version')}'."
                )
            if candidate_meta.get("prompt_hash") == baseline_meta.get("prompt_hash"):
                summary.warnings.append("System prompt hash is identical between baseline and candidate.")

        # Map results by test_case_id
        cand_map = {r["test_case_id"]: r for r in candidate_results}
        base_map = {r["test_case_id"]: r for r in baseline_results}

        all_case_ids = set(cand_map.keys()).union(set(base_map.keys()))

        for case_id in sorted(all_case_ids):
            in_cand = case_id in cand_map
            in_base = case_id in base_map

            if in_cand and not in_base:
                cand = cand_map[case_id]
                c_passed = cand.get("passed_deterministic", True)
                summary.added_cases.append(case_id)
                summary.case_comparisons.append(
                    TestCaseComparison(
                        case_id=case_id,
                        status="added",
                        candidate_passed=c_passed,
                        candidate_answer=cand["generated_answer"],
                        candidate_citations=cand.get("cited_sources", []),
                        notes="Newly added test case; absent in baseline",
                    )
                )
            elif in_base and not in_cand:
                base = base_map[case_id]
                b_passed = base.get("passed_deterministic", True)
                summary.removed_cases.append(case_id)
                summary.case_comparisons.append(
                    TestCaseComparison(
                        case_id=case_id,
                        status="removed",
                        candidate_passed=False,
                        baseline_passed=b_passed,
                        candidate_answer="",
                        baseline_answer=base["generated_answer"],
                        baseline_citations=base.get("cited_sources", []),
                        notes="Test case removed from candidate dataset",
                    )
                )
            else:
                cand = cand_map[case_id]
                base = base_map[case_id]

                c_passed = cand.get("passed_deterministic", True)
                b_passed = base.get("passed_deterministic", True)

                # Score deltas
                c_faith = cand.get("ragas_faithfulness")
                b_faith = base.get("ragas_faithfulness")
                faith_delta = (
                    round(c_faith - b_faith, 3)
                    if (c_faith is not None and b_faith is not None)
                    else None
                )

                c_rel = cand.get("ragas_answer_relevancy")
                b_rel = base.get("ragas_answer_relevancy")
                rel_delta = (
                    round(c_rel - b_rel, 3)
                    if (c_rel is not None and b_rel is not None)
                    else None
                )

                c_prec = cand.get("ragas_context_precision")
                b_prec = base.get("ragas_context_precision")
                prec_delta = (
                    round(c_prec - b_prec, 3)
                    if (c_prec is not None and b_prec is not None)
                    else None
                )

                # Citation diff
                c_cites = set(cand.get("cited_sources", []))
                b_cites = set(base.get("cited_sources", []))
                cite_diff = {
                    "added": sorted(list(c_cites - b_cites)),
                    "removed": sorted(list(b_cites - c_cites)),
                }

                # Status determination
                if not b_passed and c_passed:
                    status = "recovered"
                    summary.recovered.append(case_id)
                elif b_passed and not c_passed:
                    status = "new_failure"
                    summary.new_failures.append(case_id)
                elif c_passed and b_passed:
                    status = "unchanged_pass"
                    summary.unchanged_passes.append(case_id)
                else:
                    status = "unchanged_fail"
                    summary.unchanged_failures.append(case_id)

                summary.case_comparisons.append(
                    TestCaseComparison(
                        case_id=case_id,
                        status=status,
                        candidate_passed=c_passed,
                        baseline_passed=b_passed,
                        candidate_answer=cand["generated_answer"],
                        baseline_answer=base["generated_answer"],
                        candidate_citations=cand.get("cited_sources", []),
                        baseline_citations=base.get("cited_sources", []),
                        faithfulness_delta=faith_delta,
                        answer_relevancy_delta=rel_delta,
                        context_precision_delta=prec_delta,
                        citation_diff=cite_diff,
                    )
                )

        # Aggregate metric deltas
        if baseline_metrics:
            for met, c_val in candidate_metrics.items():
                if met in baseline_metrics:
                    summary.metric_deltas[met] = round(c_val - baseline_metrics[met], 3)

        return summary
