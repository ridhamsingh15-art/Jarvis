from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from gui.views.missions_view import MissionsView
from mission_control.crash_store import CrashSafeMissionStore
from mission_control.mission import Mission, MissionState
from mission_control.store import MissionStore


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_missions_view_shows_durable_verification_evidence(tmp_path: Path) -> None:
    _app()
    db = tmp_path / "missions.sqlite3"
    store = CrashSafeMissionStore(db)
    store.create_mission("evidence-1", "Read a file", ['{"tool":"file","action":"read_file","args":{"path":"x"}}'])
    store.begin_step(
        mission_id="evidence-1", step_index=0, tool="file", action="read_file",
        args={"path": "x"}, idempotency_key="key-1", side_effecting=False, started_at="now",
    )
    store.finish_step("evidence-1", 0, {
        "status": "completed", "result": "contents", "verification": {"status": "verified", "checks": ["content_matches_disk"]},
        "finished_at": "now",
    })
    store.set_mission_state("evidence-1", "COMPLETED")

    view = MissionsView(db)
    assert view._mission_list.count() >= 1
    item = next(view._mission_list.item(i) for i in range(view._mission_list.count())
                if "evidence-1" in view._mission_list.item(i).text())
    view._mission_list.setCurrentItem(item)
    assert "content_matches_disk" in view._details.toPlainText()
    assert '"mission_verification": "verified"' in view._details.toPlainText()
    view.close()


def test_missions_view_surfaces_pending_approval_without_executing(tmp_path: Path) -> None:
    _app()
    db = tmp_path / "approval.sqlite3"
    store = MissionStore(db)
    step = json.dumps({"tool": "file", "action": "delete", "args": {"path": "unapproved.txt"}})
    store.save_mission(Mission(
        id="approval-1", objective="Delete only after approval", state=MissionState.WAITING_APPROVAL,
        steps=[step], pending_approvals=[step], failure_reason="Requires explicit confirmation",
    ))

    view = MissionsView(db)
    approval_item = next(view._mission_list.item(i) for i in range(view._mission_list.count())
                         if "approval-1" in view._mission_list.item(i).text())
    assert "[APPROVAL]" in approval_item.text()
    view._mission_list.setCurrentItem(approval_item)
    assert "pending_approvals" in view._details.toPlainText()
    assert view._approve_button.isEnabled()
    assert view._run_button.isEnabled() is False
    # The view does not execute anything just by loading or selecting a pending approval.
    assert not (tmp_path / "unapproved.txt").exists()
    view.close()

def test_missions_view_records_crash_safe_approval_then_requires_resume(tmp_path: Path, monkeypatch) -> None:
    from PySide6.QtWidgets import QMessageBox

    _app()
    db = tmp_path / "crash-approval.sqlite3"
    store = CrashSafeMissionStore(db)
    step_text = json.dumps({
        "id": "launch", "tool": "windows", "action": "open_app",
        "args": {"app": "notepad"}, "depends_on": [],
    })
    store.create_mission("crash-approval", "Open Notepad", [step_text])
    store.begin_step(
        mission_id="crash-approval", step_index=0, tool="windows", action="open_app",
        args={"app": "notepad"}, idempotency_key="approval-key", side_effecting=True, started_at="now",
    )
    store.finish_step("crash-approval", 0, {
        "status": "pending_approval", "error": "confirmation required",
        "verification": {"status": "not_run"}, "finished_at": "now",
    })
    store.set_mission_state("crash-approval", "WAITING_APPROVAL", "confirmation required")

    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: QMessageBox.StandardButton.Ok)
    view = MissionsView(db)
    item = next(view._mission_list.item(i) for i in range(view._mission_list.count())
                if "crash-approval" in view._mission_list.item(i).text())
    view._mission_list.setCurrentItem(item)
    assert "1 approval" in item.text()
    assert view._approve_button.isEnabled()
    view._approve_selected()

    mission = store.mission("crash-approval")
    step = store.step("crash-approval", 0)
    assert mission and mission["state"] == "RUNNING"
    assert step and step["status"] == "retry_authorized"
    saved_steps = json.loads(mission["steps_json"])
    assert "user_confirmed" not in json.loads(saved_steps[0])
    assert view._run_button.isEnabled()
    view.close()

