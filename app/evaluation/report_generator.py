"""Generates structured Markdown and JSON regression evaluation reports."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from app.core.logging import logger
from app.evaluation.baseline import BaselineComparisonSummary
from app.evaluation.quality_gate import QualityGateResult


class ReportGenerator:
    """Produces GitHub-friendly Markdown summaries and machine-readable JSON evaluation reports."""

    def __init__(self, output_dir: Optional[str] = None):
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = Path(__file__).resolve().parent.parent.parent / "reports"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_json_report(
        self,
        candidate_meta: Dict[str, Any],
        baseline_meta: Optional[Dict[str, Any]],
        quality_gate_result: QualityGateResult,
        baseline_summary: BaselineComparisonSummary,
        candidate_metrics: Dict[str, float],
    ) -> Dict[str, Any]:
        """Compile complete machine-readable evaluation report dictionary."""
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "candidate": candidate_meta,
            "baseline": baseline_meta,
            "quality_gate": {
                "passed": quality_gate_result.passed,
                "failure_reasons": quality_gate_result.failure_reasons,
                "checks": [c.model_dump() for c in quality_gate_result.gate_checks],
            },
            "metrics": candidate_metrics,
            "regression_summary": {
                "new_failures": baseline_summary.new_failures,
                "recovered": baseline_summary.recovered,
                "unchanged_passes": baseline_summary.unchanged_passes,
                "unchanged_failures": baseline_summary.unchanged_failures,
                "added_cases": baseline_summary.added_cases,
                "removed_cases": baseline_summary.removed_cases,
                "metric_deltas": baseline_summary.metric_deltas,
                "warnings": baseline_summary.warnings,
            },
            "case_comparisons": [c.model_dump() for c in baseline_summary.case_comparisons],
        }
        return report

    def generate_markdown_report(
        self,
        candidate_meta: Dict[str, Any],
        baseline_meta: Optional[Dict[str, Any]],
        quality_gate_result: QualityGateResult,
        baseline_summary: BaselineComparisonSummary,
        candidate_metrics: Dict[str, float],
    ) -> str:
        """Render a clean, GitHub Flavored Markdown regression report."""
        status_badge = "✅ PASSED" if quality_gate_result.passed else "❌ FAILED"
        cand_run_id = candidate_meta.get("run_id", "N/A")
        base_run_id = baseline_meta.get("run_id", "None") if baseline_meta else "None (Initial Run)"

        lines = [
            f"# 🛡️ AI Evaluation & Regression Test Report",
            f"",
            f"**Overall Status:** {status_badge}",
            f"",
            f"### 📋 Run Metadata",
            f"| Attribute | Candidate Run | Baseline Run |",
            f"| :--- | :--- | :--- |",
            f"| **Run ID** | `{cand_run_id}` | `{base_run_id}` |",
            f"| **Dataset Version** | `{candidate_meta.get('dataset_version', 'N/A')}` | `{baseline_meta.get('dataset_version', 'N/A') if baseline_meta else 'N/A'}` |",
            f"| **Prompt Version** | `{candidate_meta.get('prompt_version', 'N/A')}` | `{baseline_meta.get('prompt_version', 'N/A') if baseline_meta else 'N/A'}` |",
            f"| **Prompt Hash** | `{candidate_meta.get('prompt_hash', 'N/A')}` | `{baseline_meta.get('prompt_hash', 'N/A') if baseline_meta else 'N/A'}` |",
            f"| **Target Model** | `{candidate_meta.get('app_model', 'N/A')}` | `{baseline_meta.get('app_model', 'N/A') if baseline_meta else 'N/A'}` |",
            f"| **Evaluator Judge** | `{candidate_meta.get('evaluator_model', 'N/A')}` | `{baseline_meta.get('evaluator_model', 'N/A') if baseline_meta else 'N/A'}` |",
            f"| **Timestamp (UTC)** | {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} | - |",
            f"",
            f"---",
            f"",
            f"### 🚪 Quality Gate Results",
        ]

        if quality_gate_result.failure_reasons:
            lines.append("> [!CAUTION]")
            lines.append("> **Quality Gate Violations Detected:**")
            for reason in quality_gate_result.failure_reasons:
                lines.append(f"> - {reason}")
            lines.append("")
        else:
            lines.append("> [!NOTE]")
            lines.append("> All mandatory metrics, deterministic assertions, and regression thresholds passed.")
            lines.append("")

        lines.extend([
            f"| Policy Rule | Threshold | Actual Score | Status | Details |",
            f"| :--- | :--- | :--- | :---: | :--- |",
        ])
        for chk in quality_gate_result.gate_checks:
            icon = "✅" if chk.passed else "❌"
            thresh_str = str(chk.threshold)
            actual_str = str(chk.actual) if chk.actual is not None else "N/A"
            lines.append(f"| `{chk.name}` | `{thresh_str}` | `{actual_str}` | {icon} | {chk.message} |")

        lines.extend([
            f"",
            f"---",
            f"",
            f"### 📊 Evaluation Metrics Overview",
            f"| Metric Name | Candidate Score | Baseline Score | Delta |",
            f"| :--- | :---: | :---: | :---: |",
        ])
        for met, val in candidate_metrics.items():
            delta = baseline_summary.metric_deltas.get(met)
            delta_str = f"{delta:+.3f}" if delta is not None else "-"
            base_val_str = f"{val - delta:.3f}" if delta is not None else "-"
            lines.append(f"| **{met}** | `{val:.3f}` | `{base_val_str}` | `{delta_str}` |")

        # Regression breakdown
        lines.extend([
            f"",
            f"---",
            f"",
            f"### 🔍 Regression & Case Drift Summary",
            f"- **Newly Failing Cases:** `{len(baseline_summary.new_failures)}` ({', '.join(baseline_summary.new_failures) or 'None'})",
            f"- **Recovered Cases:** `{len(baseline_summary.recovered)}` ({', '.join(baseline_summary.recovered) or 'None'})",
            f"- **Unchanged Passing:** `{len(baseline_summary.unchanged_passes)}`",
            f"- **Unchanged Failing:** `{len(baseline_summary.unchanged_failures)}`",
            f"- **Added Test Cases:** `{len(baseline_summary.added_cases)}`",
            f"- **Removed Test Cases:** `{len(baseline_summary.removed_cases)}`",
            f"",
        ])

        if baseline_summary.warnings:
            lines.append("> [!WARNING]")
            lines.append("> **Evaluation Environment Warnings:**")
            for w in baseline_summary.warnings:
                lines.append(f"> - {w}")
            lines.append("")

        # Detailed diff for changed cases (new failures or recovered or diffs)
        changed_cases = [
            c for c in baseline_summary.case_comparisons
            if c.status in ("new_failure", "recovered") or (c.baseline_answer and c.candidate_answer != c.baseline_answer)
        ]

        if changed_cases:
            lines.extend([
                f"### 📝 Changed Case Answers & Citation Diffs",
                f"",
            ])
            for case in changed_cases:
                status_icon = "🚨 New Failure" if case.status == "new_failure" else "🎉 Recovered" if case.status == "recovered" else "ℹ️ Answer Paraphrased"
                lines.extend([
                    f"#### Case `{case.case_id}` ({status_icon})",
                    f"- **Status:** `{case.status}` | **Candidate Passed:** `{case.candidate_passed}`",
                    f"- **Citations Added:** `{case.citation_diff.get('added', [])}` | **Citations Removed:** `{case.citation_diff.get('removed', [])}`",
                    f"",
                    f"**Candidate Answer:**",
                    f"> {case.candidate_answer}",
                    f"",
                ])
                if case.baseline_answer:
                    lines.extend([
                        f"**Baseline Answer:**",
                        f"> {case.baseline_answer}",
                        f"",
                    ])
                lines.append("---")

        # Recommendations
        lines.extend([
            f"",
            f"### 💡 Recommendations for Investigation",
        ])
        if quality_gate_result.passed:
            lines.append("1. **Quality Gates Passed:** Safe to merge or promote to staging. Consider updating baseline run ID to lock in improvements.")
        else:
            lines.append("1. **Inspect Root Causes:** Review the prompt diff or model parameter changes that introduced the failures listed above.")
            lines.append("2. **Grounding & Context Check:** If Faithfulness regressed, ensure prompt still forbids speculation and enforces refusal on unanswerable questions.")
            lines.append("3. **Citation Regressions:** Check if system prompt rules for citation token syntax `[source-id]` were altered.")
            lines.append("4. **Do Not Override Gates:** Fix underlying prompt/retrieval regressions before merging to main branch.")

        return "\n".join(lines)

    def save_reports(
        self,
        candidate_meta: Dict[str, Any],
        baseline_meta: Optional[Dict[str, Any]],
        quality_gate_result: QualityGateResult,
        baseline_summary: BaselineComparisonSummary,
        candidate_metrics: Dict[str, float],
    ) -> Dict[str, str]:
        """Save both markdown and JSON reports to disk and return their file paths."""
        run_id = candidate_meta.get("run_id", "unknown_run")
        json_report = self.generate_json_report(
            candidate_meta, baseline_meta, quality_gate_result, baseline_summary, candidate_metrics
        )
        md_report = self.generate_markdown_report(
            candidate_meta, baseline_meta, quality_gate_result, baseline_summary, candidate_metrics
        )

        json_path = self.output_dir / f"regression_report_{run_id}.json"
        md_path = self.output_dir / f"regression_report_{run_id}.md"

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_report, f, indent=2)

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_report)

        logger.info(f"Evaluation reports generated: {json_path} and {md_path}")
        return {"json_path": str(json_path), "markdown_path": str(md_path)}
