"""Evaluate model-generated plans without executing any planned action.

Run from the repository root:
    .venv\\Scripts\\python.exe evaluation\\evaluate_model_planner.py
Optional:
    .venv\\Scripts\\python.exe evaluation\\evaluate_model_planner.py --cases evaluation\\model_planner_cases.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

# Support direct execution as documented, where Python otherwise puts only
# the evaluation/ directory on sys.path.
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from config.config import load_config
from core.llm import LLMClient
from mission_control.objective_planner import _build_llm_objective_plan


def _tool_sequence(encoded_steps: list[str]) -> list[str]:
    result: list[str] = []
    for encoded in encoded_steps:
        spec = json.loads(encoded)
        result.append(f"{spec['tool']}.{spec['action']}")
    return result


def _replace_workspace(value: Any, workspace: Path) -> Any:
    if isinstance(value, str):
        return value.replace("{workspace}", str(workspace))
    if isinstance(value, list):
        return [_replace_workspace(item, workspace) for item in value]
    if isinstance(value, dict):
        return {key: _replace_workspace(item, workspace) for key, item in value.items()}
    return value


def evaluate(cases_path: Path, workspace: Path) -> dict[str, Any]:
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    if not isinstance(cases, list):
        raise TypeError("Evaluation cases must be a JSON array.")
    client = LLMClient(load_config())
    rows: list[dict[str, Any]] = []

    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("objective"), str):
            raise TypeError("Each evaluation case must have an objective.")
        case_id = str(case.get("id", "unnamed"))
        objective = case["objective"].replace("{workspace}", str(workspace))
        started = time.perf_counter()
        recovery_context = _replace_workspace(case.get("recovery"), workspace) if case.get("recovery") else None
        try:
            encoded = _build_llm_objective_plan(objective, client, recovery_context=recovery_context)
            sequence = _tool_sequence(encoded)
            unsupported_correct = not bool(case.get("expected_unsupported", False))
            sequence_correct = sequence == case.get("expected_tools", [])
            recovery_alternative = None
            if recovery_context is not None:
                failed_signature = [
                    (item.get("tool"), item.get("action"), item.get("args", {}))
                    for item in recovery_context.get("failed_plan", [])
                ]
                actual_signature = [(json.loads(item).get("tool"), json.loads(item).get("action"), json.loads(item).get("args", {})) for item in encoded]
                recovery_alternative = bool(actual_signature and actual_signature != failed_signature)
            rows.append({
                "id": case_id,
                "category": case.get("category", "uncategorized"),
                "expected_unsupported": bool(case.get("expected_unsupported", False)),
                "valid_plan": True,
                "unsupported_correct": unsupported_correct,
                "tool_sequence": sequence,
                "planned_steps": [json.loads(item) for item in encoded],
                "tool_sequence_correct": sequence_correct,
                "recovery_case": recovery_context is not None,
                "recovery_alternative": recovery_alternative,
                "latency_seconds": round(time.perf_counter() - started, 3),
            })
        except (TypeError, ValueError) as exc:
            unsupported = bool(case.get("expected_unsupported", False))
            rows.append({
                "id": case_id,
                "category": case.get("category", "uncategorized"),
                "expected_unsupported": unsupported,
                "valid_plan": False,
                "unsupported_correct": unsupported,
                "tool_sequence": [],
                "tool_sequence_correct": unsupported and case.get("expected_tools", []) == [],
                "recovery_case": recovery_context is not None,
                "recovery_alternative": False if recovery_context is not None else None,
                "failure_class": type(exc).__name__,
                "failure_reason": str(exc)[:500],
                "latency_seconds": round(time.perf_counter() - started, 3),
            })

    total = len(rows)
    supported_rows = [row for row in rows if not row["expected_unsupported"]]
    unsupported_rows = [row for row in rows if row["expected_unsupported"]]
    recovery_rows = [row for row in rows if row.get("recovery_case")]
    summary = {
        "cases": total,
        "valid_plan_rate": round(sum(row["valid_plan"] for row in supported_rows) / len(supported_rows), 3) if supported_rows else 0.0,
        "tool_sequence_accuracy": round(sum(row["tool_sequence_correct"] for row in supported_rows) / len(supported_rows), 3) if supported_rows else 0.0,
        "unsupported_handling_accuracy": round(sum(row["unsupported_correct"] for row in unsupported_rows) / len(unsupported_rows), 3) if unsupported_rows else 0.0,
        "recovery_cases": len(recovery_rows),
        "recovery_alternative_rate": round(sum(bool(row.get("recovery_alternative")) for row in recovery_rows) / len(recovery_rows), 3) if recovery_rows else None,
        "recovery_expected_sequence_accuracy": round(sum(bool(row.get("tool_sequence_correct")) for row in recovery_rows) / len(recovery_rows), 3) if recovery_rows else None,
        "total_planning_seconds": round(sum(row["latency_seconds"] for row in rows), 3),
        "results": rows,
        "execution_performed": False,
    }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path(__file__).with_name("model_planner_cases.json"),
        help="JSON evaluation cases (default: model_planner_cases.json)",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.home() / "Documents",
        help="A directory path used as a harmless planning fixture; no files are changed.",
    )
    parser.add_argument("--output", type=Path, help="Optional path to write the JSON report.")
    args = parser.parse_args()
    if not args.workspace.is_dir():
        parser.error(f"Workspace directory does not exist: {args.workspace}")
    report = evaluate(args.cases, args.workspace)
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    print(rendered)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if report["cases"] and report["valid_plan_rate"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
