from __future__ import annotations

from gui.main_window import _PAGE_INDEX
from gui.sidebar import _NAV_ITEMS


def test_dashboard_restores_overview_without_renumbering_legacy_pages() -> None:
    assert {key: _PAGE_INDEX[key] for key in ("chat", "memory", "history", "logs", "plugins", "settings", "dashboard")} == {
        "chat": 0,
        "memory": 1,
        "history": 2,
        "logs": 3,
        "plugins": 4,
        "settings": 5,
        "dashboard": 6,
    }
    if "missions" in _PAGE_INDEX:
        assert _PAGE_INDEX["missions"] > _PAGE_INDEX["dashboard"]
    assert _NAV_ITEMS[0][0] == "dashboard"
    assert _NAV_ITEMS[0][2] == "Overview"


def test_dashboard_restores_cyan_control_center_styles() -> None:
    from gui.themes.dark import DARK_THEME
    from gui.themes.theme import build_stylesheet

    assert DARK_THEME.accent.lower() == "#00d9ff"
    stylesheet = build_stylesheet(DARK_THEME)
    assert "QFrame#dashboardHero" in stylesheet
    assert "QFrame#dashboardTelemetry" in stylesheet
