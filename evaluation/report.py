import json

from .leaderboard import Leaderboard
from .metrics import EvaluationMetrics
from .regression import RegressionResult


class ReportGenerator:
    """Produces evaluation reports in HTML, JSON, and Markdown formats."""

    def generate_json(
        self,
        metrics: EvaluationMetrics,
        regressions: list[RegressionResult],
        leaderboard: Leaderboard,
    ) -> str:
        categories: list[dict] = []
        regressions_list: list[dict] = []
        leaderboard_list: list[dict] = []

        data: dict = {
            "overall_success_rate": metrics.overall_success_rate(),
            "categories": categories,
            "regressions": regressions_list,
            "leaderboard": leaderboard_list,
        }

        for cm in metrics.all_metrics():
            data["categories"].append(
                {
                    "category": cm.category,
                    "total": cm.total_cases,
                    "passed": cm.passed,
                    "failed": cm.failed,
                    "success_rate": cm.success_rate,
                    "avg_latency_ms": cm.avg_latency_ms,
                    "avg_quality": cm.avg_quality,
                }
            )

        for rr in regressions:
            data["regressions"].append(
                {
                    "category": rr.category,
                    "baseline": rr.baseline_success_rate,
                    "current": rr.current_success_rate,
                    "delta": rr.delta,
                    "regressed": rr.regressed,
                }
            )

        for entry in leaderboard.all_entries():
            data["leaderboard"].append(
                {
                    "name": entry.name,
                    "category": entry.category,
                    "score": entry.score,
                }
            )

        return json.dumps(data, indent=2)

    def generate_markdown(
        self,
        metrics: EvaluationMetrics,
        regressions: list[RegressionResult],
        leaderboard: Leaderboard,
    ) -> str:
        lines: list[str] = []
        lines.append("# JARVIS AIOS Evaluation Report\n")
        lines.append(f"**Overall Success Rate:** {metrics.overall_success_rate():.2%}\n")

        lines.append("\n## Category Breakdown\n")
        lines.append("| Category | Total | Passed | Failed | Success Rate | Avg Latency | Avg Quality |")
        lines.append("|----------|-------|--------|--------|--------------|-------------|-------------|")
        for cm in metrics.all_metrics():
            lines.append(
                f"| {cm.category} | {cm.total_cases} | {cm.passed} | {cm.failed} | "
                f"{cm.success_rate:.2%} | {cm.avg_latency_ms:.1f}ms | {cm.avg_quality:.4f} |"
            )

        if regressions:
            lines.append("\n## Regression Analysis\n")
            lines.append("| Category | Baseline | Current | Delta | Regressed |")
            lines.append("|----------|----------|---------|-------|-----------|")
            for rr in regressions:
                flag = "⚠️ YES" if rr.regressed else "✅ No"
                lines.append(
                    f"| {rr.category} | {rr.baseline_success_rate:.2%} | "
                    f"{rr.current_success_rate:.2%} | {rr.delta:+.4f} | {flag} |"
                )

        if leaderboard.all_entries():
            lines.append("\n## Leaderboard\n")
            for cat in leaderboard.all_categories():
                lines.append(f"\n### {cat}\n")
                for i, entry in enumerate(leaderboard.top(cat), 1):
                    lines.append(f"{i}. **{entry.name}** — {entry.score:.4f}")

        return "\n".join(lines)

    def generate_html(
        self,
        metrics: EvaluationMetrics,
        regressions: list[RegressionResult],
        leaderboard: Leaderboard,
    ) -> str:
        parts: list[str] = []
        parts.append("<!DOCTYPE html><html><head><title>JARVIS Evaluation Report</title>")
        parts.append("<style>body{font-family:sans-serif;margin:2em;} table{border-collapse:collapse;width:100%;} ")
        parts.append("th,td{border:1px solid #ccc;padding:8px;text-align:left;} th{background:#f4f4f4;}</style></head><body>")
        parts.append("<h1>JARVIS AIOS Evaluation Report</h1>")
        parts.append(f"<p>Overall Success Rate: <strong>{metrics.overall_success_rate():.2%}</strong></p>")

        parts.append("<h2>Category Breakdown</h2><table><tr><th>Category</th><th>Total</th><th>Passed</th><th>Failed</th><th>Success Rate</th></tr>")
        for cm in metrics.all_metrics():
            parts.append(f"<tr><td>{cm.category}</td><td>{cm.total_cases}</td><td>{cm.passed}</td><td>{cm.failed}</td><td>{cm.success_rate:.2%}</td></tr>")
        parts.append("</table>")

        if regressions:
            parts.append("<h2>Regressions</h2><table><tr><th>Category</th><th>Baseline</th><th>Current</th><th>Delta</th><th>Regressed</th></tr>")
            for rr in regressions:
                flag = "⚠️" if rr.regressed else "✅"
                parts.append(f"<tr><td>{rr.category}</td><td>{rr.baseline_success_rate:.2%}</td><td>{rr.current_success_rate:.2%}</td><td>{rr.delta:+.4f}</td><td>{flag}</td></tr>")
            parts.append("</table>")

        parts.append("</body></html>")
        return "".join(parts)