def test_missions_view_can_reject_pending_approval_without_execution(tmp_path: Path, monkeypatch) -> None:
    from PySide6.QtWidgets import QMessageBox

    _app()
    db = tmp_path / "reject.sqlite3"
    store = MissionStore(db)
    step = json.dumps({"tool": "email", "action": "send", "args": {"to": "nobody"}})
    store.save_mission(Mission(
        id="reject-1", objective="Send an email only if approved", state=MissionState.WAITING_APPROVAL,
        steps=[step], pending_approvals=[step],
    ))
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: QMessageBox.StandardButton.Ok)

    view = MissionsView(db)
    item = next(view._mission_list.item(i) for i in range(view._mission_list.count())
                if "reject-1" in view._mission_list.item(i).text())
    view._mission_list.setCurrentItem(item)
    assert view._reject_button.isEnabled()
    view._reject_selected()

    rejected = store.load_mission("reject-1")
    assert rejected is not None
    assert rejected.state is MissionState.FAILED
    assert rejected.pending_approvals == []
    assert "no action was executed" in rejected.failure_reason
    view.close()


def test_missions_view_creates_pauses_and_deletes_recurring_schedule(tmp_path: Path, monkeypatch) -> None:
    from datetime import datetime, timezone
    from types import SimpleNamespace

    from PySide6.QtWidgets import QMessageBox

    _app()

    class FakeService:
        def __init__(self):
            self.schedules = []
            self.deleted = []
        def list_schedules(self):
            return list(self.schedules)
        def list_goals(self):
            return []
        def get_plan(self, goal_id):
            return None
        def list_schedule_runs(self, schedule_id=None):
            return []
        def create_schedule(self, description, interval_seconds):
            item = SimpleNamespace(
                schedule_id="schedule-ui-test", description=description,
                interval_seconds=interval_seconds, enabled=True,
                next_run_at=datetime.now(timezone.utc).isoformat(), last_status=None,
            )
            self.schedules.append(item)
            return item
        def set_schedule_enabled(self, schedule_id, enabled):
            item = next(item for item in self.schedules if item.schedule_id == schedule_id)
            item.enabled = enabled
            return item
        def delete_schedule(self, schedule_id):
            self.deleted.append(schedule_id)
            self.schedules = [item for item in self.schedules if item.schedule_id != schedule_id]

    service = FakeService()
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
    view = MissionsView(tmp_path / "missions.sqlite3", autonomy_service=service)

    view._schedule_description.setText("Summarize new project changes")
    view._schedule_interval.setValue(60)
    view._create_schedule()
    assert len(service.schedules) == 1
    assert service.schedules[0].interval_seconds == 3600
    assert view._schedule_list.count() == 1

    view._toggle_schedule()
    assert service.schedules[0].enabled is False
    assert "PAUSED" in view._schedule_list.item(0).text()

    view._delete_schedule()
    assert service.deleted == ["schedule-ui-test"]
    assert view._schedule_list.count() == 0
    view.close()


