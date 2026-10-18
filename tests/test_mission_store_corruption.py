import sqlite3

import pytest

from mission_control.mission import Mission, MissionState
from mission_control.store import MissionStore, MissionStoreCorruptionError


def _seed_mission(tmp_path):
    db_path = tmp_path / "corrupt-mission.sqlite3"
    store = MissionStore(db_path)
    mission = Mission(
        id="corrupt-mission",
        objective="isolated corruption test",
        state=MissionState.RUNNING,
        steps=['{"tool":"file","action":"read_file","args":{"path":"example.txt"}}'],
    )
    store.save_mission(mission)
    return db_path, store, mission


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("steps_json", "{broken", "steps_json is not valid JSON"),
        ("completed_json", "{}", "completed_json has an invalid JSON type"),
        ("pending_json", '[1, "approve"]', "pending_json must contain only strings"),
        ("approved_json", "null", "approved_json has an invalid JSON type"),
        ("pending_approval_indexes_json", "{broken", "pending_approval_indexes_json is not valid JSON"),
        ("approved_step_indexes_json", "{}", "approved_step_indexes_json has an invalid JSON type"),
    ],
)
def test_load_mission_rejects_corrupt_or_wrong_shaped_mission_json(tmp_path, column, value, message):
    db_path, store, mission = _seed_mission(tmp_path)
    db = sqlite3.connect(db_path)
    try:
        db.execute(f"UPDATE missions SET {column}=? WHERE id=?", (value, mission.id))
        db.commit()
    finally:
        db.close()

    with pytest.raises(MissionStoreCorruptionError, match=message):
        store.load_mission(mission.id)


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("args_json", "{broken", "mission_steps.args_json is not valid JSON"),
        ("args_json", "[]", "mission_steps.args_json has an invalid JSON type"),
        ("paths_json", "{}", "mission_steps.paths_json has an invalid JSON type"),
    ],
)
def test_load_mission_rejects_corrupt_or_wrong_shaped_step_json(tmp_path, column, value, message):
    db_path, store, mission = _seed_mission(tmp_path)
    store.record_step(
        mission.id,
        0,
        {
            "tool": "file",
            "action": "read_file",
            "args": {"path": "example.txt"},
            "status": "completed",
            "paths": [],
            "result": {"ok": True},
        },
    )
    db = sqlite3.connect(db_path)
    try:
        db.execute(
            f"UPDATE mission_steps SET {column}=? WHERE mission_id=? AND step_index=0",
            (value, mission.id),
        )
        db.commit()
    finally:
        db.close()

    with pytest.raises(MissionStoreCorruptionError, match=message):
        store.load_mission(mission.id)


def test_legacy_cli_refuses_to_resume_corrupt_mission_without_execution(tmp_path, capsys):
    from mission_control.cli import run_objective

    db_path, _store, mission = _seed_mission(tmp_path)
    db = sqlite3.connect(db_path)
    try:
        db.execute("UPDATE missions SET steps_json=? WHERE id=?", ("{broken", mission.id))
        db.commit()
    finally:
        db.close()

    result = run_objective(
        mission.objective,
        db_path,
        mission_id=mission.id,
        resume=True,
    )
    captured = capsys.readouterr()

    assert result == 2
    assert "mission checkpoint is corrupt" in captured.err
    assert "Traceback" not in captured.err


def test_crash_cli_legacy_resume_reports_corrupt_checkpoint_safely(tmp_path, capsys):
    from mission_control.crash_cli import run_objective

    db_path, _store, mission = _seed_mission(tmp_path)
    db = sqlite3.connect(db_path)
    try:
        db.execute("UPDATE missions SET steps_json=? WHERE id=?", ("{broken", mission.id))
        db.commit()
    finally:
        db.close()

    result = run_objective(
        mission.objective,
        db_path,
        mission_id=mission.id,
        resume=True,
        workspace_root=tmp_path,
    )
    captured = capsys.readouterr()

    assert result == 2
    assert "legacy mission checkpoint is corrupt" in captured.out
    assert "Traceback" not in captured.out
