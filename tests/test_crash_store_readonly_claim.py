from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from mission_control.crash_store import CrashSafeMissionStore


def _readonly_args():
    return {
        "mission_id": "readonly-claim",
        "step_index": 0,
        "tool": "file",
        "action": "read_file",
        "args": {"path": "example.txt"},
        "idempotency_key": "stable-read-key",
        "side_effecting": False,
        "started_at": "test-start",
    }


def test_concurrent_read_only_claim_allows_only_one_live_owner(tmp_path):
    db_path = tmp_path / "readonly-claim.sqlite3"
    first = CrashSafeMissionStore(db_path)
    second = CrashSafeMissionStore(db_path)
    first.create_mission("readonly-claim", "read-only claim race", ["read step"])
    barrier = Barrier(2)
    args = _readonly_args()

    def attempt(store):
        barrier.wait(timeout=3)
        return store.begin_step(**args)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, (first, second)))

    assert sorted(results) == [False, True]
    saved = first.step("readonly-claim", 0)
    assert saved is not None
    assert saved["status"] == "started"
    assert saved["attempt_count"] == 1


def test_interrupted_read_only_step_can_be_reclaimed_after_owner_check(tmp_path):
    db_path = tmp_path / "readonly-recovery.sqlite3"
    first = CrashSafeMissionStore(db_path)
    recovery = CrashSafeMissionStore(db_path)
    first.create_mission("readonly-recovery", "read-only recovery", ["read step"])
    args = _readonly_args()
    args["mission_id"] = "readonly-recovery"

    assert first.begin_step(**args) is True
    recovery_args = {**args, "started_at": "recovery-start"}
    assert recovery.begin_step(**recovery_args, allow_readonly_replay=True) is True
    saved = first.step("readonly-recovery", 0)
    assert saved is not None
    assert saved["status"] == "started"
    assert saved["attempt_count"] == 2


def test_read_only_replay_requires_explicit_authorization(tmp_path):
    store = CrashSafeMissionStore(tmp_path / "readonly-no-replay.sqlite3")
    store.create_mission("readonly-no-replay", "read-only no implicit replay", ["read step"])
    args = _readonly_args()
    args["mission_id"] = "readonly-no-replay"

    assert store.begin_step(**args) is True
    assert store.begin_step(**args) is False
    saved = store.step("readonly-no-replay", 0)
    assert saved is not None
    assert saved["attempt_count"] == 1
