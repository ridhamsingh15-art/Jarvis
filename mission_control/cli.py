"""CLI for real, policy-gated, restartable Mission Control objectives."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import uuid
from collections.abc import Sequence
from pathlib import Path

from core.execution_policy import ExecutionPolicy
from core.executor.action_registry import ActionRegistry
from core.executor.executor import ExecutionEngine
from core.executor.isolated_handler import IsolatedToolHandler
from tools.file import FileTool

from .execution import MissionExecutor
from .mission import Mission, MissionState
from .store import MissionStore, MissionStoreCorruptionError

_DEFAULT_DOWNLOADS = Path.home() / "Downloads"


def build_plan(objective: str) -> list[str]:
    """Convert a supported user objective into explicit, structured tool steps."""
    text = objective.strip()
    delete_match = re.fullmatch(r"delete\s+(.+)", text, flags=re.IGNORECASE)
    if delete_match:
        target = delete_match.group(1).strip().strip('"')
        return [json.dumps({"tool": "file", "action": "delete", "args": {"path": target}})]

    match = re.search(
        r"(?:list\s+(?:the\s+)?(?P<count>\d+)\s+largest\s+files\s+in\s+|"
        r"summarize\s+(?:the\s+)?largest\s+files\s+in\s+)(?P<path>.+?)"
        r"(?:\s+and\s+summarize\s+them)?\s*$",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        path_text = match.group("path").strip().strip('"')
        if path_text.lower() in {"my downloads folder", "downloads", "my downloads"}:
            path_text = str(_DEFAULT_DOWNLOADS)
        path = str(Path(path_text).expanduser())
        count = int(match.group("count") or 10)
        if not 1 <= count <= 100:
            raise ValueError("The requested file count must be between 1 and 100")
        if text.lower().startswith("summarize"):
            return [json.dumps({"tool": "file", "action": "summarize_files", "args": {"path": path, "limit": count}})]
        plan = [json.dumps({"tool": "file", "action": "list_largest_files", "args": {"path": path, "limit": count}})]
        if "and summarize them" in text.lower():
            plan.append(json.dumps({"tool": "file", "action": "summarize_files", "args": {"path": path, "limit": count}}))
        return plan

    raise ValueError("Unsupported objective. Use 'List the 10 largest files in my Downloads folder and summarize them'.")


def _make_engine(file_tool: FileTool) -> ExecutionEngine:
    registry = ActionRegistry()
    for action_name in file_tool.get_actions():
        registry.register(
            f"file.{action_name}",
            IsolatedToolHandler(file_tool, action_name, timeout_seconds=30.0),
        )
    return ExecutionEngine(registry)


def run_objective(
    objective: str,
    db_path: str | Path,
    mission_id: str | None = None,
    resume: bool = False,
    pause_after_step: int = 0,
    resolve_interrupted_step: str | None = None,
) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    store = MissionStore(db_path)
    if resume:
        if not mission_id:
            print("ERROR: --resume requires --mission-id", file=sys.stderr, flush=True)
            return 2
        try:
            mission = store.load_mission(mission_id)
        except MissionStoreCorruptionError as exc:
            print(f"ERROR: mission checkpoint is corrupt: {exc}", file=sys.stderr, flush=True)
            return 2
        if mission is None:
            print(f"ERROR: mission not found: {mission_id}", file=sys.stderr, flush=True)
            return 2
        if resolve_interrupted_step is not None:
            try:
                mission = store.resolve_interrupted_step(mission_id, resolve_interrupted_step)
            except ValueError as exc:
                print(f"ERROR: {exc}", file=sys.stderr, flush=True)
                return 2
        if mission.state in (MissionState.FAILED, MissionState.COMPLETED, MissionState.WAITING_APPROVAL, MissionState.RECOVERY_REQUIRED):
            print(json.dumps(_mission_summary(mission), indent=2, ensure_ascii=False), flush=True)
            return 0 if mission.state == MissionState.COMPLETED else 1
        mission.state = MissionState.RUNNING
    else:
        try:
            steps = build_plan(objective)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr, flush=True)
            return 2
        mission = Mission(id=mission_id or str(uuid.uuid4()), objective=objective, state=MissionState.RUNNING, steps=steps)
        store.save_mission(mission)

    # Legacy CLI can inspect the user home (including Downloads), but may not
    # mutate files outside that explicitly bounded workspace.
    file_tool = FileTool(workspace_root=Path.home())
    engine = _make_engine(file_tool)
    # Read-only file actions are allowed. Destructive actions fail closed unless an
    # explicit approval flow is added; this CLI intentionally does not auto-approve.
    policy = ExecutionPolicy(
        allow_destructive_from_core=False,
        workspace_root=Path.home(),
    )
    executor = MissionExecutor(
        execution_engine=engine,
        policy=policy,
        persist=store.save_mission,
        record_step=store.record_step,
    )
    print(f"MISSION_ID={mission.id}", flush=True)
    print(f"MISSION_OBJECTIVE={mission.objective}", flush=True)
    print(f"PLANNED_STEPS={len(mission.steps)}", flush=True)

    completed_this_run = 0
    while mission.state == MissionState.RUNNING:
        before = len(mission.completed_steps)
        executor.step(mission)
        after = len(mission.completed_steps)
        if after > before:
            completed_this_run += after - before
            result = next((r for r in mission.step_results if r.get("step_index") == after - 1), {})
            print(f"STEP_{after}_STATUS={result.get('status', 'unknown')}", flush=True)
            print(f"STEP_{after}_EXIT_CODE={result.get('exit_code')}", flush=True)
            print(f"STEP_{after}_STDOUT={result.get('stdout', '')}", flush=True)
            if pause_after_step and completed_this_run >= pause_after_step:
                print("MISSION_CHECKPOINT_READY=1", flush=True)
                time.sleep(120)
        elif mission.state == MissionState.RUNNING:
            # A running step without a terminal result must never spin or be marked done.
            mission.state = MissionState.FAILED
            mission.failure_reason = "Executor returned without completing a step or changing mission state."
            store.save_mission(mission)

    summary = _mission_summary(mission)
    print("MISSION_RESULT=" + json.dumps(summary, ensure_ascii=False), flush=True)
    return 0 if mission.state == MissionState.COMPLETED else 1


def _mission_summary(mission: Mission) -> dict:
    return {
        "mission_id": mission.id,
        "state": mission.state.value,
        "objective": mission.objective,
        "planned_steps": len(mission.steps),
        "completed_steps": len(mission.completed_steps),
        "step_results": mission.step_results,
        "failure_reason": mission.failure_reason,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a real JARVIS Mission Control objective")
    parser.add_argument("--mission", dest="objective", help="Natural-language mission objective")
    parser.add_argument("--mission-db", default=str(Path.home() / ".jarvis" / "crash_missions.sqlite3"), help="SQLite persistence path (shared crash-safe mission journal)")
    parser.add_argument("--mission-id", help="Mission ID for resume or deterministic demos")
    parser.add_argument("--resume", action="store_true", help="Resume a persisted mission")
    parser.add_argument("--pause-after-step", type=int, default=0, help=argparse.SUPPRESS)
    parser.add_argument(
        "--resolve-interrupted-step", choices=("completed", "retry"),
        help="Explicitly resolve a crash-interrupted step after checking its real-world postcondition.",
    )
    args = parser.parse_args(argv)
    if not args.objective and not args.resume:
        parser.error("--mission is required unless --resume is used")
    if args.resolve_interrupted_step and not args.resume:
        parser.error("--resolve-interrupted-step requires --resume")
    if args.resolve_interrupted_step and not args.mission_id:
        parser.error("--resolve-interrupted-step requires --mission-id")
    return run_objective(
        args.objective or "", args.mission_db, args.mission_id, args.resume,
        args.pause_after_step, args.resolve_interrupted_step,
    )


if __name__ == "__main__":
    raise SystemExit(main())