def test_missions_view_exposes_goal_progress_and_explicit_controls(tmp_path: Path, monkeypatch) -> None:
    from types import SimpleNamespace

    from PySide6.QtWidgets import QMessageBox

    from core.models.primitives import Identifier

    _app()

    class FakeService:
        def __init__(self):
            self.goals = []
            self.started = []
        def list_goals(self):
            return list(self.goals)
        def get_plan(self, goal_id):
            return None
        def create_goal(self, description):
            goal = SimpleNamespace(
                id=Identifier("goal-ui-test"), description=description,
                state=SimpleNamespace(value="CREATED"),
                priority=SimpleNamespace(value="NORMAL"),
                metadata={"execution_results": [], "verification_status": "not_verified"},
            )
            self.goals.append(goal)
            return goal
        def start_goal(self, goal_id):
            self.started.append(goal_id.value)
            self.goals[0].state = SimpleNamespace(value="RUNNING")
        def status(self, goal_id):
            return next(item.state.value for item in self.goals if item.id == goal_id)
        def list_schedules(self):
            return []
        def list_schedule_runs(self, schedule_id=None):
            return []

    service = FakeService()
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: QMessageBox.StandardButton.Ok)
    view = MissionsView(tmp_path / "missions.sqlite3", autonomy_service=service)
    view._goal_description.setText("Inspect the test workspace")
    view._create_goal()

    assert service.started == ["goal-ui-test"]
    assert view._goal_list.count() == 1
    assert "RUNNING" in view._goal_list.item(0).text()
    assert "verification_status" in view._goal_details.toPlainText()
    assert view._goal_pause.isEnabled()
    view.close()


def test_missions_view_approves_duplicate_step_occurrences_independently_and_persists(
    tmp_path: Path, monkeypatch
) -> None:
    from PySide6.QtWidgets import QMessageBox

    _app()
    db = tmp_path / "duplicate-approval-ui.sqlite3"
    step = json.dumps({"tool": "file", "action": "delete", "args": {"path": "temp.txt"}})
    original = Mission(
        id="duplicate-ui-approval",
        objective="Approve each repeated delete separately",
        state=MissionState.WAITING_APPROVAL,
        steps=[step, step],
        pending_approvals=[step],
        pending_approval_indexes=[0, 1],
    )
    store = MissionStore(db)
    store.save_mission(original)
    monkeypatch.setattr(
        QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes
    )
    monkeypatch.setattr(
        QMessageBox, "information", lambda *args, **kwargs: QMessageBox.StandardButton.Ok
    )
    monkeypatch.setattr(
        QMessageBox, "critical", lambda *args, **kwargs: QMessageBox.StandardButton.Ok
    )

    view = MissionsView(db)
    item = next(
        view._mission_list.item(i)
        for i in range(view._mission_list.count())
        if "duplicate-ui-approval" in view._mission_list.item(i).text()
    )
    view._mission_list.setCurrentItem(item)

    # First occurrence: approval must not authorize the second identical step.
    view._step_number.setValue(1)
    view._approve_selected()
    first = MissionStore(db).load_mission("duplicate-ui-approval")
    assert first is not None
    assert first.state is MissionState.WAITING_APPROVAL
    assert first.pending_approval_indexes == [1]
    assert first.approved_step_indexes == [0]
    assert first.pending_approvals == [step]

    # Reloading the view/store must preserve the occurrence-specific decision.
    reloaded_view = MissionsView(db)
    reloaded = MissionStore(db).load_mission("duplicate-ui-approval")
    assert reloaded is not None
    assert reloaded.pending_approval_indexes == [1]
    assert reloaded.approved_step_indexes == [0]

    # A stale repeat approval for the already-approved occurrence must fail closed.
    reloaded_view._mission_list.setCurrentRow(0)
    reloaded_view._step_number.setValue(1)
    reloaded_view._approve_selected()
    stale = MissionStore(db).load_mission("duplicate-ui-approval")
    assert stale is not None
    assert stale.pending_approval_indexes == [1]
    assert stale.approved_step_indexes == [0]
    assert stale.state is MissionState.WAITING_APPROVAL

    # The second explicit approval releases only the remaining occurrence.
    reloaded_view._step_number.setValue(2)
    reloaded_view._approve_selected()
    final = MissionStore(db).load_mission("duplicate-ui-approval")
    assert final is not None
    assert final.state is MissionState.RUNNING
    assert final.pending_approval_indexes == []
    assert final.approved_step_indexes == [0, 1]
    assert final.pending_approvals == []
    view.close()
    reloaded_view.close()
