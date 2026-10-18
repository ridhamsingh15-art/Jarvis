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

from core.execution_policy import ExecutionPolicy
from core.executor.action_registry import ActionRegistry
from core.executor.executor import ExecutionEngine
from core.executor.isolated_handler import IsolatedToolHandler
from mission_control.crash_safe import CrashSafeMissionRunner
from mission_control.crash_store import (
    CrashSafeMissionStore,
    CrashSafeStoreCorruptionError,
)
from mission_control.objective_planner import build_adaptive_objective_plan
from tools.file import FileTool
from tools.filesystem_queries import FileSystemQueryTool
from tools.shell import _SAFE_COMMAND_PREFIXES, ShellTool


def _engine(workspace_root: str | Path, tool_registry: Any | None = None) -> ExecutionEngine:
    registry = ActionRegistry()
    file_tool = FileTool(workspace_root=workspace_root)
    for action_name in file_tool.get_actions():
        registry.register(
            f"file.{action_name}",
            IsolatedToolHandler(file_tool, action_name, timeout_seconds=30.0),
        )

    query_tool = FileSystemQueryTool()
    for action_name in query_tool.get_actions():
        registry.register(
            f"file.{action_name}",
            IsolatedToolHandler(query_tool, action_name, timeout_seconds=30.0),
        )

    shell_tool = ShellTool(workspace_root=workspace_root, timeout_seconds=120, allowed_commands=list(_SAFE_COMMAND_PREFIXES))

    # Expose the same registered desktop/browser capabilities used by the main agent.
    from tools.browser import BrowserTool
    from tools.codex_desktop import CodexDesktopTool
    from tools.windows import WindowsTool

    for desktop_tool in (BrowserTool(), WindowsTool(), CodexDesktopTool()):
        configured_timeout = getattr(desktop_tool, "execution_timeout_seconds", 25.0)
        timeout_seconds = float(configured_timeout) + 5.0 if desktop_tool.name == "codex_desktop" else 30.0
        for action_name in desktop_tool.get_actions():
            registry.register(
                f"{desktop_tool.name}.{action_name}",
                IsolatedToolHandler(desktop_tool, action_name, timeout_seconds=timeout_seconds),
            )

    registry.register(
        "shell.run",
        IsolatedToolHandler(
            shell_tool, "run", mode="shell_structured", timeout_seconds=125.0,
        ),
    )

    # Extend the mission engine with additional explicitly registered BaseTool
    # capabilities. Never accept an arbitrary action merely because the model names it.
    if tool_registry is not None:
        list_tools = getattr(tool_registry, "list_tools", None)
        get_tool = getattr(tool_registry, "get_executor", None) or getattr(tool_registry, "get", None)
        if callable(list_tools) and callable(get_tool):
            for tool_name in list_tools():
                if tool_name == "shell":
                    # Keep the workspace-scoped, policy-gated ShellTool created above.
                    continue
                tool = get_tool(tool_name)
                if tool is None:
                    continue
                for action_name in tool.get_actions():
                    timeout_seconds = max(30.0, float(getattr(tool, "execution_timeout_seconds", 25.0)) + 5.0)
                    registry.register(
                        f"{tool_name}.{action_name}",
                        IsolatedToolHandler(tool, action_name, timeout_seconds=timeout_seconds),
                    )
    return ExecutionEngine(registry)


