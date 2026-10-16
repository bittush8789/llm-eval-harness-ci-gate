"""Unit tests for Markdown and JSON regression report generation."""

import json
from pathlib import Path
from app.evaluation.baseline import BaselineComparisonSummary, TestCaseComparison
from app.evaluation.quality_gate import GateCheck, QualityGateResult
from app.evaluation.report_generator import ReportGenerator


def test_generate_and_save_reports(tmp_path):
    """Verify markdown and JSON reports are generated and contain required sections."""
    generator = ReportGenerator(output_dir=str(tmp_path))

    candidate_meta = {
        "run_id": "test_run_123",
        "dataset_version": "v1",
        "prompt_version": "v1.0.0",
        "prompt_hash": "a1b2c3d4",
        "app_model": "gemini-1.5-flash",
        "evaluator_model": "gemini-1.5-pro",
    }
    baseline_meta = {
        "run_id": "test_base_001",
        "dataset_version": "v1",
        "prompt_version": "v0.9.0",
        "prompt_hash": "e5f6g7h8",
        "app_model": "gemini-1.5-flash",
        "evaluator_model": "gemini-1.5-pro",
    }
    quality_gate_result = QualityGateResult(
        passed=True,
        failure_reasons=[],
        gate_checks=[
            GateCheck(
                name="min_faithfulness",
                passed=True,
                threshold=0.85,
                actual=0.92,
                message="Score: 0.920 (Min: 0.850)",
            )
        ],
    )
    baseline_summary = BaselineComparisonSummary(
        candidate_run_id="test_run_123",
        baseline_run_id="test_base_001",
        new_failures=[],
        recovered=["NORM-002"],
        unchanged_passes=["NORM-001"],
        unchanged_failures=[],
        metric_deltas={"faithfulness": 0.05},
        case_comparisons=[
            TestCaseComparison(
                case_id="NORM-002",
                status="recovered",
                candidate_passed=True,
                baseline_passed=False,
                candidate_answer="Grounded answer with [iam-policy-202]",
                baseline_answer="Vague answer",
                citation_diff={"added": ["iam-policy-202"], "removed": []},
            )
        ],
    )
    candidate_metrics = {"faithfulness": 0.92, "answer_relevance": 0.88}

    report_paths = generator.save_reports(
        candidate_meta=candidate_meta,
        baseline_meta=baseline_meta,
        quality_gate_result=quality_gate_result,
        baseline_summary=baseline_summary,
        candidate_metrics=candidate_metrics,
    )

    md_file = Path(report_paths["markdown_path"])
    json_file = Path(report_paths["json_path"])

    assert md_file.is_file()
    assert json_file.is_file()

    # Markdown checks
    md_content = md_file.read_text(encoding="utf-8")
    assert "test_run_123" in md_content
    assert "test_base_001" in md_content
    assert "Quality Gate Results" in md_content
    assert "Evaluation Metrics Overview" in md_content
    assert "Regression & Case Drift Summary" in md_content
    assert "Recommendations for Investigation" in md_content

    # Ensure no API keys or credential leakage
    assert "AIzaSy" not in md_content
    assert "sk-" not in md_content

    # JSON checks
    with open(json_file, "r", encoding="utf-8") as f:
        json_data = json.load(f)
    assert json_data["candidate"]["run_id"] == "test_run_123"
    assert json_data["quality_gate"]["passed"] is True
    assert json_data["metrics"]["faithfulness"] == 0.92
