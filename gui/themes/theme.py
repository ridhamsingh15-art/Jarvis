"""
Theme engine — dataclass, manager, and stylesheet builder.

Every color in the application is a semantic token in Theme.
ThemeManager holds the active theme and rebuilds the stylesheet
when the theme changes. No widget ever hardcodes a color.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal
from typing_extensions import Self


@dataclass(frozen=True)
class Theme:
    """Immutable semantic color token set.

    Every visual property is driven by these tokens.
    To create a new theme, instantiate Theme with different values.
    """

    name: str

    # Backgrounds
    background: str
    surface: str
    surface_alt: str
    sidebar: str

    # Borders
    border: str
    border_light: str

    # Text
    text: str
    text_secondary: str
    text_muted: str

    # Accent
    accent: str
    accent_hover: str
    accent_muted: str

    # Bubbles
    user_bubble: str
    bot_bubble: str
    error_bubble: str
    system_bubble: str

    # Status
    success: str
    warning: str
    error: str

    # Input
    input_bg: str
    input_border: str

    # Cards
    card_bg: str
    card_border: str

    # Misc
    scrollbar_bg: str
    scrollbar_handle: str
    hover_overlay: str
    shadow: str


class ThemeManager(QObject):
    """Singleton that owns the active theme.

    Signals
    -------
    theme_changed(Theme)
        Emitted after the active theme has been swapped.
    """

    theme_changed = Signal(object)

    _instance: ThemeManager | None = None
    _initialized: bool = False

    def __new__(cls) -> Self:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        from typing import cast
        return cast(Self, cls._instance)

    def __init__(self) -> None:
        if self._initialized:
            return
        super().__init__()
        self._initialized = True
        self._theme: Theme | None = None

    @property
    def theme(self) -> Theme:
        """Return the active theme, falling back to dark."""
        if self._theme is None:
            from gui.themes.dark import DARK_THEME
            self._theme = DARK_THEME
        return self._theme

    def set_theme(self, theme: Theme) -> None:
        """Switch the active theme and notify listeners.

        Args:
            theme: New Theme instance to activate.
        """
        self._theme = theme
        self.theme_changed.emit(theme)

    def stylesheet(self) -> str:
        """Build QSS from the active theme."""
        return build_stylesheet(self.theme)


# ── Font constants ───────────────────────────────────────────

FONT_FAMILY = "'Segoe UI', 'Inter', 'Roboto', system-ui, sans-serif"
FONT_SIZE_XS = "11px"
FONT_SIZE_SM = "12px"
FONT_SIZE_BASE = "14px"
FONT_SIZE_LG = "16px"
FONT_SIZE_XL = "20px"
FONT_SIZE_XXL = "24px"
BORDER_RADIUS_SM = "6px"
BORDER_RADIUS = "8px"
BORDER_RADIUS_LG = "12px"
BORDER_RADIUS_XL = "16px"


def build_stylesheet(t: Theme) -> str:
    """Generate the complete application QSS from theme tokens.

    Args:
        t: Theme instance with all color tokens.

    Returns:
        Full QSS stylesheet string.
    """
    return f"""
/* ── Global ──────────────────────────────────────────── */
QMainWindow, QWidget {{
    background-color: {t.background};
    color: {t.text};
    font-family: {FONT_FAMILY};
    font-size: {FONT_SIZE_BASE};
}}
QWidget#centralContainer {{
    background-color: {t.background};
}}

/* ── Scroll Areas ────────────────────────────────────── */
QScrollArea {{
    background-color: transparent;
    border: none;
}}
QScrollArea > QWidget > QWidget {{
    background-color: transparent;
}}
QScrollBar:vertical {{
    background: {t.scrollbar_bg};
    width: 6px;
    margin: 0;
    border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {t.scrollbar_handle};
    min-height: 30px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical:hover {{
    background: {t.text_muted};
}}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    height: 0;
}}

/* ── Sidebar ─────────────────────────────────────────── */
QFrame#sidebarFrame {{
    background-color: {t.sidebar};
    border-right: 1px solid {t.border};
}}
QPushButton.sidebarBtn {{
    background-color: transparent;
    color: {t.text_secondary};
    border: none;
    border-radius: {BORDER_RADIUS};
    padding: 10px 16px;
    text-align: left;
    font-size: {FONT_SIZE_BASE};
}}
QPushButton.sidebarBtn:hover {{
    background-color: {t.hover_overlay};
    color: {t.text};
}}
QPushButton.sidebarBtn[active="true"] {{
    background-color: {t.accent_muted};
    color: {t.accent};
    font-weight: 600;
}}
QLabel#sidebarBrand {{
    color: {t.text};
    font-size: {FONT_SIZE_LG};
    font-weight: 700;
    padding: 0;
    background: transparent;
}}
QLabel#sidebarVersion {{
    color: {t.text_muted};
    font-size: {FONT_SIZE_XS};
    background: transparent;
}}