def _sync_legacy_projection(db_path: str | Path, mission_id: str) -> None:
    """Refresh legacy MissionStore views from the crash-safe journal after approval actions."""
    from mission_control.mission import Mission, MissionState
    from mission_control.store import MissionStore

    store = CrashSafeMissionStore(db_path)
    crash_mission = store.mission(mission_id)
    if crash_mission is None:
        return
    try:
        steps = json.loads(crash_mission.get("steps_json", "[]"))
    except (TypeError, json.JSONDecodeError):
        return
    if not isinstance(steps, list) or not all(isinstance(step, str) for step in steps):
        return

    rows = store.steps(mission_id)
    completed_indices = {row["step_index"] for row in rows if row["status"] == "completed"}
    mission = Mission(
        id=mission_id, objective=str(crash_mission.get("objective", "")),
        state=MissionState.RUNNING, steps=list(steps),
        completed_steps=[step for index, step in enumerate(steps) if index in completed_indices],
    )
    for row in rows:
        status = {"needs_review": "unknown", "retry_authorized": "pending"}.get(row["status"], row["status"])
        code = row.get("exit_code") if row.get("exit_code") is not None else row.get("normalized_code")
        if status == "blocked":
            code = 126
        elif status == "failed" and code is None:
            code = 1
        mission.step_results.append({
            "step_index": row["step_index"], "tool": row["tool"], "action": row["action"],
            "args": row["args"], "status": status, "stdout": row["stdout"],
            "stderr": row["stderr"] or row["error"], "exit_code": code, "error": row["error"],
            "paths": row["paths"], "result": row["result"],
            "started_at": row["started_at"], "finished_at": row["finished_at"],
        })
    statuses = [row["status"] for row in rows]
    if "pending_approval" in statuses:
        mission.state = MissionState.WAITING_APPROVAL
    elif "abandoned" in statuses:
        mission.state = MissionState.ABANDONED
    elif any(status in {"blocked", "failed", "needs_review"} for status in statuses):
        mission.state = MissionState.FAILED
    elif steps and len(completed_indices) == len(steps):
        mission.state = MissionState.COMPLETED
    mission.failure_reason = str(crash_mission.get("failure_reason", ""))
    MissionStore(db_path).save_mission(mission)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Crash-safe JARVIS mission execution")
    parser.add_argument("--mission", help="Bounded natural-language objective")
    parser.add_argument("--steps-json", help="JSON array of structured step objects (diagnostics/tests)")
    parser.add_argument("--mission-id", default=None)
    parser.add_argument("--mission-db", default=str(Path.home() / ".jarvis" / "crash_missions.sqlite3"))
    parser.add_argument("--workspace-root", default=str(Path.home()))
    parser.add_argument("--resume", action="store_true", help="Resume an existing mission using the supplied same objective/steps")
    parser.add_argument("--require-verified", action="store_true", help="Return non-zero unless every completed step is independently verified")
    parser.add_argument("--pending-approvals", action="store_true", help="List steps awaiting explicit operator approval")
    parser.add_argument("--approve", metavar="MISSION_ID", help="Approve and execute one pending step (selected by --step)")
    parser.add_argument("--deny", metavar="MISSION_ID", help="Deny one pending step (selected by --step)")
    parser.add_argument("--needs-review", action="store_true", help="List steps awaiting operator review")
    parser.add_argument("--show-needs-review", metavar="MISSION_ID", help="Show review reasons for one mission")
    parser.add_argument("--resolve-needs-review", metavar="MISSION_ID", help="Resolve a review step for one mission")
    parser.add_argument("--step", type=int, default=1, help="One-based step number for review resolution (default: 1)")
    parser.add_argument("--resolution", choices=("retry", "abandon"), help="Explicitly retry or abandon the uncertain step")
    parser.add_argument("--after-execute-marker", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    management_commands = (args.pending_approvals, args.approve, args.deny, args.needs_review, args.show_needs_review, args.resolve_needs_review)
    management = any(bool(value) for value in management_commands)
    if not args.mission and not args.steps_json and not management and not args.resume:
        parser.error("--mission, --steps-json, --resume, or a mission-management command is required")
    if sum(bool(value) for value in management_commands) > 1:
        parser.error("Choose only one mission-management command")
    if args.resume and (args.mission or args.steps_json or management):
        parser.error("--resume cannot be combined with a new objective, steps, or management command")
    if args.step < 1:
        parser.error("--step must be >= 1")
    store = CrashSafeMissionStore(args.mission_db)
    if args.pending_approvals:
        print("PENDING_APPROVALS=" + json.dumps(store.pending_approvals(), ensure_ascii=False, default=str), flush=True)
        return 0
    if args.approve or args.deny:
        mission_id = args.approve or args.deny
        approved = bool(args.approve)
        try:
            mission = store.resolve_pending_approval(mission_id, args.step - 1, approved)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            print("ERROR: " + str(exc), flush=True)
            return 2
        if not approved:
            _sync_legacy_projection(args.mission_db, mission_id)
            print("APPROVAL=DENIED MISSION_STATE=" + str(mission.get("state")), flush=True)
            return 0
        try:
            saved_steps = json.loads(mission.get("steps_json", "[]"))
            if not isinstance(saved_steps, list) or not all(isinstance(step, str) for step in saved_steps):
                raise ValueError("Stored mission plan is invalid; approved action was not executed")
        except (TypeError, json.JSONDecodeError, ValueError) as exc:
            print("ERROR: " + str(exc), flush=True)
            return 2
        def pause_after_approved_execute(_mission_id, _index, _task):
            if not args.after_execute_marker:
                return
            marker = Path(args.after_execute_marker)
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text("tool_returned_before_result_persist\n", encoding="utf-8")
            while True:
                time.sleep(1)

        if not args.after_execute_marker:
            print("APPROVAL=GRANTED; resuming durable mission " + mission_id, flush=True)
            return run_objective(
                objective=str(mission.get("objective", "")), db_path=args.mission_db,
                mission_id=mission_id, resume=True, workspace_root=args.workspace_root,
                require_verified=args.require_verified,
            )
        runner = CrashSafeMissionRunner(
            store, _engine(args.workspace_root), ExecutionPolicy(
                allow_destructive_from_core=True, workspace_root=args.workspace_root,
            ),
            after_execute=pause_after_approved_execute,
        )
        result = runner.run(mission_id, mission.get("objective", ""), saved_steps)
        _sync_legacy_projection(args.mission_db, mission_id)
        state = (result.get("mission") or {}).get("state", "UNKNOWN")
        verification_status = (result.get("mission") or {}).get("verification_status", "not_verified")
        print("APPROVAL=GRANTED MISSION_STATE=" + str(state) + " VERIFICATION_STATUS=" + str(verification_status), flush=True)
        for step_result in result.get("steps", []):
            print("STEP_RESULT=" + json.dumps(step_result, ensure_ascii=False, default=str), flush=True)
        return 0 if state == "COMPLETED" and verification_status == "verified" else 1
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
        runner = CrashSafeMissionRunner(
            store, _engine(args.workspace_root),
            ExecutionPolicy(allow_destructive_from_core=False, workspace_root=args.workspace_root),
        )
        result = runner.run(args.resolve_needs_review, mission["objective"], saved_steps)
        print("RESOLUTION=RETRY MISSION_STATE=" + str((result.get("mission") or {}).get("state", "UNKNOWN")), flush=True)
        for step in result.get("steps", []):
            print("STEP_RESULT=" + json.dumps(step, ensure_ascii=False, default=str), flush=True)
        retry_mission = result.get("mission") or {}
        retry_verification = retry_mission.get("verification_status", "not_verified")
        print("RESOLUTION_VERIFICATION_STATUS=" + str(retry_verification), flush=True)
        return 0 if retry_mission.get("state") == "COMPLETED" and retry_verification == "verified" else 1
    try:
        if args.resume:
            if not args.mission_id:
                parser.error("--resume requires --mission-id")
            saved_mission = store.mission(args.mission_id)
            if saved_mission is None:
                print("ERROR: mission not found: " + args.mission_id, flush=True)
                return 2
            steps = json.loads(saved_mission.get("steps_json", "[]"))
            if not isinstance(steps, list) or not all(isinstance(step, str) for step in steps):
                raise ValueError("Stored mission plan is invalid; resume was not run")
            objective = str(saved_mission.get("objective", ""))
        elif args.steps_json:
            raw = json.loads(args.steps_json)
            if not isinstance(raw, list) or not all(isinstance(item, dict) for item in raw):
                raise ValueError("--steps-json must be a JSON array of step objects")
            steps = [json.dumps(item, ensure_ascii=False) for item in raw]
            objective = args.mission or "Structured diagnostic mission"
        else:
            objective = args.mission
            steps = build_adaptive_objective_plan(objective)
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
        store, _engine(args.workspace_root), ExecutionPolicy(
                allow_destructive_from_core=True, workspace_root=args.workspace_root,
            ),
        after_execute=pause_after_execute if args.after_execute_marker else None,
    )
    result = runner.run(mission_id, objective, steps)
    mission = result.get("mission") or {}
    print("MISSION_ID=" + mission_id, flush=True)
    print("MISSION_STATE=" + str(mission.get("state", "UNKNOWN")), flush=True)
    print("MISSION_FAILURE_REASON=" + str(mission.get("failure_reason", "")), flush=True)
    verification_status = mission.get("verification_status", "not_verified")
    print("MISSION_VERIFICATION_STATUS=" + str(verification_status), flush=True)
    if result.get("error"):
        print("MISSION_ERROR=" + str(result["error"]), flush=True)
        return 2
    for step in result.get("steps", []):
        print("STEP_RESULT=" + json.dumps(step, ensure_ascii=False, default=str), flush=True)
    print("MISSION_RESULT=" + json.dumps(result, ensure_ascii=False, default=str), flush=True)
    return 0 if mission.get("state") == "COMPLETED" and verification_status == "verified" else 1


