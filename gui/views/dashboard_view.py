"""Overview dashboard for the JARVIS desktop control center."""

from __future__ import annotations

import ctypes
import math
import sys

from PySide6.QtCore import Qt, Signal, QTimer, QRectF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class CoreOrbWidget(QWidget):
    """Lightweight animated HUD core whose color follows actual chat state."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._phase = 0.0
        self._state = "idle"
        self.setObjectName("dashboardCoreOrb")
        self.setMinimumSize(92, 92)
        self.setMaximumSize(112, 112)
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._advance)
        self._timer.start()

    def set_state(self, state: str) -> None:
        clean = str(state or "idle").strip().lower()
        self._state = clean if clean in {"thinking", "error"} else "idle"
        self.update()

    def _advance(self) -> None:
        self._phase = (self._phase + (0.10 if self._state == "thinking" else 0.035)) % (2 * math.pi)
        if self.isVisible():
            self.update()

    def paintEvent(self, _event) -> None:
        side = min(self.width(), self.height())
        if side <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate((self.width() - side) / 2, (self.height() - side) / 2)
        center = side / 2
        cyan = QColor("#00D9FF")
        amber = QColor("#FFC857") if self._state == "thinking" else cyan
        if self._state == "error":
            amber = QColor("#FF667A")
        pulse = 0.78 + 0.12 * (math.sin(self._phase) + 1.0)
        painter.setPen(QPen(QColor(0, 217, 255, 24), 1))
        painter.setBrush(QColor(0, 217, 255, 8))
        painter.drawEllipse(QRectF(center * 0.12, center * 0.12, side * 0.76, side * 0.76))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(cyan.red(), cyan.green(), cyan.blue(), 90), 1))
        painter.drawEllipse(QRectF(center * 0.27, center * 0.27, side * 0.46, side * 0.46))
        painter.save()
        painter.translate(center, center)
        painter.rotate(math.degrees(self._phase))
        pen = QPen(amber, 2)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawArc(QRectF(-side * 0.34, -side * 0.34, side * 0.68, side * 0.68), 15 * 16, 235 * 16)
        painter.restore()
        painter.setPen(QPen(QColor(0, 217, 255, 170), 1))
        painter.drawEllipse(QRectF(center * 0.62, center * 0.62, side * 0.38, side * 0.38))
        glow = QColor(amber)
        glow.setAlpha(50)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        radius = side * 0.12 * pulse
        painter.drawEllipse(QRectF(center - radius, center - radius, radius * 2, radius * 2))
        painter.setBrush(amber)
        radius = side * 0.045
        painter.drawEllipse(QRectF(center - radius, center - radius, radius * 2, radius * 2))
        painter.end()


class _WindowsSystemMetrics:
    """Read actual CPU and RAM usage via Windows APIs without adding dependencies."""

    class _FileTime(ctypes.Structure):
        _fields_ = [("low", ctypes.c_ulong), ("high", ctypes.c_ulong)]

    class _MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("length", ctypes.c_ulong), ("memory_load", ctypes.c_ulong),
            ("total_phys", ctypes.c_ulonglong), ("avail_phys", ctypes.c_ulonglong),
            ("total_page_file", ctypes.c_ulonglong), ("avail_page_file", ctypes.c_ulonglong),
            ("total_virtual", ctypes.c_ulonglong), ("avail_virtual", ctypes.c_ulonglong),
            ("avail_extended_virtual", ctypes.c_ulonglong),
        ]

    def __init__(self) -> None:
        self._previous_cpu: tuple[int, int, int] | None = None

    @staticmethod
    def _ticks(value: "_WindowsSystemMetrics._FileTime") -> int:
        return (value.high << 32) | value.low

    def read(self) -> tuple[float | None, float | None]:
        if sys.platform != "win32":
            return None, None
        try:
            idle, kernel, user = self._FileTime(), self._FileTime(), self._FileTime()
            memory = self._MemoryStatus()
            memory.length = ctypes.sizeof(memory)
            if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
                cpu = None
            else:
                current = (self._ticks(idle), self._ticks(kernel), self._ticks(user))
                cpu = None
                if self._previous_cpu is not None:
                    di = current[0] - self._previous_cpu[0]
                    dk = current[1] - self._previous_cpu[1]
                    du = current[2] - self._previous_cpu[2]
                    total = dk + du
                    if total > 0:
                        cpu = max(0.0, min(100.0, 100.0 * (total - di) / total))
                self._previous_cpu = current
            ram = None
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
                ram = float(memory.memory_load)
            return cpu, ram
        except (AttributeError, OSError, TypeError, ValueError):
            return None, None


class DashboardView(QWidget):
    """High-level view of the current JARVIS runtime and navigation shortcuts."""

    navigate_requested = Signal(str)
    federation_requested = Signal()
    _model_state_updated = Signal(object)

    def __init__(
        self,
        model_name: str = "",
        memory_backend: str = "SQLite",
        tool_count: int = 0,
        mode: str = "assistant",
        workspace: str = "",
        model_state=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._initial_model_name = model_name or "Not configured"
        self._memory_backend = memory_backend or "Unknown"
        self._tool_count = tool_count
        self._mode = mode or "assistant"
        self._workspace = workspace or "Not configured"
        self._model_state = model_state
        self._snapshot: dict = {}
        self._model_state_updated.connect(self._apply_model_state)
        self._state_listener = self._on_state_changed
        self._metrics_reader = _WindowsSystemMetrics()
        self._build_ui()
        self._metrics_timer = QTimer(self)
        self._metrics_timer.setInterval(1500)
        self._metrics_timer.timeout.connect(self.refresh_system_metrics)
        self._metrics_timer.start()
        self.refresh_system_metrics()
        self.refresh_snapshot()

        if self._model_state is not None and hasattr(self._model_state, "add_listener"):
            self._model_state.add_listener(self._state_listener)
            self.destroyed.connect(self._remove_state_listener)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setObjectName("dashboardScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        root.addWidget(scroll)

        content = QWidget()
        content.setObjectName("dashboardContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 28, 32, 32)
        layout.setSpacing(18)

        top = QHBoxLayout()
        top.setSpacing(12)
        titles = QVBoxLayout()
        titles.setSpacing(4)

        eyebrow = QLabel("JARVIS  /  CONTROL CENTER")
        eyebrow.setObjectName("dashboardEyebrow")
        titles.addWidget(eyebrow)

        title = QLabel("Control, at a glance.")
        title.setObjectName("dashboardTitle")
        titles.addWidget(title)

        subtitle = QLabel("Your local workspace, runtime, and tools in one place.")
        subtitle.setObjectName("dashboardSubtitle")
        titles.addWidget(subtitle)
        top.addLayout(titles, stretch=1)

        refresh = QPushButton("↻  Refresh snapshot")
        refresh.setObjectName("dashboardRefreshBtn")
        refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh.clicked.connect(self.refresh_snapshot)
        top.addWidget(refresh, alignment=Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(top)

        hero = QFrame()
        hero.setObjectName("dashboardHero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(24, 22, 24, 22)
        hero_layout.setSpacing(20)

        hero_copy = QVBoxLayout()
        hero_copy.setSpacing(8)
        hero_kicker = QLabel("PERSONAL AI WORKSPACE")
        hero_kicker.setObjectName("dashboardHeroKicker")
        hero_copy.addWidget(hero_kicker)

        hero_title = QLabel("Your AI. Your machine. Your rules.")
        hero_title.setObjectName("dashboardHeroTitle")
        hero_title.setWordWrap(True)
        hero_copy.addWidget(hero_title)

        hero_desc = QLabel(
            "A clear view of the current runtime, with shortcuts to the places "
            "you use to work with JARVIS."
        )
        hero_desc.setObjectName("dashboardHeroDescription")
        hero_desc.setWordWrap(True)
        hero_copy.addWidget(hero_desc)
        hero_layout.addLayout(hero_copy, stretch=1)

        self._core_orb = CoreOrbWidget()
        hero_layout.addWidget(self._core_orb, alignment=Qt.AlignmentFlag.AlignCenter)

        pill = QLabel("●  DESKTOP CLIENT")
        pill.setObjectName("dashboardHeroPill")
        pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pill.setMinimumWidth(142)
        pill.setMaximumHeight(34)
        hero_layout.addWidget(pill, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addWidget(hero)

        metrics = QGridLayout()
        metrics.setContentsMargins(0, 0, 0, 0)
        metrics.setHorizontalSpacing(12)
        metrics.setVerticalSpacing(12)
        self._model_value = self._metric_card(metrics, 0, 0, "ACTIVE AI MODEL", "—")
        self._mode_value = self._metric_card(metrics, 0, 1, "OPERATING MODE", "—")
        self._tools_value = self._metric_card(metrics, 1, 0, "REGISTERED TOOLS", "—")
        self._memory_value = self._metric_card(metrics, 1, 1, "MEMORY BACKEND", "—")
        layout.addLayout(metrics)

        telemetry = QFrame()
        telemetry.setObjectName("dashboardTelemetry")
        telemetry_layout = QVBoxLayout(telemetry)
        telemetry_layout.setContentsMargins(18, 14, 18, 16)
        telemetry_layout.setSpacing(10)
        telemetry_heading = QLabel("LIVE SYSTEM TELEMETRY")
        telemetry_heading.setObjectName("dashboardSectionLabel")
        telemetry_layout.addWidget(telemetry_heading)

        self._cpu_value = QLabel("CPU  ·  Measuring…")
        self._cpu_value.setObjectName("dashboardTelemetryValue")
        telemetry_layout.addWidget(self._cpu_value)
        self._cpu_bar = QProgressBar()
        self._cpu_bar.setObjectName("dashboardCpuBar")
        self._cpu_bar.setRange(0, 100)
        self._cpu_bar.setValue(0)
        self._cpu_bar.setTextVisible(False)
        self._cpu_bar.setFixedHeight(5)
        telemetry_layout.addWidget(self._cpu_bar)

        self._ram_value = QLabel("RAM  ·  Measuring…")
        self._ram_value.setObjectName("dashboardTelemetryValue")
        telemetry_layout.addWidget(self._ram_value)
        self._ram_bar = QProgressBar()
        self._ram_bar.setObjectName("dashboardRamBar")
        self._ram_bar.setRange(0, 100)
        self._ram_bar.setValue(0)
        self._ram_bar.setTextVisible(False)
        self._ram_bar.setFixedHeight(5)
        telemetry_layout.addWidget(self._ram_bar)
        layout.addWidget(telemetry)

        workspace = QFrame()
        workspace.setObjectName("dashboardWorkspace")
        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(18, 16, 18, 16)
        workspace_layout.setSpacing(7)

        workspace_heading = QLabel("CURRENT WORKSPACE")
        workspace_heading.setObjectName("dashboardSectionLabel")
        workspace_layout.addWidget(workspace_heading)

        self._workspace_value = QLabel("—")
        self._workspace_value.setObjectName("dashboardWorkspacePath")
        self._workspace_value.setWordWrap(True)
        workspace_layout.addWidget(self._workspace_value)
        layout.addWidget(workspace)

        section = QLabel("QUICK ACCESS")
        section.setObjectName("dashboardSectionLabel")
        layout.addWidget(section)

        actions = QGridLayout()
        actions.setHorizontalSpacing(10)
        actions.setVerticalSpacing(10)
        self._add_action(actions, 0, 0, "Open Chat", "Continue a conversation", "chat")
        self._add_action(actions, 0, 1, "Manage Plugins", "Review registered tools", "plugins")
        self._add_action(actions, 1, 0, "View Logs", "Inspect recent runtime activity", "logs")
        self._add_action(actions, 1, 1, "Settings", "Review the current configuration", "settings")
        self._add_action(actions, 2, 0, "Device Federation", "Pair and manage trusted devices", "federation")
        layout.addLayout(actions)

        self._status = QLabel("Runtime values are read from the current application context.")
        self._status.setObjectName("dashboardStatusText")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)
        layout.addStretch(1)
        scroll.setWidget(content)

    def _metric_card(self, grid: QGridLayout, row: int, column: int, label: str, value: str) -> QLabel:
        card = QFrame()
        card.setProperty("class", "dashboardMetricCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 18)
        card_layout.setSpacing(9)

        heading = QLabel(label)
        heading.setObjectName("dashboardMetricLabel")
        card_layout.addWidget(heading)

        value_label = QLabel(value)
        value_label.setObjectName("dashboardMetricValue")
        value_label.setWordWrap(True)
        card_layout.addWidget(value_label)
        grid.addWidget(card, row, column)
        return value_label

    def _add_action(
        self, grid: QGridLayout, row: int, column: int,
        title: str, description: str, page_key: str,
    ) -> None:
        button = QPushButton()
        button.setObjectName(f"dashboardOpen{page_key.title()}Btn")
        button.setProperty("class", "dashboardActionBtn")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setMinimumHeight(76)
        button.setText(f"{title}   ›\n{description}")
        if page_key == "federation":
            button.clicked.connect(self.federation_requested.emit)
        else:
            button.clicked.connect(lambda checked=False, key=page_key: self.navigate_requested.emit(key))
        grid.addWidget(button, row, column)

    def refresh_system_metrics(self) -> None:
        """Refresh CPU/RAM from native Windows counters; never synthesize values."""
        cpu, ram = self._metrics_reader.read()
        if cpu is None:
            self._cpu_value.setText("CPU  ·  Unavailable")
            self._cpu_bar.setValue(0)
        else:
            self._cpu_value.setText(f"CPU  ·  {cpu:.0f}%")
            self._cpu_bar.setValue(round(cpu))
        if ram is None:
            self._ram_value.setText("RAM  ·  Unavailable")
            self._ram_bar.setValue(0)
        else:
            self._ram_value.setText(f"RAM  ·  {ram:.0f}% used")
            self._ram_bar.setValue(round(ram))

    def set_runtime_status(self, status: str) -> None:
        """Reflect ChatView's actual processing status in the animated core."""
        clean = str(status or "idle").strip().lower()
        self._core_orb.set_state(clean)
        if clean == "thinking":
            self._status.setText("JARVIS is processing a request.")
        elif clean == "error":
            self._status.setText("The latest request reported an error. Check Logs for details.")
        else:
            self._status.setText("JARVIS is ready. Runtime details are read from the active application context.")

    def refresh_snapshot(self) -> None:
        """Update dashboard values from the latest available model state."""
        state = {}
        if self._model_state is not None and hasattr(self._model_state, "to_dict"):
            try:
                state = self._model_state.to_dict()
            except Exception:
                state = {}
        self._apply_model_state(state)

    def _on_state_changed(self, state) -> None:
        try:
            snapshot = state.to_dict() if hasattr(state, "to_dict") else {}
            self._model_state_updated.emit(snapshot)
        except Exception:
            return

    def _apply_model_state(self, snapshot) -> None:
        self._snapshot = dict(snapshot) if isinstance(snapshot, dict) else {}
        active_model = self._snapshot.get("active_model") or self._initial_model_name
        provider = self._snapshot.get("active_provider")
        if provider and active_model != "Not configured":
            model_text = f"{active_model}  ·  {provider}"
        else:
            model_text = str(active_model)
        mode = self._snapshot.get("operating_mode") or self._mode
        selection = self._snapshot.get("selection_mode")
        mode_text = str(mode).replace("_", " ").title()
        if selection:
            mode_text = f"{mode_text}  ·  {str(selection).title()} selection"

        self._model_value.setText(model_text)
        self._mode_value.setText(mode_text)
        self._tools_value.setText(str(self._tool_count))
        self._memory_value.setText(self._memory_backend)
        self._workspace_value.setText(self._workspace)
        if self._snapshot.get("fallback_used"):
            self._status.setText(
                "The latest recorded request used a fallback provider. "
                "Check the Logs page for runtime details."
            )
        else:
            self._status.setText(
                "Snapshot refreshed from the current application context. "
                "Detailed activity is available in Logs."
            )

    def _remove_state_listener(self, *_args) -> None:
        if self._model_state is not None and hasattr(self._model_state, "remove_listener"):
            try:
                self._model_state.remove_listener(self._state_listener)
            except Exception:
                pass
