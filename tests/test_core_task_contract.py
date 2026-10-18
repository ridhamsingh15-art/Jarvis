import copy
import pickle

import pytest

from core.exceptions import InvalidStateError
from core.task import Task, TaskStatus


@pytest.mark.parametrize("status", list(TaskStatus))
def test_task_accepts_each_enum_status(status):
    task = Task(tool="file", action="read_file", status=status)
    assert task.status is status


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("pending", TaskStatus.PENDING),
        ("PENDING", TaskStatus.PENDING),
        ("completed", TaskStatus.COMPLETED),
        ("COMPLETED", TaskStatus.COMPLETED),
        ("retrying", TaskStatus.RETRYING),
        ("RETRYING", TaskStatus.RETRYING),
    ],
)
def test_task_normalizes_recognized_status_strings(status, expected):
    assert Task(tool="file", action="read_file", status=status).status is expected


@pytest.mark.parametrize("status", ["", "UNKNOWN", "success", "completed "])
def test_task_rejects_unknown_status_instead_of_defaulting_to_pending(status):
    with pytest.raises(ValueError, match="Unknown task status"):
        Task(tool="file", action="read_file", status=status)


@pytest.mark.parametrize("status", [None, 1, object()])
def test_task_rejects_non_string_non_enum_status(status):
    with pytest.raises(TypeError, match="status must be a TaskStatus"):
        Task(tool="file", action="read_file", status=status)


def test_transition_after_public_status_corruption_fails_with_domain_error():
    task = Task(tool="file", action="read_file")
    task.status = "not-a-valid-status"

    with pytest.raises(InvalidStateError, match="invalid status"):
        task.start()


def test_transition_rejects_invalid_target_type():
    task = Task(tool="file", action="read_file")

    with pytest.raises(TypeError, match="target must be a TaskStatus"):
        task._transition("RUNNING")


def test_task_deepcopy_rebuilds_independent_state_lock():
    original = Task(tool="file", action="read_file")
    original.start()

    cloned = copy.deepcopy(original)

    assert cloned is not original
    assert cloned.status is TaskStatus.RUNNING
    assert cloned._state_lock is not original._state_lock
    cloned.complete({"content": "copied"})
    assert cloned.status is TaskStatus.COMPLETED
    assert original.status is TaskStatus.RUNNING


def test_task_pickle_roundtrip_rebuilds_state_lock():
    original = Task(tool="file", action="write_file", args={"path": "file.txt"})
    original.start()

    restored = pickle.loads(pickle.dumps(original))

    assert restored.status is TaskStatus.RUNNING
    assert restored.args == {"path": "file.txt"}
    assert restored._state_lock is not original._state_lock
    restored.fail("isolated failure")
    assert restored.status is TaskStatus.FAILED
    assert original.status is TaskStatus.RUNNING