def execute_objective(
    objective: str,
    *,
    mission_db: str | Path | None = None,
    mission_id: str | None = None,
    workspace_root: str | Path | None = None,
    steps: list[str] | None = None,
    tool_registry: Any | None = None,
) -> dict[str, Any]:
    """Shared execution service; optional tool registries extend capabilities without bypassing validation."""
    db_path = mission_db or os.environ.get("JARVIS_MISSION_DB") or (Path.home() / ".jarvis" / "crash_missions.sqlite3")
    root = workspace_root or os.environ.get("JARVIS_MISSION_WORKSPACE_ROOT") or Path.home()
    identifier = mission_id or str(uuid.uuid4())
    engine = _engine(root, tool_registry=tool_registry)
    objective_steps = steps if steps is not None else build_adaptive_objective_plan(
        objective, execution_engine=engine, tool_registry=tool_registry,
    )
    store = CrashSafeMissionStore(db_path)
    list_tools = getattr(tool_registry, "list_tools", None)
    additional_tools = frozenset(list_tools()) if callable(list_tools) else frozenset()
    policy = ExecutionPolicy(
        allow_destructive_from_core=True,
        registered_tools=additional_tools,
        workspace_root=root,
    )
    runner = CrashSafeMissionRunner(store, engine, policy)
    return runner.run(identifier, objective, objective_steps)


