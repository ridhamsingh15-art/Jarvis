"""CLI entry point for durable, write-ahead Mission Control execution."""
from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from core.exceptions import ExecutionError
from core.execution_policy import ExecutionPolicy
from core.executor.action_registry import ActionRegistry
from core.executor.executor import ExecutionEngine
from mission_control.crash_safe import CrashSafeMissionRunner
from mission_control.crash_store import CrashSafeMissionStore
from mission_control.objective_planner import build_objective_plan
from tools.file import FileTool
from tools.filesystem_queries import FileSystemQueryTool
from tools.shell import ShellTool


def _engine(workspace_root: str | Path) -> ExecutionEngine:
    registry = ActionRegistry()
    file_tool = FileTool()
    for action_name in file_tool.get_actions():
        def file_handler(_context, _action=action_name, **kwargs):
            return file_tool.execute(_action, kwargs)
        registry.register(f"file.{action_name}", file_handler)

    query_tool = FileSystemQueryTool()
    for action_name in query_tool.get_actions():
        def query_handler(_context, _action=action_name, **kwargs):
            return query_tool.execute(_action, kwargs)
        registry.register(f"file.{action_name}", query_handler)

    shell_tool = ShellTool(workspace_root=workspace_root, timeout_seconds=120)

    def shell_run(_context, **kwargs):
        command = kwargs.get("command") or kwargs.get("cmd") or kwargs.get("executable")
        if not isinstance(command, str):
            raise ExecutionError("shell.run requires a string command")
        result = shell_tool.run(command, cwd_override=kwargs.get("cwd"), timeout=kwargs.get("timeout"))
        return {
            "command": result.command, "stdout": result.stdout, "stderr": result.stderr,
            "exit_code": result.return_code if not result.blocked and not result.timed_out else None,
            "blocked": result.blocked, "blocked_reason": result.blocked_reason,
            "timed_out": result.timed_out,
        }

    registry.register("shell.run", shell_run)
    return ExecutionEngine(registry)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Crash-safe JARVIS mission execution")
    parser.add_argument("--mission", help="Bounded natural-language objective")
    parser.add_argument("--steps-json", help="JSON array of structured step objects (diagnostics/tests)")
    parser.add_argument("--mission-id", default=None)
    parser.add_argument("--mission-db", default=str(Path.home() / ".jarvis" / "crash_missions.sqlite3"))
    parser.add_argument("--workspace-root", default=str(Path.home()))
    parser.add_argument("--resume", action="store_true", help="Resume an existing mission using the supplied same objective/steps")
    parser.add_argument("--needs-review", action="store_true", help="List steps awaiting operator review")
    parser.add_argument("--show-needs-review", metavar="MISSION_ID", help="Show review reasons for one mission")
    parser.add_argument("--resolve-needs-review", metavar="MISSION_ID", help="Resolve a review step for one mission")
    parser.add_argument("--step", type=int, default=1, help="One-based step number for review resolution (default: 1)")
    parser.add_argument("--resolution", choices=("retry", "abandon"), help="Explicitly retry or abandon the uncertain step")
    parser.add_argument("--after-execute-marker", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    management = args.needs_review or args.show_needs_review or args.resolve_needs_review
    if not args.mission and not args.steps_json and not management:
        parser.error("--mission, --steps-json, or a needs-review command is required")
    if sum(bool(value) for value in (args.needs_review, args.show_needs_review, args.resolve_needs_review)) > 1:
        parser.error("Choose only one needs-review command")
    store = CrashSafeMissionStore(args.mission_db)
    if args.needs_review:
        print("NEEDS_REVIEW=" + json.dumps(store.needs_review(), ensure_ascii=False, default=str), flush=True)
        return 0
    if args.show_needs_review:
        mission = store.mission(args.show_needs_review)
        if mission is None:
            print("ERROR: mission not found: " + args.show_needs_review, flush=True)
            return 2
        steps_for_mission = store.steps(args.show_needs_review)
        review_steps = [dict(step, step_number=step["step_index"] + 1) for step in steps_for_mission if step["status"] == "needs_review"]
        print("MISSION=" + json.dumps({"mission_id": mission["mission_id"], "state": mission["state"], "failure_reason": mission["failure_reason"], "steps": review_steps}, ensure_ascii=False, default=str), flush=True)
        return 0 if review_steps else 1
    if args.resolve_needs_review:
        if not args.resolution or args.step < 1:
            parser.error("--resolve-needs-review requires --resolution retry|abandon and --step >= 1")
        try:
            mission = store.resolve_needs_review(args.resolve_needs_review, args.step - 1, args.resolution)
        except ValueError as exc:
            print("ERROR: " + str(exc), flush=True)
            return 2
        if args.resolution == "abandon":
            print("RESOLUTION=ABANDONED MISSION_STATE=" + str(mission.get("state")), flush=True)
            print("RECORDED_REASON=" + str(mission.get("failure_reason", "")), flush=True)
            return 0
        try:
            saved_steps = json.loads(mission.get("steps_json", "[]"))
            if not isinstance(saved_steps, list) or not all(isinstance(step, str) for step in saved_steps):
                raise ValueError("Stored mission plan is invalid; retry was not run")
        except (TypeError, json.JSONDecodeError, ValueError) as exc:
            print("ERROR: " + str(exc), flush=True)
            return 2
        runner = CrashSafeMissionRunner(store, _engine(args.workspace_root), ExecutionPolicy(allow_destructive_from_core=False))
        result = runner.run(args.resolve_needs_review, mission["objective"], saved_steps)
        print("RESOLUTION=RETRY MISSION_STATE=" + str((result.get("mission") or {}).get("state", "UNKNOWN")), flush=True)
        for step in result.get("steps", []):
            print("STEP_RESULT=" + json.dumps(step, ensure_ascii=False, default=str), flush=True)
        return 0 if (result.get("mission") or {}).get("state") == "COMPLETED" else 1
    try:
        if args.steps_json:
            raw = json.loads(args.steps_json)
            if not isinstance(raw, list) or not all(isinstance(item, dict) for item in raw):
                raise ValueError("--steps-json must be a JSON array of step objects")
            steps = [json.dumps(item, ensure_ascii=False) for item in raw]
            objective = args.mission or "Structured diagnostic mission"
        else:
            objective = args.mission
            steps = build_objective_plan(objective)
    except (ValueError, TypeError) as exc:
        print(json.dumps({"state": "FAILED", "failure_class": "planner", "failure_reason": str(exc)}, ensure_ascii=False), flush=True)
        return 2

    mission_id = args.mission_id or str(uuid.uuid4())
    def pause_after_execute(_mission_id, _index, _task):
        if not args.after_execute_marker:
            return
        marker = Path(args.after_execute_marker)
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("tool_returned_before_result_persist\n", encoding="utf-8")
        while True:
            time.sleep(1)

    runner = CrashSafeMissionRunner(
        store, _engine(args.workspace_root), ExecutionPolicy(allow_destructive_from_core=False),
        after_execute=pause_after_execute if args.after_execute_marker else None,
    )
    result = runner.run(mission_id, objective, steps)
    mission = result.get("mission") or {}
    print("MISSION_ID=" + mission_id, flush=True)
    print("MISSION_STATE=" + str(mission.get("state", "UNKNOWN")), flush=True)
    print("MISSION_FAILURE_REASON=" + str(mission.get("failure_reason", "")), flush=True)
    for step in result.get("steps", []):
        print("STEP_RESULT=" + json.dumps(step, ensure_ascii=False, default=str), flush=True)
    print("MISSION_RESULT=" + json.dumps(result, ensure_ascii=False, default=str), flush=True)
    return 0 if mission.get("state") == "COMPLETED" else 1


def execute_objective(
    objective: str,
    *,
    mission_db: str | Path | None = None,
    mission_id: str | None = None,
    workspace_root: str | Path | None = None,
    steps: list[str] | None = None,
) -> dict[str, Any]:
    """Shared execution service for CLI, main.py and supported GUI missions."""
    objective_steps = steps if steps is not None else build_objective_plan(objective)
    db_path = mission_db or os.environ.get("JARVIS_MISSION_DB") or (Path.home() / ".jarvis" / "crash_missions.sqlite3")
    root = workspace_root or os.environ.get("JARVIS_MISSION_WORKSPACE_ROOT") or Path.home()
    identifier = mission_id or str(uuid.uuid4())
    store = CrashSafeMissionStore(db_path)
    runner = CrashSafeMissionRunner(store, _engine(root), ExecutionPolicy(allow_destructive_from_core=False))
    return runner.run(identifier, objective, objective_steps)


def run_objective(
    objective: str,
    db_path: str | Path,
    mission_id: str | None = None,
    resume: bool = False,
    pause_after_step: int = 0,
    resolve_interrupted_step: str | None = None,
) -> int:
    """Compatibility entry for main.py; all execution is delegated to CrashSafeMissionRunner.

    The legacy MissionStore tables are maintained as a read-compatible projection
    for existing reports/tests, never as an execution/checkpoint authority.
    """
    from mission_control.crash_safe import _READ_ONLY_ACTIONS, _stable_key
    from mission_control.mission import Mission, MissionState
    from mission_control.store import MissionStore

    if resume and not mission_id:
        print("ERROR: --resume requires --mission-id", flush=True)
        return 2
    store = CrashSafeMissionStore(db_path)
    legacy_store = MissionStore(db_path)
    saved = store.mission(mission_id) if mission_id else None
    legacy_mission = None

    if resume and saved is not None:
        objective = str(saved["objective"])
        try:
            steps = json.loads(saved.get("steps_json", "[]"))
        except json.JSONDecodeError:
            print("ERROR: stored crash-safe plan is invalid", flush=True)
            return 2
        if not isinstance(steps, list) or not all(isinstance(step, str) for step in steps):
            print("ERROR: stored crash-safe plan is invalid", flush=True)
            return 2
        if resolve_interrupted_step:
            print("ERROR: --resolve-interrupted-step applies only to legacy interrupted records; use --resolve-needs-review for crash-safe missions", flush=True)
            return 2
    elif resume:
        legacy_mission = legacy_store.load_mission(str(mission_id))
        if legacy_mission is None:
            print(json.dumps({"state": "FAILED", "failure_reason": f"Mission not found: {mission_id}"}, ensure_ascii=False), flush=True)
            return 2
        recovery_required = getattr(MissionState, "RECOVERY_REQUIRED", None)
        if recovery_required is not None and legacy_mission.state == recovery_required and not resolve_interrupted_step:
            print(json.dumps({"state": "RECOVERY_REQUIRED", "failure_reason": legacy_mission.failure_reason}, ensure_ascii=False, indent=2), flush=True)
            return 1
        if resolve_interrupted_step:
            resolver = getattr(legacy_store, "resolve_interrupted_step", None)
            if resolver is None:
                print("ERROR: this legacy mission database does not support interrupted-step resolution", flush=True)
                return 2
            try:
                legacy_mission = resolver(str(mission_id), resolve_interrupted_step)
            except ValueError as exc:
                print("ERROR: " + str(exc), flush=True)
                return 2
        objective = legacy_mission.objective
        steps = list(legacy_mission.steps)
        store.create_mission(str(mission_id), objective, steps)
        # Import only explicitly completed legacy checkpoints. Unfinished steps are
        # rerun by the crash-safe runner after the operator's explicit resolution.
        for index, step_text in enumerate(steps):
            if step_text not in legacy_mission.completed_steps:
                continue
            spec = json.loads(step_text)
            tool, action, args = str(spec["tool"]), str(spec["action"]), spec.get("args", {})
            store.begin_step(
                mission_id=str(mission_id), step_index=index, tool=tool, action=action,
                args=args, idempotency_key=_stable_key(str(mission_id), index, spec),
                side_effecting=(tool, action) not in _READ_ONLY_ACTIONS, started_at="operator-confirmed-legacy-checkpoint",
            )
            store.finish_step(str(mission_id), index, {
                "status": "completed", "stdout": "", "stderr": "",
                "exit_code": 0, "normalized_code": None, "error": "Operator confirmed completed postcondition in legacy recovery bridge.",
                "paths": [], "result": {"operator_confirmed": True}, "finished_at": "operator-confirmed",
            })
    else:
        try:
            steps = build_objective_plan(objective)
        except (ValueError, TypeError) as exc:
            print(json.dumps({"state": "FAILED", "failure_class": "planner", "failure_reason": str(exc)}, ensure_ascii=False), flush=True)
            return 2
        mission_id = mission_id or str(uuid.uuid4())
        store.create_mission(mission_id, objective, steps)

    mission_id = str(mission_id or uuid.uuid4())
    # Seed the legacy view from the crash-safe journal, without consulting it for
    # execution decisions. This keeps the old database schema readable downstream.
    current_steps = store.steps(mission_id)
    legacy_mission = Mission(
        id=mission_id, objective=objective, state=MissionState.RUNNING, steps=list(steps),
        completed_steps=[steps[row["step_index"]] for row in current_steps if row["status"] == "completed" and row["step_index"] < len(steps)],
    )

    def sync_projection(_mission_id: str, _index: int, _record: dict[str, Any]) -> None:
        rows = store.steps(mission_id)
        crash_mission = store.mission(mission_id) or {}
        completed_indices = {row["step_index"] for row in rows if row["status"] == "completed"}
        legacy_mission.completed_steps = [step for i, step in enumerate(steps) if i in completed_indices]
        legacy_mission.step_results = []
        for row in rows:
            status = row["status"]
            legacy_status = {"needs_review": "unknown", "retry_authorized": "pending"}.get(status, status)
            code = row.get("exit_code")
            if code is None:
                code = row.get("normalized_code")
            if legacy_status == "blocked":
                code = 126
            elif legacy_status == "failed" and code is None:
                code = 1
            legacy_mission.step_results.append({
                "step_index": row["step_index"], "tool": row["tool"], "action": row["action"],
                "args": row["args"], "status": legacy_status, "stdout": row["stdout"],
                "stderr": row["stderr"] or row["error"], "exit_code": code, "error": row["error"],
                "paths": row["paths"], "result": row["result"],
                "started_at": row["started_at"], "finished_at": row["finished_at"],
            })
        statuses = [row["status"] for row in rows]
        if any(status in {"blocked", "failed", "needs_review", "abandoned"} for status in statuses):
            legacy_mission.state = MissionState.FAILED
        elif len(completed_indices) == len(steps) and steps:
            legacy_mission.state = MissionState.COMPLETED
        else:
            legacy_mission.state = MissionState.RUNNING
        legacy_mission.failure_reason = str(crash_mission.get("failure_reason", ""))
        legacy_store.save_mission(legacy_mission)
        if pause_after_step > 0 and _index + 1 == pause_after_step and _record.get("status") == "completed":
            print("MISSION_CHECKPOINT_READY=1", flush=True)
            while True:
                time.sleep(1)

    if not store.steps(mission_id):
        legacy_store.save_mission(legacy_mission)
    runner = CrashSafeMissionRunner(
        store, _engine(Path.home()), ExecutionPolicy(allow_destructive_from_core=False), after_step=sync_projection,
    )
    result = runner.run(mission_id, objective, steps)
    sync_projection(mission_id, max(0, len(steps) - 1), {"status": "final"}) if steps else None
    mission = result.get("mission") or {}
    # Keep legacy consumers readable while making the crash-safe WAL the sole executor.
    print(json.dumps({
        "mission_id": mission_id, "state": mission.get("state", "UNKNOWN"),
        "failure_reason": mission.get("failure_reason", ""), "steps": result.get("steps", []),
    }, ensure_ascii=False, indent=2, default=str), flush=True)
    return 0 if mission.get("state") == "COMPLETED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
