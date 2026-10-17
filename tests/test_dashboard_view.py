from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from gui.views.dashboard_view import DashboardView


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


class _FakeModelState:
    def __init__(self, snapshot: dict) -> None:
        self.snapshot = snapshot
        self.listeners = []

    def to_dict(self) -> dict:
        return dict(self.snapshot)

    def add_listener(self, callback) -> None:
        self.listeners.append(callback)

    def remove_listener(self, callback) -> None:
        self.listeners.remove(callback)

    def update(self, **values) -> None:
        self.snapshot.update(values)
        for callback in list(self.listeners):
            callback(self)


def test_dashboard_shows_runtime_values_and_workspace() -> None:
    _app()
    view = DashboardView(model_name="qwen3:8b", memory_backend="SQLite", tool_count=14, workspace=r"C:\Jarvis")
    values = [label.text() for label in view.findChildren(QLabel, "dashboardMetricValue")]
    assert any("qwen3:8b" in value for value in values)
    assert "14" in values
    assert "SQLite" in values
    assert view.findChild(QLabel, "dashboardWorkspacePath").text() == r"C:\Jarvis"
    view.close()


def test_dashboard_quick_access_emits_navigation_key() -> None:
    _app()
    view = DashboardView()
    requested: list[str] = []
    view.navigate_requested.connect(requested.append)
    button = view.findChild(QPushButton, "dashboardOpenChatBtn")
    assert button is not None
    button.click()
    assert requested == ["chat"]
    view.close()


def test_dashboard_refreshes_when_model_state_changes() -> None:
    _app()
    state = _FakeModelState({
        "active_provider": "ollama",
        "active_model": "qwen3:8b",
        "operating_mode": "local",
    })
    view = DashboardView(model_state=state)
    assert "qwen3:8b" in view.findChildren(QLabel, "dashboardMetricValue")[0].text()
    state.update(active_model="qwen2.5-coder:7b")
    assert "qwen2.5-coder:7b" in view.findChildren(QLabel, "dashboardMetricValue")[0].text()
    view.close()


def test_dashboard_hud_tracks_real_chat_status() -> None:
    _app()
    view = DashboardView()
    view.set_runtime_status("thinking")
    assert view._core_orb._state == "thinking"
    assert "processing" in view.findChild(QLabel, "dashboardStatusText").text().lower()
    view.set_runtime_status("error")
    assert view._core_orb._state == "error"
    assert "error" in view.findChild(QLabel, "dashboardStatusText").text().lower()
    view.close()


def test_dashboard_system_telemetry_never_uses_placeholder_percentages() -> None:
    _app()
    view = DashboardView()
    view.refresh_system_metrics()
    values = [label.text() for label in view.findChildren(QLabel, "dashboardTelemetryValue")]
    assert any(value.startswith("CPU") for value in values)
    assert any(value.startswith("RAM") for value in values)
    assert all("Measuring" not in value for value in values)
    view.close()