def run_objective(
    objective: str,
    db_path: str | Path,
    mission_id: str | None = None,
    resume: bool = False,
    pause_after_step: int = 0,
    resolve_interrupted_step: str | None = None,
    workspace_root: str | Path | None = None,
    require_verified: bool = False,
) -> int:
    """Compatibility entry for main.py; all execution is delegated to CrashSafeMissionRunner.

    The legacy MissionStore tables are maintained as a read-compatible projection
    for existing reports/tests, never as an execution/checkpoint authority.
    """
    from mission_control.crash_safe import _READ_ONLY_ACTIONS, _stable_key
    from mission_control.mission import Mission, MissionState
    from mission_control.store import MissionStore, MissionStoreCorruptionError

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
        try:
            legacy_mission = legacy_store.load_mission(str(mission_id))
        except MissionStoreCorruptionError as exc:
            print(f"ERROR: legacy mission checkpoint is corrupt: {exc}", flush=True)
            return 2
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
            steps = build_adaptive_objective_plan(objective)
        except (ValueError, TypeError) as exc:
            print(json.dumps({"state": "FAILED", "failure_class": "planner", "failure_reason": str(exc)}, ensure_ascii=False), flush=True)
            return 2
        mission_id = mission_id or str(uuid.uuid4())
        store.create_mission(mission_id, objective, steps)

    mission_id = str(mission_id or uuid.uuid4())
    # Seed the legacy view from the crash-safe journal, without consulting it for
    # execution decisions. This keeps the old database schema readable downstream.
    try:
        current_steps = store.steps(mission_id)
    except CrashSafeStoreCorruptionError as exc:
        reason = f"Stored crash-safe mission data is corrupt; resume was refused: {exc}"
        store.set_mission_state(mission_id, "FAILED", reason)
        print(json.dumps({
            "mission_id": mission_id,
            "state": "FAILED",
            "failure_class": "persistence_corruption",
            "failure_reason": reason,
        }, ensure_ascii=False), flush=True)
        return 2
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
        if "pending_approval" in statuses:
            legacy_mission.state = MissionState.WAITING_APPROVAL
        elif "abandoned" in statuses:
            legacy_mission.state = MissionState.ABANDONED
        elif any(status in {"blocked", "failed", "needs_review"} for status in statuses):
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

    if not current_steps:
        legacy_store.save_mission(legacy_mission)
    resolved_workspace = Path(workspace_root).expanduser().resolve() if workspace_root is not None else Path.home().resolve()
    runner = CrashSafeMissionRunner(
        store, _engine(resolved_workspace), ExecutionPolicy(
            allow_destructive_from_core=True, workspace_root=resolved_workspace,
        ), after_step=sync_projection,
    )
    try:
        result = runner.run(mission_id, objective, steps)
    except CrashSafeStoreCorruptionError as exc:
        reason = f"Stored crash-safe mission data is corrupt; execution stopped: {exc}"
        store.set_mission_state(mission_id, "FAILED", reason)
        print(json.dumps({
            "mission_id": mission_id,
            "state": "FAILED",
            "failure_class": "persistence_corruption",
            "failure_reason": reason,
        }, ensure_ascii=False), flush=True)
        return 2
    if steps and not result.get("error"):
        sync_projection(mission_id, max(0, len(steps) - 1), {"status": "final"})
    mission = result.get("mission") or {}
    # Keep legacy consumers readable while making the crash-safe WAL the sole executor.
    verification_status = mission.get("verification_status", "not_verified")
    print(json.dumps({
        "mission_id": mission_id, "state": mission.get("state", "UNKNOWN"),
        "failure_reason": mission.get("failure_reason", ""),
        "verification_status": verification_status, "steps": result.get("steps", []),
        "error": result.get("error"),
    }, ensure_ascii=False, indent=2, default=str), flush=True)
    if result.get("error"):
        return 2
    return 0 if mission.get("state") == "COMPLETED" and (not require_verified or verification_status == "verified") else 1


if __name__ == "__main__":
    raise SystemExit(main())