/* ── Header ──────────────────────────────────────────── */
QFrame#headerFrame {{
    background-color: {t.surface};
    border-bottom: 1px solid {t.border};
}}
QLabel#headerTitle {{
    color: {t.text};
    font-size: {FONT_SIZE_LG};
    font-weight: 700;
    background: transparent;
}}
QLabel.headerMeta {{
    color: {t.text_muted};
    font-size: {FONT_SIZE_SM};
    background: transparent;
}}
QLabel#headerDot {{
    background: transparent;
}}
QPushButton#headerSettingsBtn {{
    background: transparent;
    border: none;
    color: {t.text_muted};
    font-size: {FONT_SIZE_LG};
    padding: 6px;
    border-radius: {BORDER_RADIUS};
}}
QPushButton#headerSettingsBtn:hover {{
    background-color: {t.hover_overlay};
    color: {t.text};
}}

/* ── Footer ──────────────────────────────────────────── */
QFrame#footerFrame {{
    background-color: {t.surface};
    border-top: 1px solid {t.border};
}}
QLabel.footerText {{
    color: {t.text_muted};
    font-size: {FONT_SIZE_XS};
    background: transparent;
}}
QLabel#footerDot {{
    background: transparent;
}}

/* ── Chat Bubbles ────────────────────────────────────── */
QFrame#userBubble {{
    background-color: {t.user_bubble};
    border-radius: {BORDER_RADIUS_LG};
    border: none;
}}
QFrame#botBubble {{
    background-color: {t.bot_bubble};
    border: 1px solid {t.border_light};
    border-radius: {BORDER_RADIUS_LG};
}}
QFrame#errorBubble {{
    background-color: {t.error_bubble};
    border: 1px solid {t.error};
    border-radius: {BORDER_RADIUS_LG};
}}
QFrame#systemBubble {{
    background-color: {t.system_bubble};
    border: 1px solid {t.border_light};
    border-radius: {BORDER_RADIUS_LG};
}}
QLabel.bubbleText {{
    color: {t.text};
    font-size: {FONT_SIZE_BASE};
    background: transparent;
    border: none;
    padding: 0;
}}
QLabel.bubbleRole {{
    color: {t.text_muted};
    font-size: {FONT_SIZE_SM};
    font-weight: 600;
    background: transparent;
    border: none;
}}
QLabel.bubbleTime {{
    color: {t.text_muted};
    font-size: {FONT_SIZE_XS};
    background: transparent;
    border: none;
}}

/* ── Code Blocks ─────────────────────────────────────── */
QFrame#codeBlock {{
    background-color: {t.surface_alt};
    border: 1px solid {t.border};
    border-radius: {BORDER_RADIUS};
}}
QTextEdit#codeContent {{
    background-color: transparent;
    color: {t.text};
    border: none;
    font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
    font-size: {FONT_SIZE_SM};
    selection-background-color: {t.accent_muted};
}}
QPushButton#copyBtn {{
    background-color: transparent;
    color: {t.text_muted};
    border: 1px solid {t.border};
    border-radius: {BORDER_RADIUS_SM};
    padding: 3px 10px;
    font-size: {FONT_SIZE_XS};
}}
QPushButton#copyBtn:hover {{
    background-color: {t.hover_overlay};
    color: {t.text};
}}

/* ── Task Cards ──────────────────────────────────────── */
QFrame#taskCard {{
    background-color: {t.card_bg};
    border: 1px solid {t.card_border};
    border-radius: {BORDER_RADIUS_LG};
}}
QLabel.taskTitle {{
    color: {t.text};
    font-size: {FONT_SIZE_BASE};
    font-weight: 600;
    background: transparent;
}}
QLabel.taskDetail {{
    color: {t.text_secondary};
    font-size: {FONT_SIZE_SM};
    background: transparent;
}}
QLabel.taskBadge {{
    font-size: {FONT_SIZE_XS};
    font-weight: 600;
    border-radius: {BORDER_RADIUS_SM};
    padding: 2px 8px;
    background: transparent;
}}

/* ── Input Area ──────────────────────────────────────── */
QFrame#inputFrame {{
    background-color: {t.surface};
    border-top: 1px solid {t.border};
}}
QTextEdit#messageInput {{
    background-color: {t.input_bg};
    color: {t.text};
    border: 1px solid {t.input_border};
    border-radius: {BORDER_RADIUS_LG};
    padding: 10px 14px;
    font-size: {FONT_SIZE_BASE};
    font-family: {FONT_FAMILY};
    selection-background-color: {t.accent};
}}
QTextEdit#messageInput:focus {{
    border-color: {t.accent};
}}
QPushButton#sendButton {{
    background-color: {t.accent};
    color: #ffffff;
    border: none;
    border-radius: {BORDER_RADIUS};
    padding: 8px 20px;
    font-weight: 600;
    font-size: {FONT_SIZE_BASE};
    min-width: 60px;
}}
QPushButton#sendButton:hover {{
    background-color: {t.accent_hover};
}}
QPushButton#sendButton:disabled {{
    background-color: {t.border};
    color: {t.text_muted};
}}

