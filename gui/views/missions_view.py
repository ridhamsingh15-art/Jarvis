"""Mission Control GUI: durable mission evidence and explicit review/approval actions."""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from mission_control.crash_store import CrashSafeMissionStore

_USER_ROLE = int(Qt.ItemDataRole.UserRole)


class MissionsView(QWidget):
    """Read durable mission journals and require explicit operator actions."""

    def __init__(self, mission_db: str | Path | None = None, registry: Any = None,
                 execution_policy: Any = None, autonomy_service: Any = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._autonomy_service = autonomy_service
        configured_db = mission_db or os.environ.get("JARVIS_MISSION_DB")
        self._mission_db = Path(configured_db or (Path.home() / ".jarvis" / "crash_missions.sqlite3")).expanduser()
        self._registry = registry
        self._execution_policy = execution_policy
        self._items: dict[tuple[str, str], dict[str, Any]] = {}
        self._build_ui()
        self.refresh()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(3000)
        self._refresh_timer.timeout.connect(self.refresh)
        self._refresh_timer.start()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(10)

        title = QLabel("Mission Control")
        title.setProperty("class", "viewTitle")
        root.addWidget(title)
        subtitle = QLabel("Persisted execution evidence, verification status, approvals, and interrupted actions.")
        subtitle.setProperty("class", "viewSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        goal_title = QLabel("Autonomous goals")
        goal_title.setProperty("class", "viewSubtitle")
        root.addWidget(goal_title)
        goal_form = QHBoxLayout()
        self._goal_description = QLineEdit()
        self._goal_description.setPlaceholderText("Goal for JARVIS to plan, execute, verify, and checkpoint")
        self._goal_create = QPushButton("Create goal")
        self._goal_create.clicked.connect(self._create_goal)
        goal_form.addWidget(self._goal_description, 1)
        goal_form.addWidget(self._goal_create)
        root.addLayout(goal_form)
        goal_body = QHBoxLayout()
        self._goal_list = QListWidget()
        self._goal_list.setMaximumHeight(110)
        self._goal_list.currentItemChanged.connect(self._goal_selection_changed)
        goal_body.addWidget(self._goal_list, 1)
        self._goal_details = QTextEdit()
        self._goal_details.setReadOnly(True)
        self._goal_details.setMaximumHeight(110)
        self._goal_details.setPlaceholderText("Select a goal to inspect progress, evidence, and intervention state.")
        goal_body.addWidget(self._goal_details, 1)
        root.addLayout(goal_body)
        goal_actions = QHBoxLayout()
        self._goal_start = QPushButton("Start")
        self._goal_start.clicked.connect(lambda: self._goal_action("start"))
        self._goal_pause = QPushButton("Pause")
        self._goal_pause.clicked.connect(lambda: self._goal_action("pause"))
        self._goal_resume = QPushButton("Resume")
        self._goal_resume.clicked.connect(lambda: self._goal_action("resume"))
        self._goal_cancel = QPushButton("Cancel")
        self._goal_cancel.clicked.connect(lambda: self._goal_action("cancel"))
        for button in (self._goal_start, self._goal_pause, self._goal_resume, self._goal_cancel):
            goal_actions.addWidget(button)
        goal_actions.addStretch()
        root.addLayout(goal_actions)
        self._refresh_goals()

        schedule_title = QLabel("Scheduled goals")
        schedule_title.setProperty("class", "viewSubtitle")
        root.addWidget(schedule_title)
        schedule_form = QHBoxLayout()
        self._schedule_description = QLineEdit()
        self._schedule_description.setPlaceholderText("Goal to repeat, e.g. summarize new project changes")
        self._schedule_interval = QSpinBox()
        self._schedule_interval.setRange(1, 525_600)
        self._schedule_interval.setValue(1_440)
        self._schedule_interval.setSuffix(" min")
        self._schedule_create = QPushButton("Create recurring goal")
        self._schedule_create.clicked.connect(self._create_schedule)
        schedule_form.addWidget(self._schedule_description, 1)
        schedule_form.addWidget(QLabel("Every:"))
        schedule_form.addWidget(self._schedule_interval)
        schedule_form.addWidget(self._schedule_create)
        root.addLayout(schedule_form)

        schedule_body = QHBoxLayout()
        self._schedule_list = QListWidget()
        self._schedule_list.setMaximumHeight(105)
        self._schedule_list.currentItemChanged.connect(self._schedule_selection_changed)
        schedule_body.addWidget(self._schedule_list, 1)
        self._schedule_details = QTextEdit()
        self._schedule_details.setReadOnly(True)
        self._schedule_details.setMaximumHeight(105)
        self._schedule_details.setPlaceholderText("Select a schedule to inspect its run history.")
        schedule_body.addWidget(self._schedule_details, 1)
        root.addLayout(schedule_body)
        schedule_actions = QHBoxLayout()
        self._schedule_toggle = QPushButton("Pause schedule")
        self._schedule_toggle.setToolTip("Pausing prevents future occurrences. An already-running goal continues.")
        self._schedule_toggle.clicked.connect(self._toggle_schedule)
        self._schedule_delete = QPushButton("Delete schedule")
        self._schedule_delete.clicked.connect(self._delete_schedule)
        schedule_actions.addWidget(self._schedule_toggle)
        schedule_actions.addWidget(self._schedule_delete)
        schedule_actions.addStretch()
        root.addLayout(schedule_actions)
        self._refresh_schedules()

        toolbar = QHBoxLayout()
        self._refresh_button = QPushButton("Refresh")
        self._refresh_button.clicked.connect(self.refresh)
        toolbar.addWidget(self._refresh_button)
        toolbar.addStretch()
        toolbar.addWidget(QLabel("Review step:"))
        self._step_number = QSpinBox()
        self._step_number.setMinimum(1)
        self._step_number.setMaximum(999)
        toolbar.addWidget(self._step_number)
        root.addLayout(toolbar)

        body = QHBoxLayout()
        self._mission_list = QListWidget()
        self._mission_list.setMinimumWidth(280)
        self._mission_list.currentItemChanged.connect(self._selection_changed)
        self._step_number.valueChanged.connect(lambda _value: self._selection_changed(self._mission_list.currentItem(), None))
        body.addWidget(self._mission_list, 1)

        self._details = QTextEdit()
        self._details.setReadOnly(True)
        self._details.setPlaceholderText("Select a mission to inspect its persisted evidence.")
        body.addWidget(self._details, 2)
        root.addLayout(body, 1)

        actions = QHBoxLayout()
        self._approve_button = QPushButton("Approve pending step")
        self._approve_button.clicked.connect(self._approve_selected)
        self._reject_button = QPushButton("Reject pending step")
        self._reject_button.clicked.connect(self._reject_selected)
        self._run_button = QPushButton("Resume approved mission")
        self._run_button.clicked.connect(self._run_next_legacy_step)
        self._retry_button = QPushButton("Retry reviewed step")
        self._retry_button.clicked.connect(self._resolve_review_retry)
        self._abandon_button = QPushButton("Abandon reviewed step")
        self._abandon_button.clicked.connect(self._resolve_review_abandon)
        for button in (self._approve_button, self._reject_button, self._run_button, self._retry_button, self._abandon_button):
            actions.addWidget(button)
        root.addLayout(actions)
        self._set_action_buttons(None)

    def refresh(self) -> None:
        previous = self._mission_list.currentItem()
        previous_data = previous.data(_USER_ROLE) if previous else None
        self._mission_list.clear()
        self._items.clear()
        self._details.clear()
        try:
            store = CrashSafeMissionStore(self._mission_db)
            for mission in store.missions(200):
                mission_id = str(mission["mission_id"])
                key = ("crash", mission_id)
                self._items[key] = mission
                mission_steps = store.steps(mission_id)
                review_count = sum(1 for row in mission_steps if row.get("status") == "needs_review")
                approval_count = sum(1 for row in mission_steps if row.get("status") == "pending_approval")
                verification = self._mission_verification(mission_steps, mission.get("state"))
                label = f"[MISSION] {mission_id} · {mission.get('state')} · {verification}"
                if review_count:
                    label += f" · {review_count} review"
                if approval_count:
                    label += f" · {approval_count} approval"
                item = QListWidgetItem(label)
                item.setData(_USER_ROLE, key)
                self._mission_list.addItem(item)

            # The legacy MissionStore uses the same SQLite file and retains approval queues.
            try:
                with closing(sqlite3.connect(f"file:{self._mission_db.resolve().as_posix()}?mode=ro", uri=True, timeout=2)) as db:
                    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                    if "missions" in tables:
                        rows = db.execute(
                            "SELECT id, objective, state, pending_json, failure_reason FROM missions "
                            "WHERE state IN ('WAITING_APPROVAL','RUNNING','RECOVERY_REQUIRED') "
                            "OR pending_json NOT IN ('[]','') ORDER BY updated_at DESC LIMIT 200"
                        ).fetchall()
                        for mission_id, objective, state, pending_json, failure_reason in rows:
                            if ("crash", str(mission_id)) in self._items:
                                continue
                            try:
                                pending = json.loads(pending_json or "[]")
                            except json.JSONDecodeError:
                                pending = []
                            # Keep running legacy missions visible so an approved mission can be advanced explicitly.
                            key = ("approval", str(mission_id))
                            record = {"mission_id": mission_id, "objective": objective, "state": state,
                                      "pending_approvals": pending, "failure_reason": failure_reason}
                            self._items[key] = record
                            label = "[APPROVAL]" if pending or state == "WAITING_APPROVAL" else "[LEGACY]"
                            item = QListWidgetItem(f"{label} {mission_id} · {state} · {len(pending)} pending")
                            item.setData(_USER_ROLE, key)
                            self._mission_list.addItem(item)
            except (sqlite3.Error, OSError):
                # Crash-safe mission evidence remains available even if the legacy schema is absent.
                pass
        except (OSError, sqlite3.Error, ValueError) as exc:
            self._details.setPlainText(f"Could not load mission journal: {type(exc).__name__}: {exc}")

        if previous_data:
            for index in range(self._mission_list.count()):
                item = self._mission_list.item(index)
                if item.data(_USER_ROLE) == previous_data:
                    self._mission_list.setCurrentItem(item)
                    break
        if self._mission_list.currentItem() is None and self._mission_list.count():
            self._mission_list.setCurrentRow(0)
        if not self._mission_list.count():
            self._details.setPlainText(f"No persisted missions or pending approvals found.\nJournal: {self._mission_db}")
        self._selection_changed(self._mission_list.currentItem(), None)
        self._refresh_goals()
        self._refresh_schedules()

    @staticmethod
    def _mission_verification(steps: list[dict[str, Any]], state: Any) -> str:
        if not steps:
            return "not_verified"
        statuses = [row.get("verification", {}).get("status", "not_supported") for row in steps]
        if state == "COMPLETED" and statuses and all(status == "verified" for status in statuses):
            return "verified"
        if any(status in {"verified", "partial"} for status in statuses):
            return "partial"
        return "not_verified"

    def _selection_changed(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        key = current.data(_USER_ROLE) if current else None
        record = self._items.get(key, {}) if key else {}
        if not key:
            self._details.clear()
            self._set_action_buttons(None)
            return
        if key[0] == "crash":
            store = CrashSafeMissionStore(self._mission_db)
            mission = store.mission(key[1]) or record
            steps = store.steps(key[1])
            payload = {
                "mission": mission,
                "mission_verification": self._mission_verification(steps, mission.get("state")),
                "steps": [
                    {
                        "step_number": row.get("step_index", 0) + 1,
                        "tool": row.get("tool"), "action": row.get("action"),
                        "status": row.get("status"), "args": row.get("args"),
                        "verification": row.get("verification"), "paths": row.get("paths"),
                        "exit_code": row.get("exit_code"), "error": row.get("error"),
                        "result_preview": str(row.get("result"))[:3000],
                        "started_at": row.get("started_at"), "finished_at": row.get("finished_at"),
                    } for row in steps
                ],
            }
            self._details.setPlainText(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
        else:
            try:
                from mission_control.store import MissionStore
                mission = MissionStore(self._mission_db).load_mission(key[1])
                if mission is not None:
                    record = {
                        "mission_id": mission.id, "objective": mission.objective,
                        "state": mission.state.value, "pending_approvals": mission.pending_approvals,
                        "approved_steps": mission.approved_steps, "failure_reason": mission.failure_reason,
                        "steps": mission.step_results,
                    }
                    self._items[key] = {**self._items[key], "state": mission.state.value,
                                        "pending_approvals": mission.pending_approvals}
            except (OSError, sqlite3.Error, ValueError):
                pass
            self._details.setPlainText(json.dumps(record, indent=2, ensure_ascii=False, default=str))
        self._set_action_buttons(key)

    def _set_action_buttons(self, key: tuple[str, str] | None) -> None:
        record = self._items.get(key, {}) if key else {}
        is_legacy_approval = bool(key and key[0] == "approval" and record.get("pending_approvals"))
        is_crash = bool(key and key[0] == "crash")
        review = False
        pending_approval = False
        if is_crash:
            try:
                selected_step = self._step_number.value() - 1
                rows = CrashSafeMissionStore(self._mission_db).steps(key[1])
                review = any(row.get("status") == "needs_review" and row.get("step_index") == selected_step for row in rows)
                pending_approval = any(row.get("status") == "pending_approval" and row.get("step_index") == selected_step for row in rows)
            except (OSError, sqlite3.Error):
                review = False
                pending_approval = False
        self._approve_button.setEnabled(is_legacy_approval or pending_approval)
        self._reject_button.setEnabled(is_legacy_approval or pending_approval)
        self._run_button.setEnabled(bool(key and ((key[0] == "approval" and record.get("state") == "RUNNING") or (key[0] == "crash" and record.get("state") == "RUNNING"))))
        self._retry_button.setEnabled(review)
        self._abandon_button.setEnabled(review)

    def _approve_selected(self) -> None:
        current = self._mission_list.currentItem()
        key = current.data(_USER_ROLE) if current else None
        if not key:
            return
        answer = QMessageBox.question(
            self, "Approve mission step",
            "Approve this exact pending step? This records explicit authorization; the step will not run until you separately choose Resume approved mission.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            if key[0] == "crash":
                store = CrashSafeMissionStore(self._mission_db)
                store.resolve_pending_approval(key[1], self._step_number.value() - 1, True)
            elif key[0] == "approval":
                from mission_control.mission import MissionState
                from mission_control.store import MissionStore
                legacy = MissionStore(self._mission_db)
                mission = legacy.load_mission(key[1])
                if mission is None:
                    raise ValueError("Mission no longer exists.")
                step_index = self._step_number.value() - 1
                if not 0 <= step_index < len(mission.steps):
                    raise ValueError("Selected step index is outside the persisted plan.")
                step_text = mission.steps[step_index]
                from mission_control.approval import ApprovalManager

                approvals = ApprovalManager()
                if step_index in mission.pending_approval_indexes:
                    approvals.approve_step(mission, step_index)
                else:
                    # Legacy checkpoints may only have text-based approval state.
                    # Allow fallback only when the selected text is uniquely identifiable.
                    if step_text not in mission.pending_approvals:
                        raise ValueError("Selected step is not awaiting approval.")
                    if mission.steps.count(step_text) != 1:
                        raise ValueError("This legacy approval is ambiguous for repeated step text; it must be re-created with indexed approval state.")
                    approvals.approve(mission, step_text)

                # The shared approval manager is the single source of truth for
                # indexed/text compatibility and state transitions.
                if step_index in mission.pending_approval_indexes:
                    raise ValueError("Selected step is still awaiting approval.")
                if step_index not in mission.approved_step_indexes and step_text not in mission.approved_steps:
                    raise ValueError("Approval was not recorded for the selected step.")
                mission.failure_reason = "" if mission.state == MissionState.RUNNING else mission.failure_reason
                legacy.save_mission(mission)
            else:
                return
            QMessageBox.information(self, "Approval recorded", "Approval was durably recorded. No action was executed by the approval button.")
        except (OSError, sqlite3.Error, ValueError, TypeError) as exc:
            QMessageBox.critical(self, "Approval failed", f"{type(exc).__name__}: {exc}")
        self.refresh()

    def _reject_selected(self) -> None:
        current = self._mission_list.currentItem()
        key = current.data(_USER_ROLE) if current else None
        if not key:
            return
        answer = QMessageBox.question(
            self, "Reject pending step",
            "Reject this pending step and record that no action was authorized?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            if key[0] == "crash":
                CrashSafeMissionStore(self._mission_db).resolve_pending_approval(
                    key[1], self._step_number.value() - 1, False,
                )
            elif key[0] == "approval":
                from mission_control.mission import MissionState
                from mission_control.store import MissionStore
                store = MissionStore(self._mission_db)
                mission = store.load_mission(key[1])
                if mission is None or not mission.pending_approvals:
                    raise ValueError("Mission has no pending approval.")
                mission.pending_approvals = []
                mission.state = MissionState.FAILED
                mission.failure_reason = "Pending step rejected by operator; no action was executed."
                store.save_mission(mission)
            else:
                return
            QMessageBox.information(self, "Step rejected", "The rejection was durably recorded. No action was executed.")
        except (OSError, sqlite3.Error, ValueError, TypeError) as exc:
            QMessageBox.critical(self, "Rejection failed", f"{type(exc).__name__}: {exc}")
        self.refresh()

    def _run_next_legacy_step(self) -> None:
        current = self._mission_list.currentItem()
        key = current.data(_USER_ROLE) if current else None
        if not key:
            return
        if key[0] == "crash":
            answer = QMessageBox.question(
                self, "Resume approved mission",
                "Resume this durable mission through the crash-safe runner? Remaining policy-allowed steps may execute; unresolved approvals will pause again.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            try:
                store = CrashSafeMissionStore(self._mission_db)
                mission = store.mission(key[1])
                if mission is None or mission.get("state") != "RUNNING":
                    raise ValueError("Mission is not in RUNNING state.")
                saved_steps = json.loads(mission.get("steps_json", "[]"))
                if not isinstance(saved_steps, list) or not all(isinstance(step, str) for step in saved_steps):
                    raise ValueError("Persisted mission plan is invalid.")
                from core.execution_policy import ExecutionPolicy
                from mission_control.crash_cli import _engine
                from mission_control.crash_safe import CrashSafeMissionRunner
                list_tools = getattr(self._registry, "list_tools", None)
                registered_tools = frozenset(list_tools()) if callable(list_tools) else frozenset()
                result = CrashSafeMissionRunner(
                    store, _engine(Path.home(), tool_registry=self._registry),
                    ExecutionPolicy(allow_destructive_from_core=False, registered_tools=registered_tools),
                ).run(key[1], mission["objective"], saved_steps)
                state = (result.get("mission") or {}).get("state", "UNKNOWN")
                QMessageBox.information(self, "Mission resumed", f"Mission state: {state}")
            except (OSError, sqlite3.Error, ValueError, TypeError, RuntimeError) as exc:
                QMessageBox.critical(self, "Resume failed", f"{type(exc).__name__}: {exc}")
            self.refresh()
            return
        if key[0] != "approval":
            return
        if self._registry is None or self._execution_policy is None:
            QMessageBox.warning(self, "Execution unavailable", "The configured tool registry or execution policy is unavailable. Nothing was executed.")
            return
        answer = QMessageBox.question(
            self, "Run next mission step",
            "Run exactly one next uncompleted step through the configured registered tools and execution policy?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            from core.executor.action_registry import ActionRegistry
            from core.executor.executor import ExecutionEngine
            from core.executor.isolated_handler import IsolatedToolHandler
            from mission_control.execution import MissionExecutor
            from mission_control.store import MissionStore

            store = MissionStore(self._mission_db)
            mission = store.load_mission(key[1])
            if mission is None or mission.state.value != "RUNNING":
                raise ValueError("Mission is not in RUNNING state.")
            action_registry = ActionRegistry()
            for tool_name in self._registry.list_tools():
                tool = self._registry.get_executor(tool_name)
                if tool is None:
                    continue
                for action_name in tool.get_actions():
                    timeout_seconds = max(
                        30.0, float(getattr(tool, "execution_timeout_seconds", 25.0)) + 5.0
                    )
                    action_registry.register(
                        f"{tool_name}.{action_name}",
                        IsolatedToolHandler(tool, action_name, timeout_seconds=timeout_seconds),
                    )
            engine = ExecutionEngine(action_registry)
            registered_names = frozenset(self._registry.list_tools())
            policy = self._execution_policy.with_registered_tools(registered_names)
            executor = MissionExecutor(
                execution_engine=engine, policy=policy,
                persist=store.save_mission, record_step=store.record_step,
            )
            before = len(mission.completed_steps)
            executor.step(mission)
            state = mission.state.value
            completed = len(mission.completed_steps) - before
            QMessageBox.information(
                self, "Mission step result",
                f"State: {state}\nNewly completed steps: {completed}\n{mission.failure_reason}",
            )
        except (OSError, sqlite3.Error, ValueError, TypeError, RuntimeError) as exc:
            QMessageBox.critical(self, "Mission step failed", f"{type(exc).__name__}: {exc}")
        self.refresh()

    def _resolve_review_retry(self) -> None:
        self._resolve_review("retry")

    def _resolve_review_abandon(self) -> None:
        self._resolve_review("abandon")

    def _resolve_review(self, resolution: str) -> None:
        current = self._mission_list.currentItem()
        key = current.data(_USER_ROLE) if current else None
        if not key or key[0] != "crash":
            return
        step_index = self._step_number.value() - 1
        step = CrashSafeMissionStore(self._mission_db).step(key[1], step_index)
        if not step or step.get("status") != "needs_review":
            QMessageBox.warning(self, "No review required", "The selected step is not awaiting review.")
            self.refresh()
            return
        if resolution == "retry":
            prompt = (
                f"Step {step_index + 1} ({step.get('tool')}.{step.get('action')}) has an unknown prior outcome. "
                "Inspect the real-world result first. Retry may repeat a side effect. Continue only if you verified it did not happen."
            )
        else:
            prompt = f"Abandon step {step_index + 1}? The mission will remain recorded as abandoned."
        answer = QMessageBox.question(
            self, "Resolve interrupted action", prompt,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            store = CrashSafeMissionStore(self._mission_db)
            mission = store.resolve_needs_review(key[1], step_index, resolution)
            if resolution == "retry":
                saved_steps = json.loads(mission.get("steps_json", "[]"))
                if not isinstance(saved_steps, list) or not all(isinstance(item, str) for item in saved_steps):
                    raise ValueError("Persisted mission plan is invalid.")
                from core.execution_policy import ExecutionPolicy
                from mission_control.crash_cli import _engine
                from mission_control.crash_safe import CrashSafeMissionRunner
                list_tools = getattr(self._registry, "list_tools", None)
                registered_tools = frozenset(list_tools()) if callable(list_tools) else frozenset()
                result = CrashSafeMissionRunner(
                    store, _engine(Path.home(), tool_registry=self._registry),
                    ExecutionPolicy(allow_destructive_from_core=False, registered_tools=registered_tools),
                ).run(key[1], mission["objective"], saved_steps)
                state = (result.get("mission") or {}).get("state", "UNKNOWN")
                QMessageBox.information(self, "Retry finished", f"Mission state: {state}")
            else:
                QMessageBox.information(self, "Step abandoned", "The review decision was recorded. No action was executed.")
        except (OSError, sqlite3.Error, ValueError, TypeError) as exc:
            QMessageBox.critical(self, "Resolution failed", f"{type(exc).__name__}: {exc}")
        self.refresh()

    @staticmethod
    def _format_interval(seconds: int) -> str:
        if seconds % 86_400 == 0:
            return f"{seconds // 86_400}d"
        if seconds % 3_600 == 0:
            return f"{seconds // 3_600}h"
        if seconds % 60 == 0:
            return f"{seconds // 60}m"
        return f"{seconds}s"

    def _refresh_schedules(self) -> None:
        selected = self._schedule_list.currentItem()
        selected_id = selected.data(_USER_ROLE) if selected else None
        self._schedule_list.clear()
        service = self._autonomy_service
        if service is None:
            self._schedule_description.setEnabled(False)
            self._schedule_interval.setEnabled(False)
            self._schedule_create.setEnabled(False)
            self._schedule_toggle.setEnabled(False)
            self._schedule_delete.setEnabled(False)
            self._schedule_details.setPlainText("Durable autonomy service is not configured.")
            return
        try:
            for schedule in service.list_schedules():
                item = QListWidgetItem(
                    f"{'ENABLED' if schedule.enabled else 'PAUSED'} · every {self._format_interval(schedule.interval_seconds)} · {schedule.description}"
                )
                item.setData(_USER_ROLE, schedule.schedule_id)
                self._schedule_list.addItem(item)
                if schedule.schedule_id == selected_id:
                    self._schedule_list.setCurrentItem(item)
            self._schedule_description.setEnabled(True)
            self._schedule_interval.setEnabled(True)
            self._schedule_create.setEnabled(True)
        except (OSError, ValueError, RuntimeError) as exc:
            self._schedule_details.setPlainText(f"Could not load schedules: {type(exc).__name__}: {exc}")
        if self._schedule_list.currentItem() is None and self._schedule_list.count():
            self._schedule_list.setCurrentRow(0)
        self._schedule_selection_changed(self._schedule_list.currentItem(), None)

    def _schedule_selection_changed(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        schedule_id = current.data(_USER_ROLE) if current else None
        service = self._autonomy_service
        if not schedule_id or service is None:
            self._schedule_details.setPlainText("No schedule selected.")
            self._schedule_toggle.setEnabled(False)
            self._schedule_delete.setEnabled(False)
            return
        try:
            schedule = next((item for item in service.list_schedules() if item.schedule_id == schedule_id), None)
            runs = service.list_schedule_runs(schedule_id)
            if schedule is None:
                self._schedule_details.setPlainText("Schedule no longer exists.")
                return
            self._schedule_details.setPlainText(json.dumps({
                "schedule_id": schedule.schedule_id,
                "enabled": schedule.enabled,
                "description": schedule.description,
                "interval_seconds": schedule.interval_seconds,
                "next_run_at": schedule.next_run_at,
                "last_status": schedule.last_status,
                "runs": [
                    {"scheduled_for": run.scheduled_for, "goal_id": run.goal_id,
                     "status": run.status, "error": run.error}
                    for run in runs[:10]
                ],
            }, indent=2, ensure_ascii=False))
            self._schedule_toggle.setText("Pause schedule" if schedule.enabled else "Resume schedule")
            self._schedule_toggle.setEnabled(True)
            self._schedule_delete.setEnabled(True)
        except (OSError, ValueError, RuntimeError) as exc:
            self._schedule_details.setPlainText(f"Could not inspect schedule: {type(exc).__name__}: {exc}")
            self._schedule_toggle.setEnabled(False)
            self._schedule_delete.setEnabled(False)

    def _create_schedule(self) -> None:
        service = self._autonomy_service
        description = self._schedule_description.text().strip()
        if service is None or not description:
            QMessageBox.warning(self, "Scheduled goal", "Enter a goal and ensure the autonomy service is running.")
            return
        try:
            schedule = service.create_schedule(description, self._schedule_interval.value() * 60)
            self._schedule_description.clear()
            QMessageBox.information(
                self, "Schedule created",
                f"Recurring goal saved. First run is scheduled for {schedule.next_run_at}.",
            )
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.critical(self, "Schedule creation failed", f"{type(exc).__name__}: {exc}")
        self._refresh_schedules()

    def _toggle_schedule(self) -> None:
        current = self._schedule_list.currentItem()
        service = self._autonomy_service
        if current is None or service is None:
            return
        schedule_id = current.data(_USER_ROLE)
        try:
            schedule = next((item for item in service.list_schedules() if item.schedule_id == schedule_id), None)
            if schedule is None:
                raise ValueError("Schedule no longer exists.")
            service.set_schedule_enabled(schedule_id, not schedule.enabled)
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.critical(self, "Schedule update failed", f"{type(exc).__name__}: {exc}")
        self._refresh_schedules()

    def _delete_schedule(self) -> None:
        current = self._schedule_list.currentItem()
        service = self._autonomy_service
        if current is None or service is None:
            return
        schedule_id = current.data(_USER_ROLE)
        answer = QMessageBox.question(
            self, "Delete schedule",
            "Delete this recurring schedule and its run ledger? Existing goals already created by it are not deleted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            service.delete_schedule(schedule_id)
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.critical(self, "Schedule deletion failed", f"{type(exc).__name__}: {exc}")
        self._refresh_schedules()


    def _refresh_goals(self) -> None:
        selected = self._goal_list.currentItem()
        selected_id = selected.data(_USER_ROLE) if selected else None
        self._goal_list.clear()
        service = self._autonomy_service
        if service is None:
            self._goal_description.setEnabled(False)
            self._goal_create.setEnabled(False)
            self._goal_details.setPlainText("Durable autonomy service is not configured.")
            for button in (self._goal_start, self._goal_pause, self._goal_resume, self._goal_cancel):
                button.setEnabled(False)
            return
        try:
            goals = service.list_goals()
            for goal in goals[-200:]:
                completed = len(goal.metadata.get("execution_results", []))
                plan = service.get_plan(goal.id)
                total = len(plan.steps) if plan else 0
                label = f"{goal.state.value} · {completed}/{total} steps · {goal.description}"
                item = QListWidgetItem(label)
                item.setData(_USER_ROLE, goal.id.value)
                self._goal_list.addItem(item)
                if goal.id.value == selected_id:
                    self._goal_list.setCurrentItem(item)
            self._goal_description.setEnabled(True)
            self._goal_create.setEnabled(True)
        except (OSError, ValueError, RuntimeError, AttributeError) as exc:
            self._goal_details.setPlainText(f"Could not load goals: {type(exc).__name__}: {exc}")
        if self._goal_list.currentItem() is None and self._goal_list.count():
            self._goal_list.setCurrentRow(self._goal_list.count() - 1)
        self._goal_selection_changed(self._goal_list.currentItem(), None)

    def _goal_selection_changed(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        goal_id = current.data(_USER_ROLE) if current else None
        service = self._autonomy_service
        if not goal_id or service is None:
            self._goal_details.setPlainText("No autonomous goal selected.")
            for button in (self._goal_start, self._goal_pause, self._goal_resume, self._goal_cancel):
                button.setEnabled(False)
            return
        try:
            from core.models.primitives import Identifier
            goal = next((item for item in service.list_goals() if item.id.value == goal_id), None)
            if goal is None:
                self._goal_details.setPlainText("Goal no longer exists.")
                return
            plan = service.get_plan(Identifier(goal_id))
            steps = [
                {"step_id": step.id.value, "description": step.description, "state": step.state.value,
                 "tool": step.context.get("tool"), "action": step.context.get("action"),
                 "args": step.context.get("args", {})}
                for step in (plan.steps if plan else [])
            ]
            self._goal_details.setPlainText(json.dumps({
                "goal_id": goal.id.value, "description": goal.description, "state": goal.state.value,
                "priority": goal.priority.value, "progress": f"{len(goal.metadata.get('execution_results', []))}/{len(steps)}",
                "verification_status": goal.metadata.get("verification_status", "not_verified"),
                "execution_state_untrusted": bool(goal.metadata.get("execution_state_untrusted")),
                "in_flight_step_id": goal.metadata.get("in_flight_step_id"),
                "in_flight_batch": bool(goal.metadata.get("in_flight_batch")),
                "batch_partial_execution": bool(goal.metadata.get("batch_partial_execution")),
                "replan_attempts": goal.metadata.get("replan_attempts", 0),
                "intervention_required": goal.metadata.get("intervention_required"),
                "failure_reason": goal.metadata.get("failure_reason"),
                "recovery_evidence": goal.metadata.get("recovery_evidence", []),
                "results": goal.metadata.get("execution_results", [])[-8:],
                "plan": steps,
            }, indent=2, ensure_ascii=False, default=str))
            state = goal.state.value
            self._goal_start.setEnabled(state in {"CREATED", "QUEUED"})
            self._goal_pause.setEnabled(state == "RUNNING")
            self._goal_resume.setEnabled(state == "PAUSED")
            self._goal_cancel.setEnabled(state in {"CREATED", "QUEUED", "RUNNING", "PAUSED", "WAITING"})
        except (OSError, ValueError, RuntimeError, AttributeError) as exc:
            self._goal_details.setPlainText(f"Could not inspect goal: {type(exc).__name__}: {exc}")

    def _create_goal(self) -> None:
        service = self._autonomy_service
        description = self._goal_description.text().strip()
        if service is None or not description:
            QMessageBox.warning(self, "Autonomous goal", "Enter a goal and ensure the autonomy service is running.")
            return
        try:
            goal = service.create_goal(description)
            self._goal_description.clear()
            service.start_goal(goal.id)
            QMessageBox.information(self, "Goal started", f"Goal {goal.id.value} was saved and queued for execution.")
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.critical(self, "Goal creation failed", f"{type(exc).__name__}: {exc}")
        self._refresh_goals()

    def _goal_action(self, action: str) -> None:
        current = self._goal_list.currentItem()
        service = self._autonomy_service
        if current is None or service is None:
            return
        from core.models.primitives import Identifier
        goal_id = Identifier(str(current.data(_USER_ROLE)))
        try:
            if action == "start":
                service.start_goal(goal_id)
            elif action == "pause":
                service.pause_goal(goal_id)
            elif action == "resume":
                service.resume_goal(goal_id)
            elif action == "cancel":
                answer = QMessageBox.question(
                    self, "Cancel goal", "Cancel this goal? In-flight side effects may still need reconciliation.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return
                service.cancel_goal(goal_id)
            else:
                raise ValueError(f"Unknown goal action {action}.")
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.critical(self, "Goal action failed", f"{type(exc).__name__}: {exc}")
        self._refresh_goals()
