import json
import sqlite3

import pytest

from mission_control.crash_store import (
    CrashSafeMissionStore,
    CrashSafeStoreCorruptionError,
)


def _seed_step(tmp_path, mission_id="crash-corruption"):
    db_path = tmp_path / f"{mission_id}.sqlite3"
    store = CrashSafeMissionStore(db_path)
    spec = {"tool": "file", "action": "read_file", "args": {"path": "example.txt"}}
    store.create_mission(mission_id, "isolated corruption test", [json.dumps(spec)])
    assert store.begin_step(
        mission_id=mission_id,
        step_index=0,
        tool="file",
        action="read_file",
        args={"path": "example.txt"},
        idempotency_key=f"{mission_id}:step0",
        side_effecting=False,
        started_at="test",
    )
    store.finish_step(
        mission_id,
        0,
        {
            "status": "pending_approval",
            "stdout": "",
            "stderr": "approval required",
            "exit_code": None,
            "normalized_code": None,
            "error": "approval required",
            "paths": [],
            "result": None,
            "verification": {"status": "not_run"},
            "finished_at": "test",
        },
    )
    store.set_mission_state(mission_id, "WAITING_APPROVAL", "approval required")
    return db_path, store, mission_id


def _corrupt_column(db_path, table, column, value, mission_id, step_index=0):
    db = sqlite3.connect(db_path)
    try:
        if table == "crash_steps":
            db.execute(
                f"UPDATE {table} SET {column}=? WHERE mission_id=? AND step_index=?",
                (value, mission_id, step_index),
            )
        else:
            db.execute(
                f"UPDATE {table} SET {column}=? WHERE mission_id=?",
                (value, mission_id),
            )
        db.commit()
    finally:
        db.close()


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("args_json", "{bad", "crash_steps.args_json is not valid JSON"),
        ("args_json", "[]", "crash_steps.args_json has an invalid JSON type"),
        ("paths_json", "{}", "crash_steps.paths_json has an invalid JSON type"),
        ("result_json", "{bad", "crash_steps.result_json is not valid JSON"),
        ("verification_json", "[]", "crash_steps.verification_json has an invalid JSON type"),
    ],
)
def test_step_loader_rejects_corrupt_or_wrong_shaped_json(tmp_path, column, value, message):
    db_path, store, mission_id = _seed_step(tmp_path)
    _corrupt_column(db_path, "crash_steps", column, value, mission_id)

    with pytest.raises(CrashSafeStoreCorruptionError, match=message):
        store.step(mission_id, 0)


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("{bad", "crash_missions.steps_json is not valid JSON"),
        ("{}", "crash_missions.steps_json has an invalid JSON type"),
        ('[1]', "crash_missions.steps_json must contain only strings"),
        ('["{bad"]', "crash_missions.steps_json step is not valid JSON"),
        ('["[]"]', "crash_missions.steps_json step has an invalid JSON type"),
    ],
)
def test_approval_rejects_corrupt_plan_without_authorizing_step(tmp_path, value, message):
    db_path, store, mission_id = _seed_step(tmp_path)
    _corrupt_column(db_path, "crash_missions", "steps_json", value, mission_id)

    with pytest.raises(CrashSafeStoreCorruptionError, match=message):
        store.resolve_pending_approval(mission_id, 0, True)

    # A corrupt persisted plan must remain pending; corruption never grants approval.
    with sqlite3.connect(db_path) as db:
        state = db.execute(
            "SELECT state FROM crash_missions WHERE mission_id=?", (mission_id,)
        ).fetchone()[0]
        status = db.execute(
            "SELECT status FROM crash_steps WHERE mission_id=? AND step_index=0",
            (mission_id,),
        ).fetchone()[0]
    assert state == "WAITING_APPROVAL"
    assert status == "pending_approval"


def test_steps_listing_propagates_domain_error_on_corrupt_row(tmp_path):
    db_path, store, mission_id = _seed_step(tmp_path)
    _corrupt_column(db_path, "crash_steps", "args_json", "{bad", mission_id)

    with pytest.raises(CrashSafeStoreCorruptionError, match="crash_steps.args_json"):
        store.steps(mission_id)


def test_runner_fails_closed_on_corrupt_step_before_invoking_executor(tmp_path):
    from core.execution_policy import ExecutionPolicy
    from mission_control.crash_safe import CrashSafeMissionRunner

    db_path, store, mission_id = _seed_step(tmp_path, "runner-corrupt-step")
    _corrupt_column(db_path, "crash_steps", "args_json", "{bad", mission_id)
    calls = []

    class NeverExecute:
        def execute(self, _task):
            calls.append("executed")

    steps = [
        json.dumps(
            {"tool": "file", "action": "read_file", "args": {"path": "example.txt"}}
        )
    ]
    runner = CrashSafeMissionRunner(
        store,
        NeverExecute(),
        ExecutionPolicy(allow_destructive_from_core=False, workspace_root=tmp_path),
    )

    result = runner.run(mission_id, "isolated corruption test", steps)

    assert result["mission"]["state"] == "FAILED"
    assert result["mission"]["verification_status"] == "not_verified"
    assert "stored crash-safe mission data is corrupt" in result["error"].lower()
    assert calls == []


def test_crash_cli_reports_corrupt_step_without_traceback_or_execution(tmp_path, capsys):
    from mission_control.crash_cli import run_objective

    db_path, _store, mission_id = _seed_step(tmp_path, "cli-corrupt-step")
    _corrupt_column(db_path, "crash_steps", "args_json", "{bad", mission_id)

    result = run_objective(
        "isolated corruption test",
        db_path,
        mission_id=mission_id,
        resume=True,
        workspace_root=tmp_path,
    )
    captured = capsys.readouterr()

    assert result == 2
    assert '"failure_class": "persistence_corruption"' in captured.out
    assert "Traceback" not in captured.out
    with sqlite3.connect(db_path) as db:
        state = db.execute(
            "SELECT state FROM crash_missions WHERE mission_id=?", (mission_id,)
        ).fetchone()[0]
    assert state == "FAILED"
