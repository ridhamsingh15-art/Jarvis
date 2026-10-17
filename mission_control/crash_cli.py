"""CLI entry point for durable, write-ahead Mission Control execution."""
from __future__ import annotations

import argparse
import json
import time
import uuid
from collections.abc import Sequence
from pathlib import Path

from core.exceptions import ExecutionError
from core.execution_policy import ExecutionPolicy
from core.executor.action_registry import ActionRegistry
from core.executor.executor import ExecutionEngine
from mission_control.cli import build_plan
from mission_control.crash_safe import CrashSafeMissionRunner
from mission_control.crash_store import CrashSafeMissionStore
from tools.file import FileTool
from tools.shell import ShellTool


def _engine(workspace_root: str | Path) -> ExecutionEngine:
    registry = ActionRegistry()
    file_tool = FileTool()
    for action_name in file_tool.get_actions():
        def file_handler(_context, _action=action_name, **kwargs):
            return file_tool.execute(_action, kwargs)
        registry.register(f"file.{action_name}", file_handler)

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
    parser.add_argument("--after-execute-marker", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if not args.mission and not args.steps_json:
        parser.error("--mission or --steps-json is required")
    try:
        if args.steps_json:
            raw = json.loads(args.steps_json)
            if not isinstance(raw, list) or not all(isinstance(item, dict) for item in raw):
                raise ValueError("--steps-json must be a JSON array of step objects")
            steps = [json.dumps(item, ensure_ascii=False) for item in raw]
            objective = args.mission or "Structured diagnostic mission"
        else:
            objective = args.mission
            steps = build_plan(objective)
    except (ValueError, TypeError) as exc:
        print(json.dumps({"state": "FAILED", "failure_class": "planner", "failure_reason": str(exc)}, ensure_ascii=False), flush=True)
        return 2

    mission_id = args.mission_id or str(uuid.uuid4())
    store = CrashSafeMissionStore(args.mission_db)

    def pause_after_execute(_mission_id, _index, _task):
        if not args.after_execute_marker:
            return
        marker = Path(args.after_execute_marker)
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("tool_returned_before_result_persist\n", encoding="utf-8")
        while True:
            time.sleep(1)

    runner = CrashSafeMissionRunner(
        store, _engine(args.workspace_root), ExecutionPolicy(allow_destructive_from_core=True),
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


if __name__ == "__main__":
    raise SystemExit(main())