/* ── Thinking Indicator ──────────────────────────────── */
QFrame#thinkingBubble {{
    background-color: {t.bot_bubble};
    border: 1px solid {t.border_light};
    border-radius: {BORDER_RADIUS_LG};
}}
QLabel#thinkingText {{
    color: {t.text_muted};
    font-size: {FONT_SIZE_BASE};
    background: transparent;
    font-style: italic;
}}
QLabel#thinkingDots {{
    color: {t.accent};
    font-size: {FONT_SIZE_LG};
    background: transparent;
}}

/* ── View Pages ──────────────────────────────────────── */
QLabel.viewTitle {{
    color: {t.text};
    font-size: {FONT_SIZE_XL};
    font-weight: 700;
    background: transparent;
}}
QLabel.viewSubtitle {{
    color: {t.text_muted};
    font-size: {FONT_SIZE_SM};
    background: transparent;
}}
QLabel.sectionHeader {{
    color: {t.text_secondary};
    font-size: {FONT_SIZE_SM};
    font-weight: 600;
    background: transparent;
    padding: 8px 0 4px 0;
}}

/* ── Settings Controls ───────────────────────────────── */
QComboBox {{
    background-color: {t.input_bg};
    color: {t.text};
    border: 1px solid {t.input_border};
    border-radius: {BORDER_RADIUS};
    padding: 8px 12px;
    font-size: {FONT_SIZE_BASE};
    min-width: 180px;
}}
QComboBox:hover {{
    border-color: {t.accent};
}}
QComboBox::drop-down {{
    border: none;
    padding-right: 8px;
}}
QComboBox QAbstractItemView {{
    background-color: {t.surface};
    color: {t.text};
    border: 1px solid {t.border};
    border-radius: {BORDER_RADIUS};
    selection-background-color: {t.accent_muted};
    selection-color: {t.text};
    padding: 4px;
}}
QFrame.settingsRow {{
    background-color: {t.surface};
    border: 1px solid {t.border};
    border-radius: {BORDER_RADIUS};
}}
QLabel.settingsLabel {{
    color: {t.text};
    font-size: {FONT_SIZE_BASE};
    background: transparent;
}}
QLabel.settingsValue {{
    color: {t.text_muted};
    font-size: {FONT_SIZE_BASE};
    background: transparent;
}}
QLabel.settingsDisabled {{
    color: {t.text_muted};
    font-size: {FONT_SIZE_SM};
    font-style: italic;
    background: transparent;
}}

/* ── Search Input ────────────────────────────────────── */
QLineEdit#searchInput {{
    background-color: {t.input_bg};
    color: {t.text};
    border: 1px solid {t.input_border};
    border-radius: {BORDER_RADIUS};
    padding: 8px 12px;
    font-size: {FONT_SIZE_BASE};
}}
QLineEdit#searchInput:focus {{
    border-color: {t.accent};
}}

/* ── Memory / History Items ──────────────────────────── */
QFrame.listItem {{
    background-color: {t.surface};
    border: 1px solid {t.border};
    border-radius: {BORDER_RADIUS};
}}
QFrame.listItem:hover {{
    border-color: {t.accent_muted};
}}

/* ── Log Viewer ──────────────────────────────────────── */
QTextEdit#logViewer {{
    background-color: {t.surface_alt};
    color: {t.text};
    border: 1px solid {t.border};
    border-radius: {BORDER_RADIUS};
    font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
    font-size: {FONT_SIZE_SM};
    padding: 8px;
    selection-background-color: {t.accent_muted};
}}

/* ── Plugin Cards ────────────────────────────────────── */
QFrame.pluginCard {{
    background-color: {t.card_bg};
    border: 1px solid {t.card_border};
    border-radius: {BORDER_RADIUS_LG};
}}

/* ── Splash Screen ───────────────────────────────────── */
QFrame#splashFrame {{
    background-color: {t.background};
    border: 1px solid {t.border};
    border-radius: {BORDER_RADIUS_XL};
}}
QLabel#splashTitle {{
    color: {t.text};
    font-size: 36px;
    font-weight: 800;
    background: transparent;
    letter-spacing: 6px;
}}
QLabel#splashVersion {{
    color: {t.text_muted};
    font-size: {FONT_SIZE_SM};
    background: transparent;
}}
QLabel#splashStatus {{
    color: {t.accent};
    font-size: {FONT_SIZE_SM};
    background: transparent;
}}
QProgressBar#splashProgress {{
    background-color: {t.surface};
    border: none;
    border-radius: 3px;
    max-height: 4px;
}}
QProgressBar#splashProgress::chunk {{
    background-color: {t.accent};
    border-radius: 3px;
}}
"""
