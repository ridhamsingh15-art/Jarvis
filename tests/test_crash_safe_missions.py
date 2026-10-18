from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

from core.execution_policy import PolicyVerdict
from mission_control import crash_safe
from mission_control.crash_safe import (
    CrashSafeMissionRunner,
    _redact_url_evidence,
    _verify_action_outcome,
)
from mission_control.crash_store import CrashSafeMissionStore

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable

from core.action_definition import ActionDefinition
from core.registry import Registry
from tools.base_tool import BaseTool


class RegisteredEchoTool(BaseTool):
    """Importable test tool used to verify subprocess-isolated extension actions."""

    @property
    def name(self) -> str:
        return "echo_tool"

    @property
    def description(self) -> str:
        return "A test-only registered echo capability."

    def get_actions(self):
        return {"echo": ActionDefinition(name="echo", description="Echo supplied text.", required_args=["text"])}

    def execute(self, action: str, args: dict) -> str:
        if action != "echo":
            raise ValueError(f"Unexpected action: {action}")
        return args["text"]


def _command(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([PYTHON, str(ROOT / "mission_crash_safe.py"), *args], cwd=ROOT, text=True, capture_output=True, timeout=20, check=False)


def _args(db: Path, mission_id: str, workspace: Path, steps: list[dict], *extra: str) -> list[str]:
    return ["--steps-json", json.dumps(steps, separators=(",", ":")), "--mission-id", mission_id,
            "--mission-db", str(db), "--workspace-root", str(workspace), *extra]


def _wait_for(path: Path, process: subprocess.Popen[str], timeout: float = 15) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists() and path.stat().st_size:
            return
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            raise AssertionError(f"mission exited before marker appeared (code={process.returncode})\n{stdout}\n{stderr}")
        time.sleep(0.05)
    raise AssertionError(f"timed out waiting for real tool marker: {path}")


def _start(args: list[str]) -> subprocess.Popen[str]:
    return subprocess.Popen([PYTHON, str(ROOT / "mission_crash_safe.py"), *args], cwd=ROOT,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

def test_kill_after_real_side_effect_before_result_persistence_never_replays(tmp_path: Path) -> None:
    target, marker, db = tmp_path / "append.log", tmp_path / "after-tool.marker", tmp_path / "mission.sqlite3"
    steps = [{"tool": "file", "action": "append_line", "args": {"path": str(target), "line": "exactly-once"}, "user_confirmed": True}]
    # A plan-supplied confirmation is untrusted; first execution must queue approval.
    pending = _command(*_args(db, "kill-after-side-effect", tmp_path, steps))
    assert pending.returncode == 1, pending.stdout + pending.stderr
    assert '"state": "WAITING_APPROVAL"' in pending.stdout
    assert not target.exists()

    process = _start(_args(db, "kill-after-side-effect", tmp_path, steps,
                           "--approve", "kill-after-side-effect", "--after-execute-marker", str(marker)))
    try:
        _wait_for(marker, process)
        assert target.read_text(encoding="utf-8").splitlines() == ["exactly-once"]
        process.kill()
        process.wait(timeout=5)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        if process.stdout:
            process.stdout.close()
        if process.stderr:
            process.stderr.close()

    restarted = _command(*_args(db, "kill-after-side-effect", tmp_path, steps))
    assert restarted.returncode == 1, restarted.stdout + restarted.stderr
    assert "needs_review" in restarted.stdout
    assert target.read_text(encoding="utf-8").splitlines() == ["exactly-once"]
    store = CrashSafeMissionStore(db)
    mission, step = store.mission("kill-after-side-effect"), store.step("kill-after-side-effect", 0)
    assert mission and mission["state"] == "FAILED"
    assert step and step["status"] == "needs_review" and step["attempt_count"] == 1
    assert "outcome is unknown" in step["error"] and step["idempotency_key"]
    print("KILL_AFTER_SIDE_EFFECT=PASS status=needs_review file_lines=1 attempts=1")

def test_kill_during_long_running_shell_step_flags_unknown_outcome(tmp_path: Path) -> None:
    db, launches = tmp_path / "long.sqlite3", tmp_path / "launches.txt"
    command = "python -c \"import os,time;open('launches.txt','a').write(str(os.getpid())+chr(10));time.sleep(60)\""
    steps = [{"tool": "shell", "action": "run", "args": {"command": command, "cwd": str(tmp_path), "timeout": 90}}]
    pending = _command(*_args(db, "kill-during-shell", tmp_path, steps))
    assert pending.returncode == 1, pending.stdout + pending.stderr
    assert '"state": "WAITING_APPROVAL"' in pending.stdout

    process = _start(_args(db, "kill-during-shell", tmp_path, steps, "--approve", "kill-during-shell"))
    child_pid = None
    try:
        _wait_for(launches, process)
        lines = launches.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        child_pid = int(lines[0])
        process.kill()
        process.wait(timeout=5)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        if process.stdout:
            process.stdout.close()
        if process.stderr:
            process.stderr.close()
        if child_pid:
            try:
                os.kill(child_pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError, OSError):
                pass

    restarted = _command(*_args(db, "kill-during-shell", tmp_path, steps))
    assert restarted.returncode == 1, restarted.stdout + restarted.stderr
    assert "needs_review" in restarted.stdout
    assert len(launches.read_text(encoding="utf-8").splitlines()) == 1
    step = CrashSafeMissionStore(db).step("kill-during-shell", 0)
    assert step and step["status"] == "needs_review" and step["attempt_count"] == 1
    assert step["exit_code"] is None and step["normalized_code"] is None
    print("KILL_DURING_LONG_SHELL=PASS status=needs_review launches=1 attempts=1")

def test_shell_step_persists_real_os_exit_code_not_normalized_code(tmp_path: Path) -> None:
    db = tmp_path / "exit-code.sqlite3"
    steps = [{"tool": "shell", "action": "run", "args": {"command": "python -c \"import sys;print('REAL_OS_OUTPUT');sys.exit(7)\"", "cwd": str(tmp_path)}}]
    pending = _command(*_args(db, "real-exit-code", tmp_path, steps))
    assert pending.returncode == 1, pending.stdout + pending.stderr
    assert '"state": "WAITING_APPROVAL"' in pending.stdout
    result = _command(*_args(db, "real-exit-code", tmp_path, steps, "--approve", "real-exit-code"))
    assert result.returncode == 1, result.stdout + result.stderr
    assert "REAL_OS_OUTPUT" in result.stdout
    step = CrashSafeMissionStore(db).step("real-exit-code", 0)
    assert step and step["status"] == "needs_review" and step["exit_code"] == 7
    assert step["normalized_code"] is None
    print("SHELL_OS_EXIT_CODE=PASS exit_code=7 normalized_code=None")


def test_plan_user_confirmed_does_not_bypass_durable_approval(tmp_path: Path) -> None:
    db = tmp_path / "approval.sqlite3"
    target = tmp_path / "approved.txt"
    steps = [{"tool": "file", "action": "append_line", "args": {"path": str(target), "line": "approved content"}, "user_confirmed": True}]
    pending = _command(*_args(db, "approval-provenance", tmp_path, steps))
    assert pending.returncode == 1, pending.stdout + pending.stderr
    assert '"state": "WAITING_APPROVAL"' in pending.stdout
    assert not target.exists()
    assert CrashSafeMissionStore(db).step("approval-provenance", 0)["status"] == "pending_approval"

    # Re-running a pending mission must preserve its approval request.
    resumed = _command(*_args(db, "approval-provenance", tmp_path, steps))
    assert resumed.returncode == 1, resumed.stdout + resumed.stderr
    assert '"state": "WAITING_APPROVAL"' in resumed.stdout
    assert not target.exists()

    approved = _command("--mission-db", str(db), "--workspace-root", str(tmp_path),
                        "--approve", "approval-provenance", "--step", "1")
    assert approved.returncode == 0, approved.stdout + approved.stderr
    assert "APPROVAL=GRANTED" in approved.stdout
    assert '"state": "COMPLETED"' in approved.stdout
    assert target.read_text(encoding="utf-8") == "approved content\n"
    assert CrashSafeMissionStore(db).step("approval-provenance", 0)["attempt_count"] == 1


def test_wal_step_claim_rejects_second_runner(tmp_path: Path) -> None:
    store = CrashSafeMissionStore(tmp_path / "claim.sqlite3")
    store.create_mission("claim-once", "claim test", ["step"])
    args = {
        "mission_id": "claim-once", "step_index": 0, "tool": "file", "action": "write_file",
        "args": {"path": "inside.txt", "content": "x"}, "idempotency_key": "stable-key",
        "side_effecting": True, "started_at": "test",
    }
    assert store.begin_step(**args) is True
    assert store.begin_step(**args) is False
    step = store.step("claim-once", 0)
    assert step and step["status"] == "started" and step["attempt_count"] == 1


def test_mission_id_cannot_be_reused_for_a_different_plan(tmp_path: Path) -> None:
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    db = tmp_path / "bound-plan.sqlite3"
    first_steps = [{"tool": "file", "action": "list_directory", "args": {"path": str(first_dir)}}]
    second_steps = [{"tool": "file", "action": "list_directory", "args": {"path": str(second_dir)}}]
    first = _command(*_args(db, "bound-plan", tmp_path, first_steps))
    assert first.returncode == 0, first.stdout + first.stderr
    second = _command(*_args(db, "bound-plan", tmp_path, second_steps))
    assert second.returncode == 2, second.stdout + second.stderr
    assert "already bound to a different objective or step plan" in second.stdout
    saved = CrashSafeMissionStore(db).mission("bound-plan")
    assert saved and saved["state"] == "COMPLETED"
    stored_steps = json.loads(saved["steps_json"])
    stored_spec = json.loads(stored_steps[0])
    assert stored_spec["args"]["path"] == str(first_dir)
    assert stored_spec["args"]["path"] != str(second_dir)


def test_crash_safe_cli_resume_uses_saved_plan_and_require_verified(tmp_path: Path) -> None:
    source = tmp_path / "resume.txt"
    source.write_text("resume verified", encoding="utf-8")
    db = tmp_path / "resume.sqlite3"
    steps = [{"tool": "file", "action": "read_file", "args": {"path": str(source)}}]
    first = _command(*_args(db, "resume-plan", tmp_path, steps, "--require-verified"))
    assert first.returncode == 0, first.stdout + first.stderr
    assert "MISSION_VERIFICATION_STATUS=verified" in first.stdout
    resumed = _command("--mission-db", str(db), "--workspace-root", str(tmp_path),
                        "--mission-id", "resume-plan", "--resume", "--require-verified")
    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    assert "MISSION_STATE=COMPLETED" in resumed.stdout

def test_multi_step_plan_resolves_persisted_output_reference(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "largest.txt"
    target.write_text("OUTPUT_REFERENCE_CONTENT", encoding="utf-8")
    db = tmp_path / "reference.sqlite3"
    steps = [
        {
            "id": "discover",
            "tool": "file",
            "action": "list_largest_files",
            "args": {"path": str(workspace), "limit": 1},
            "depends_on": [],
            "expected_outcome": "The largest file path is returned.",
        },
        {
            "id": "read",
            "tool": "file",
            "action": "read_file",
            "args": {"path": {"$ref": "discover.result.files.0.path"}},
            "depends_on": ["discover"],
            "expected_outcome": "The selected file contents are returned.",
        },
    ]
    result = _command(*_args(db, "output-reference", tmp_path, steps))
    assert result.returncode == 0, result.stdout + result.stderr
    store = CrashSafeMissionStore(db)
    assert store.mission("output-reference")["state"] == "COMPLETED"
    first = store.step("output-reference", 0)
    second = store.step("output-reference", 1)
    assert first and first["status"] == "completed"
    assert second and second["status"] == "completed"
    assert second["args"]["path"] == str(target.resolve())
    assert "OUTPUT_REFERENCE_CONTENT" in str(second["result"])
    assert first["verification"]["status"] == "verified"
    assert second["verification"]["status"] == "verified"
    completed = result.stdout
    assert '"verification_status": "verified"' in completed
    print("OUTPUT_REFERENCE=PASS steps=2 resolved_from_persisted_result=true independently_verified=true")


def test_kill_after_read_only_tool_result_retries_same_idempotency_key(tmp_path: Path) -> None:
    (tmp_path / "input.txt").write_text("read-only data", encoding="utf-8")
    marker, db = tmp_path / "after-read.marker", tmp_path / "read-only.sqlite3"
    steps = [{"tool": "file", "action": "list_directory", "args": {"path": str(tmp_path)}}]
    process = _start(_args(db, "read-only-recovery", tmp_path, steps, "--after-execute-marker", str(marker)))
    try:
        _wait_for(marker, process)
        process.kill()
        process.wait(timeout=5)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        if process.stdout:
            process.stdout.close()
        if process.stderr:
            process.stderr.close()

    store = CrashSafeMissionStore(db)
    before = store.step("read-only-recovery", 0)
    assert before and before["status"] == "started" and before["attempt_count"] == 1
    result = _command(*_args(db, "read-only-recovery", tmp_path, steps))
    assert result.returncode == 0, result.stdout + result.stderr
    after, mission = store.step("read-only-recovery", 0), store.mission("read-only-recovery")
    assert after and after["status"] == "completed" and after["attempt_count"] == 2
    assert after["idempotency_key"] == before["idempotency_key"]
    assert mission and mission["state"] == "COMPLETED"

def test_independent_verifier_rejects_fabricated_file_metadata(tmp_path: Path) -> None:
    target = tmp_path / "real.txt"
    target.write_text("real bytes", encoding="utf-8")
    output = json.dumps({"directory": str(tmp_path), "count": 1, "files": [{"path": str(target), "size_bytes": 999}]})
    result = _verify_action_outcome("file", "list_largest_files", {"path": str(tmp_path), "limit": 1}, output)
    assert result["status"] == "failed"
    assert "size" in result["error"].lower()


def test_execute_objective_supports_additional_registered_tools_through_policy_gate(tmp_path: Path) -> None:
    from mission_control.crash_cli import execute_objective

    registry = Registry()
    registry.register(RegisteredEchoTool())
    steps = [json.dumps({"id": "echo", "tool": "echo_tool", "action": "echo", "args": {"text": "registered capability works"}, "depends_on": []})]
    db = tmp_path / "dynamic.sqlite3"
    result = execute_objective(
        "Run the explicitly registered test echo capability", mission_db=db,
        mission_id="dynamic-tool", workspace_root=tmp_path, steps=steps, tool_registry=registry,
    )
    assert result["mission"]["state"] == "WAITING_APPROVAL"
    assert result["steps"][0]["status"] == "pending_approval"
    assert result["steps"][0]["result"] is None

    store = CrashSafeMissionStore(db)
    approved = store.resolve_pending_approval("dynamic-tool", 0, True)
    approved_steps = json.loads(approved["steps_json"])
    result = execute_objective(
        "Run the explicitly registered test echo capability", mission_db=db,
        mission_id="dynamic-tool", workspace_root=tmp_path, steps=approved_steps, tool_registry=registry,
    )
    assert result["mission"]["state"] == "FAILED"
    assert result["steps"][0]["status"] == "needs_review"
    assert result["mission"]["verification_status"] == "partial"
    assert result["steps"][0]["result"] == "registered capability works"


def test_concurrent_approval_and_denial_have_one_atomic_winner(tmp_path: Path) -> None:
    db = tmp_path / "approval-race.sqlite3"
    mission_id = "approval-race"
    store = CrashSafeMissionStore(db)
    steps = [json.dumps({"tool": "file", "action": "append_line", "args": {"path": str(tmp_path / "x.txt"), "line": "x"}})]
    store.create_mission(mission_id, "Resolve one pending approval", steps)
    assert store.begin_step(
        mission_id=mission_id, step_index=0, tool="file", action="append_line",
        args={"path": str(tmp_path / "x.txt"), "line": "x"},
        idempotency_key="approval-race-step", side_effecting=True, started_at="test",
    )
    store.finish_step(mission_id, 0, {
        "status": "pending_approval", "stdout": "", "stderr": "approval required",
        "exit_code": None, "normalized_code": None, "error": "approval required",
        "paths": [], "result": None, "verification": {"status": "not_run"},
        "finished_at": "test",
    })
    store.set_mission_state(mission_id, "WAITING_APPROVAL", "approval required")

    barrier = Barrier(2)

    def decide(approved: bool) -> tuple[bool, str | None]:
        contender = CrashSafeMissionStore(db)
        barrier.wait(timeout=5)
        try:
            contender.resolve_pending_approval(mission_id, 0, approved)
            return approved, None
        except ValueError as exc:
            return approved, str(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(decide, (True, False)))

    winners = [approved for approved, error in results if error is None]
    losers = [(approved, error) for approved, error in results if error is not None]
    assert len(winners) == 1, results
    assert len(losers) == 1 and "not awaiting approval" in losers[0][1], results

    final_mission = store.mission(mission_id)
    final_step = store.step(mission_id, 0)
    assert final_mission is not None and final_step is not None
    if winners[0]:
        assert final_mission["state"] == "RUNNING"
        assert final_step["status"] == "retry_authorized"
        assert final_step["stderr"] == "Operator explicitly approved this step."
    else:
        assert final_mission["state"] == "FAILED"
        assert final_step["status"] == "blocked"
        assert "Denied by operator" in final_step["error"]


def test_concurrent_recovery_retry_and_abandon_have_one_atomic_winner(tmp_path: Path) -> None:
    db = tmp_path / "recovery-race.sqlite3"
    mission_id = "recovery-race"
    store = CrashSafeMissionStore(db)
    steps = [json.dumps({"tool": "shell", "action": "run", "args": {"command": "echo test"}})]
    store.create_mission(mission_id, "Resolve one uncertain side effect", steps)
    assert store.begin_step(
        mission_id=mission_id, step_index=0, tool="shell", action="run",
        args={"command": "echo test"}, idempotency_key="recovery-race-step",
        side_effecting=True, started_at="test",
    )
    store.mark_needs_review(mission_id, 0, "simulated interrupted side effect")
    barrier = Barrier(2)

    def decide(resolution: str) -> tuple[str, str | None]:
        contender = CrashSafeMissionStore(db)
        barrier.wait(timeout=5)
        try:
            contender.resolve_needs_review(mission_id, 0, resolution)
            return resolution, None
        except ValueError as exc:
            return resolution, str(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(decide, ("retry", "abandon")))

    winners = [resolution for resolution, error in results if error is None]
    losers = [(resolution, error) for resolution, error in results if error is not None]
    assert len(winners) == 1, results
    assert len(losers) == 1 and "No needs_review step" in losers[0][1], results
    final_mission = store.mission(mission_id)
    final_step = store.step(mission_id, 0)
    assert final_mission is not None and final_step is not None
    if winners[0] == "retry":
        assert final_mission["state"] == "RUNNING"
        assert final_step["status"] == "retry_authorized"
    else:
        assert final_mission["state"] == "ABANDONED"
        assert final_step["status"] == "abandoned"


def test_crash_safe_confirmation_is_durable_and_requires_separate_resume(tmp_path: Path, monkeypatch) -> None:
    from types import SimpleNamespace

    db = tmp_path / "approval.sqlite3"
    store = CrashSafeMissionStore(db)
    steps = [json.dumps({"id": "launch", "tool": "windows", "action": "open_app", "args": {"app": "notepad"}, "depends_on": []})]
    executed = []

    class Policy:
        def check(self, context):
            verdict = PolicyVerdict.ALLOW if context.user_confirmed else PolicyVerdict.REQUIRE_CONFIRMATION
            return SimpleNamespace(verdict=verdict, reason="operator confirmation required")

    class Engine:
        def execute(self, task):
            executed.append(task.action)
            task.start()
            task.complete("Opened notepad")
            return task

    runner = CrashSafeMissionRunner(store, Engine(), Policy())
    pending = runner.run("approval-mission", "Open Notepad", steps)
    assert pending["mission"]["state"] == "WAITING_APPROVAL"
    assert pending["steps"][0]["status"] == "pending_approval"
    assert executed == []
    assert store.pending_approvals()[0]["mission_id"] == "approval-mission"

    approved = store.resolve_pending_approval("approval-mission", 0, True)
    saved_steps = json.loads(approved["steps_json"])
    assert "user_confirmed" not in json.loads(saved_steps[0])
    assert store.step("approval-mission", 0)["stderr"] == "Operator explicitly approved this step."
    assert approved["state"] == "RUNNING"
    snapshots = iter([set(), {"notepad.exe"}])
    monkeypatch.setattr(crash_safe, "_windows_process_images", lambda: next(snapshots, {"notepad.exe"}))
    completed = runner.run("approval-mission", "Open Notepad", saved_steps)
    assert completed["mission"]["state"] == "COMPLETED"
    assert completed["steps"][0]["verification"]["status"] == "verified"
    assert executed == ["windows.open_app"]


def test_windows_app_verifier_checks_independent_process_inventory(monkeypatch) -> None:
    monkeypatch.setattr(crash_safe, "_windows_process_images", lambda: {"notepad.exe"})
    verified = _verify_action_outcome("windows", "open_app", {"app": "notepad"}, "Opened notepad", baseline_process_images=set())
    assert verified["status"] == "verified"
    assert verified["process_images"] == ["notepad.exe"]

    already_running = _verify_action_outcome(
        "windows", "open_app", {"app": "notepad"}, "Opened notepad",
        baseline_process_images={"notepad.exe"},
    )
    assert already_running["status"] == "partial"
    assert "already running" in already_running["limitation"]

    monkeypatch.setattr(crash_safe, "_windows_process_images", lambda: {"explorer.exe"})
    failed = _verify_action_outcome("windows", "open_app", {"app": "notepad"}, "Opened notepad", baseline_process_images=set())
    assert failed["status"] == "failed"



def test_cdp_verification_is_opt_in(monkeypatch) -> None:
    monkeypatch.delenv("JARVIS_ENABLE_CDP_VERIFICATION", raising=False)
    assert crash_safe._cdp_page_urls() is None
    assert crash_safe._cdp_page_details() is None

def test_browser_verifier_never_claims_page_load_from_process_presence(monkeypatch) -> None:
    monkeypatch.setattr(crash_safe, "_windows_process_images", lambda: {"chrome.exe"})
    monkeypatch.setattr(crash_safe, "_cdp_page_urls", lambda: None)
    result = _verify_action_outcome("browser", "search_google", {"query": "Python asyncio"}, "Searched Google")
    assert result["status"] == "partial"
    assert "page content" in result["limitation"]


def test_browser_verifier_uses_local_cdp_to_confirm_open_page_url(monkeypatch) -> None:
    monkeypatch.setattr(crash_safe, "_windows_process_images", lambda: {"chrome.exe"})
    target_url = "https://docs.python.org/3/library/asyncio-task.html?token=secret-value#private-fragment"
    monkeypatch.setattr(crash_safe, "_cdp_page_urls", lambda: [target_url])
    monkeypatch.setattr(crash_safe, "_cdp_page_details", lambda _expected=None: [{
        "url": target_url, "title": "asyncio — Asynchronous I/O", "ready_state": "complete",
        "text": "Python documentation for asyncio tasks and coroutines",
    }])
    result = _verify_action_outcome("browser", "open_url", {"url": target_url}, "Opened URL")
    assert result["status"] == "verified"
    assert "local_cdp_page_url_matches_target" in result["checks"]
    assert "secret-value" not in json.dumps(result)
    assert "private-fragment" not in json.dumps(result)


def test_browser_verifier_does_not_verify_wrong_cdp_destination(monkeypatch) -> None:
    monkeypatch.setattr(crash_safe, "_windows_process_images", lambda: {"chrome.exe"})
    monkeypatch.setattr(crash_safe, "_cdp_page_urls", lambda: ["https://example.com/"])
    monkeypatch.setattr(crash_safe, "_cdp_page_details", lambda _expected=None: [])
    result = _verify_action_outcome(
        "browser", "open_url", {"url": "https://docs.python.org/3/library/asyncio-task.html"}, "Opened URL"
    )
    assert result["status"] == "partial"
    assert "no inspected open page matched" in result["limitation"]


def test_destructive_action_is_denied_and_persisted_without_mutation(tmp_path: Path) -> None:
    target, db = tmp_path / "keep.txt", tmp_path / "policy.sqlite3"
    target.write_text("must survive", encoding="utf-8")
    steps = [{"tool": "file", "action": "delete", "args": {"path": str(target)}}]
    result = _command(*_args(db, "deny-delete", tmp_path, steps))
    assert result.returncode == 1, result.stdout + result.stderr
    assert "MISSION_STATE=WAITING_APPROVAL" in result.stdout
    assert target.read_text(encoding="utf-8") == "must survive"
    store = CrashSafeMissionStore(db)
    mission, step = store.mission("deny-delete"), store.step("deny-delete", 0)
    assert mission and mission["state"] == "WAITING_APPROVAL"
    assert step and step["status"] == "pending_approval"
    denied = _command("--mission-db", str(db), "--deny", "deny-delete", "--step", "1")
    assert denied.returncode == 0, denied.stdout + denied.stderr
    assert "APPROVAL=DENIED" in denied.stdout
    assert target.read_text(encoding="utf-8") == "must survive"
    assert CrashSafeMissionStore(db).mission("deny-delete")["state"] == "FAILED"
    print("DESTRUCTIVE_POLICY=PASS status=FAILED after explicit denial file_unchanged=true")


def test_destructive_shell_command_is_denied_before_target_mutation(tmp_path: Path) -> None:
    target = tmp_path / "Downloads"
    target.mkdir()
    sentinel = target / "keep.txt"
    sentinel.write_text("must survive", encoding="utf-8")
    db = tmp_path / "shell-policy.sqlite3"
    command = f'rmdir /s /q "{target}"'
    steps = [{"tool": "shell", "action": "run", "args": {"command": command, "cwd": str(tmp_path)}}]

    result = _command(*_args(db, "deny-shell-delete", tmp_path, steps))
    assert result.returncode == 1, result.stdout + result.stderr
    assert "MISSION_STATE=FAILED" in result.stdout
    assert "Execution policy deny" in result.stdout
    assert target.is_dir()
    assert sentinel.read_text(encoding="utf-8") == "must survive"
    step = CrashSafeMissionStore(db).step("deny-shell-delete", 0)
    assert step and step["status"] == "blocked"
    assert "high-risk shell command" in step["error"].lower()
    print("SHELL_DESTRUCTIVE_DENIAL=PASS status=FAILED step=blocked target_unchanged=true")


def test_browser_verifier_checks_semantic_text_and_title_postconditions(monkeypatch) -> None:
    monkeypatch.setattr(crash_safe, "_windows_process_images", lambda: {"msedge.exe"})
    target_url = "https://example.com/docs"
    monkeypatch.setattr(crash_safe, "_cdp_page_urls", lambda: [target_url])
    monkeypatch.setattr(crash_safe, "_cdp_page_details", lambda _expected=None: [{
        "url": target_url, "title": "Documentation", "ready_state": "complete",
        "text": "Welcome to the official documentation. Start here.",
    }])

    verified = _verify_action_outcome(
        "browser", "open_url",
        {"url": target_url, "expected_text": "official documentation", "expected_title": "Documentation"},
        "Opened URL",
    )
    assert verified["status"] == "verified"
    assert verified["expected_text_match"] is True
    assert verified["expected_title_match"] is True
    assert "body_text_sha256" in verified
    assert verified["body_text_excerpt"] == ""

    inspected = _verify_action_outcome(
        "browser", "open_url",
        {"url": target_url, "capture_page_excerpt": True},
        "Opened URL",
    )
    assert inspected["status"] == "verified"
    assert inspected["page_excerpt_captured"] is True
    assert "official documentation" in inspected["body_text_excerpt"]

    failed = _verify_action_outcome(
        "browser", "open_url",
        {"url": target_url, "expected_text": "billing settings"},
        "Opened URL",
    )
    assert failed["status"] == "failed"
    assert failed["expected_text_match"] is False


def test_structured_expected_outcome_is_independently_checked(tmp_path: Path) -> None:
    target = tmp_path / "expected.txt"
    target.write_text("REQUIRED_LITERAL_MARKER", encoding="utf-8")
    db = tmp_path / "expected.sqlite3"
    step = {
        "id": "read",
        "tool": "file",
        "action": "read_file",
        "args": {"path": str(target)},
        "depends_on": [],
        "expected_outcome": f"file_contains:{target}::REQUIRED_LITERAL_MARKER",
    }
    result = _command(*_args(db, "expected-good", tmp_path, [step]))
    assert result.returncode == 0, result.stdout + result.stderr
    stored = CrashSafeMissionStore(db).step("expected-good", 0)
    assert stored and stored["verification"]["expected_outcome_status"] == "verified"
    assert "observed_file_sha256" in stored["verification"]

    bad_step = {**step, "expected_outcome": f"file_contains:{target}::MISSING_LITERAL_MARKER"}
    bad = _command(*_args(db, "expected-bad", tmp_path, [bad_step]))
    assert bad.returncode == 1, bad.stdout + bad.stderr
    failed = CrashSafeMissionStore(db).step("expected-bad", 0)
    assert failed and failed["status"] == "failed"
    assert failed["verification"]["expected_outcome_status"] == "failed"

def test_unverified_step_stops_dependent_steps_and_cannot_complete(tmp_path: Path, monkeypatch) -> None:
    from core.execution_policy import ExecutionPolicy
    from mission_control.crash_cli import _engine

    source = tmp_path / "input.txt"
    source.write_text("must not reach dependent step", encoding="utf-8")
    db = tmp_path / "unverified.sqlite3"
    calls = []

    def partial_verifier(tool, action, args, output, baseline_process_images=None):
        calls.append(action)
        return {"status": "partial", "method": "controlled verification failure"}

    monkeypatch.setattr(crash_safe, "_verify_action_outcome", partial_verifier)
    store = CrashSafeMissionStore(db)
    runner = CrashSafeMissionRunner(store, _engine(tmp_path), ExecutionPolicy())
    steps = [
        json.dumps({"tool": "file", "action": "list_directory", "args": {"path": str(tmp_path)}}),
        json.dumps({"tool": "file", "action": "read_file", "args": {"path": str(source)}}),
    ]

    result = runner.run("unverified-stop", "stop after uncertain result", steps)

    assert result["mission"]["state"] == "FAILED"
    assert result["mission"]["verification_status"] == "partial"
    assert result["steps"][0]["status"] == "failed"
    assert len(result["steps"]) == 1
    assert calls == ["list_directory"]

def test_output_contains_cannot_override_failed_independent_verification() -> None:
    result = crash_safe._verify_declared_expected_outcome(
        {"expected_outcome": "output_contains:SUCCESS"},
        "shell", "run", {"command": "dangerous-operation"}, "SUCCESS",
        {"status": "failed", "error": "independent postcondition failed"},
    )
    assert result["expected_outcome_status"] == "verified"
    assert result["status"] == "failed"
    assert result["error"] == "independent postcondition failed"


def test_url_evidence_redacts_userinfo_query_and_fragment() -> None:
    assert _redact_url_evidence("https://user:password@example.com/private?token=secret#fragment") == "https://example.com/private?[redacted]#[redacted]"
    assert _redact_url_evidence("http://[::1]:9222/json/list?auth=secret") == "http://[::1]:9222/json/list?[redacted]"

def test_after_step_callback_failure_does_not_finish_committed_step_twice(tmp_path: Path) -> None:
    """Projection callback failure must not rewrite an already committed step result."""
    from core.execution_policy import ExecutionPolicy
    from mission_control.crash_cli import _engine

    target = tmp_path / "callback-target.txt"
    target.write_text("stable evidence", encoding="utf-8")
    store = CrashSafeMissionStore(tmp_path / "callback.sqlite3")
    original_finish_step = store.finish_step
    finish_calls: list[tuple[str, int, str]] = []

    def counted_finish_step(mission_id: str, step_index: int, record: dict) -> None:
        finish_calls.append((mission_id, step_index, record["status"]))
        original_finish_step(mission_id, step_index, record)

    store.finish_step = counted_finish_step  # type: ignore[method-assign]
    callback_calls: list[dict] = []

    def broken_projection(_mission_id: str, _index: int, record: dict) -> None:
        callback_calls.append(record)
        raise RuntimeError("projection unavailable")

    runner = CrashSafeMissionRunner(
        store, _engine(tmp_path), ExecutionPolicy(), after_step=broken_projection,
    )
    step = {"tool": "file", "action": "read_file", "args": {"path": str(target)}}
    result = runner.run("callback-failure", "read evidence", [json.dumps(step)])

    persisted = store.step("callback-failure", 0)
    mission = store.mission("callback-failure")
    assert len(finish_calls) == 1, finish_calls
    assert finish_calls[0][2] == "completed"
    assert len(callback_calls) == 1
    assert persisted and persisted["status"] == "completed"
    assert persisted["verification"]["status"] == "verified"
    assert mission and mission["state"] == "FAILED"
    assert "Post-commit callback failed" in mission["failure_reason"]
    assert result["steps"][0]["status"] == "completed"



def test_concurrent_wal_claim_allows_only_one_side_effecting_runner(tmp_path: Path) -> None:
    """Two independent store instances racing the same step must produce one claim."""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    db_path = tmp_path / "concurrent-claim.sqlite3"
    first_store = CrashSafeMissionStore(db_path)
    second_store = CrashSafeMissionStore(db_path)
    first_store.create_mission("concurrent-claim", "claim race", ["write once"])
    barrier = Barrier(2)
    args = {
        "mission_id": "concurrent-claim",
        "step_index": 0,
        "tool": "file",
        "action": "write_file",
        "args": {"path": str(tmp_path / "side-effect.txt"), "content": "once"},
        "idempotency_key": "concurrent-stable-key",
        "side_effecting": True,
        "started_at": "concurrent-test",
    }

    def attempt(store: CrashSafeMissionStore) -> bool:
        barrier.wait(timeout=5)
        return store.begin_step(**args)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, (first_store, second_store)))

    assert sorted(results) == [False, True]
    saved = first_store.step("concurrent-claim", 0)
    assert saved is not None
    assert saved["status"] == "started"
    assert saved["attempt_count"] == 1
