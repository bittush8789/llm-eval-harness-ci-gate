"""Quality gate policy evaluator enforcing metric thresholds and regression tolerances."""

from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from pydantic import BaseModel, Field
from app.core.config import settings
from app.core.logging import logger
from app.evaluation.baseline import BaselineComparisonSummary


class GateCheck(BaseModel):
    """Individual quality gate rule check result."""

    name: str
    passed: bool
    threshold: Any
    actual: Any
    message: str


class QualityGateResult(BaseModel):
    """Aggregate quality gate enforcement decision."""

    passed: bool
    failure_reasons: List[str] = Field(default_factory=list)
    gate_checks: List[GateCheck] = Field(default_factory=list)


class QualityGate:
    """Evaluates candidate evaluation metrics and regression summary against policy thresholds."""

    def __init__(self, thresholds_path: Optional[str] = None):
        path = Path(thresholds_path or settings.EVALUATION_THRESHOLDS_FILE)
        if not path.is_file():
            # Workspace root fallback
            alt_path = Path(__file__).resolve().parent.parent.parent / "evaluation" / "thresholds.yaml"
            if alt_path.is_file():
                path = alt_path
            else:
                raise FileNotFoundError(f"Quality gate thresholds file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            self.policy = yaml.safe_load(f)

        self.minimum_metrics = self.policy.get("minimum_metrics", {})
        self.regression_tolerances = self.policy.get("regression_tolerances", {})
        self.deterministic_gates = self.policy.get("deterministic_gates", {})
        self.protected_test_cases = set(self.policy.get("protected_test_cases", []))

    def evaluate(
        self,
        candidate_metrics: Dict[str, float],
        deterministic_pass_rates: Dict[str, float],
        baseline_summary: Optional[BaselineComparisonSummary] = None,
    ) -> QualityGateResult:
        """Evaluate all quality gate rules and decide whether candidate passes."""
        checks: List[GateCheck] = []
        failure_reasons: List[str] = []

        # 1. Enforce Minimum Metric Thresholds
        for metric_name, min_threshold in self.minimum_metrics.items():
            actual_score = candidate_metrics.get(metric_name)

            # Map from deterministic pass rates if not in candidate_metrics
            if actual_score is None and metric_name in deterministic_pass_rates:
                actual_score = deterministic_pass_rates[metric_name]

            if actual_score is None:
                failure_reasons.append(f"Required metric '{metric_name}' was not evaluated or missing.")
                checks.append(
                    GateCheck(
                        name=f"min_{metric_name}",
                        passed=False,
                        threshold=min_threshold,
                        actual=None,
                        message=f"Missing evaluation metric '{metric_name}'",
                    )
                )
                continue

            passed = actual_score >= min_threshold
            if not passed:
                failure_reasons.append(
                    f"Metric '{metric_name}' failed minimum threshold: actual {actual_score:.3f} < threshold {min_threshold:.3f}"
                )
            checks.append(
                GateCheck(
                    name=f"min_{metric_name}",
                    passed=passed,
                    threshold=min_threshold,
                    actual=round(actual_score, 3),
                    message=f"Score: {actual_score:.3f} (Min: {min_threshold:.3f})",
                )
            )

        # 2. Enforce Regression Tolerances (if baseline summary is available)
        if baseline_summary and baseline_summary.baseline_run_id:
            # Check maximum allowed new failures
            max_new_failures = self.regression_tolerances.get("max_allowed_new_failures", 0)
            num_new_failures = len(baseline_summary.new_failures)
            new_failures_passed = num_new_failures <= max_new_failures

            if not new_failures_passed:
                failure_reasons.append(
                    f"Regression detected: {num_new_failures} new test failures ({', '.join(baseline_summary.new_failures)}). Allowed: {max_new_failures}"
                )
            checks.append(
                GateCheck(
                    name="max_allowed_new_failures",
                    passed=new_failures_passed,
                    threshold=max_new_failures,
                    actual=num_new_failures,
                    message=f"{num_new_failures} new failures detected (Max allowed: {max_new_failures})",
                )
            )

            # Check protected test cases
            for protected_id in self.protected_test_cases:
                if protected_id in baseline_summary.new_failures:
                    failure_reasons.append(
                        f"CRITICAL REGRESSION: Protected test case '{protected_id}' failed in candidate run!"
                    )
                    checks.append(
                        GateCheck(
                            name=f"protected_case_{protected_id}",
                            passed=False,
                            threshold="PASS",
                            actual="FAIL",
                            message=f"Protected test case {protected_id} failed!",
                        )
                    )

            # Check metric drops
            for metric, delta in baseline_summary.metric_deltas.items():
                tol_key = f"max_{metric}_drop"
                if tol_key in self.regression_tolerances:
                    allowed_drop = self.regression_tolerances[tol_key]
                    # If delta is negative, check if drop exceeds allowed_drop
                    if delta < -allowed_drop:
                        failure_reasons.append(
                            f"Metric '{metric}' regressed by {abs(delta):.3f}, exceeding tolerance of {allowed_drop:.3f}"
                        )
                        checks.append(
                            GateCheck(
                                name=f"regression_drop_{metric}",
                                passed=False,
                                threshold=allowed_drop,
                                actual=abs(delta),
                                message=f"Regressed by {abs(delta):.3f} > allowed {allowed_drop:.3f}",
                            )
                        )
                    else:
                        checks.append(
                            GateCheck(
                                name=f"regression_drop_{metric}",
                                passed=True,
                                threshold=allowed_drop,
                                actual=delta,
                                message=f"Delta: {delta:+.3f} (Within tolerance {allowed_drop:.3f})",
                            )
                        )

        overall_passed = len(failure_reasons) == 0
        return QualityGateResult(
            passed=overall_passed,
            failure_reasons=failure_reasons,
            gate_checks=checks,
        )
