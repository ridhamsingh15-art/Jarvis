import json
import sqlite3

from mission_control.mission import Mission, MissionState, normalize_step_indexes
from mission_control.store import MissionStore


def test_normalize_step_indexes_rejects_booleans_and_malformed_values():
    assert normalize_step_indexes([True, False, "1", 1.0, None, [], -1, 5, 1, 1, 0], 2) == [1, 0]
    assert normalize_step_indexes({"1": True}, 2) == []
    assert normalize_step_indexes([0, 1], True) == []


def test_sqlite_store_does_not_load_json_true_as_approved_step_one(tmp_path):
    db_path = tmp_path / "approval-index.sqlite3"
    store = MissionStore(db_path)
    mission = Mission(
        id="malformed-approval-index",
        objective="isolated malformed checkpoint",
        state=MissionState.WAITING_APPROVAL,
        steps=["read-only step", "destructive step"],
        pending_approval_indexes=[1],
    )
    store.save_mission(mission)
    db = sqlite3.connect(db_path)
    try:
        db.execute("UPDATE missions SET approved_step_indexes_json=? WHERE id=?",
                   (json.dumps([True]), mission.id))
        db.execute("UPDATE missions SET pending_approval_indexes_json=? WHERE id=?",
                   (json.dumps([False, "1", -1, 8, 1, 1]), mission.id))
        db.commit()
    finally:
        db.close()

    restored = store.load_mission(mission.id)
    assert restored is not None
    assert restored.approved_step_indexes == []
    assert restored.pending_approval_indexes == [1]
    assert 1 not in restored.approved_step_indexes


def test_sqlite_store_filters_out_of_range_and_duplicate_approval_indexes(tmp_path):
    db_path = tmp_path / "approval-index-range.sqlite3"
    store = MissionStore(db_path)
    mission = Mission(
        id="approval-index-range",
        objective="isolated malformed checkpoint",
        state=MissionState.WAITING_APPROVAL,
        steps=["one", "two"],
        approved_step_indexes=[1],
    )
    store.save_mission(mission)
    db = sqlite3.connect(db_path)
    try:
        db.execute("UPDATE missions SET approved_step_indexes_json=? WHERE id=?",
                   (json.dumps([1, 1, -1, 2, "0", True]), mission.id))
        db.commit()
    finally:
        db.close()

    restored = store.load_mission(mission.id)
    assert restored is not None
    assert restored.approved_step_indexes == [1]
