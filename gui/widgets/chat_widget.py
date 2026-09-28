"""
ChatWidget — scrollable message history with rich chat bubbles.

Displays role-based bubbles (user, assistant, error, system)
with support for rich text, code blocks with copy buttons,
timestamps, and fade-in animations. Purely a display component.

Slots
-----
append_message(role, text)
    Add a new bubble to the chat history.
clear_messages()
    Remove all messages from the history.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    Qt,
    QTimer,
    Slot,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# ── Role → display config ───────────────────────────────────

_ROLE_CONFIG: dict[str, tuple[str, str]] = {
    "user":      ("You",    "userBubble"),
    "assistant": ("Jarvis", "botBubble"),
    "error":     ("Error",  "errorBubble"),
    "system":    ("System", "systemBubble"),
}

_TOOL_ICONS: dict[str, str] = {
    "browser":  "🌐",
    "windows":  "🪟",
    "file":     "📂",
    "system":   "⚙",
}

# Simple pattern to detect code blocks in backtick fences
_CODE_BLOCK_RE = re.compile(
    r"```(\w*)\n(.*?)```", re.DOTALL
)


class ChatWidget(QWidget):
    """Scrollable chat history with rich message bubbles."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    # ── UI construction ──────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        self._history = QWidget()
        self._history_layout = QVBoxLayout(self._history)
        self._history_layout.setContentsMargins(16, 16, 16, 16)
        self._history_layout.setSpacing(8)
        self._history_layout.addStretch()

        self._scroll.setWidget(self._history)
        root.addWidget(self._scroll)

    # ── Bubble construction ──────────────────────────────────

    def _make_bubble(self, role: str, text: str) -> QFrame:
        """Create a styled chat bubble.

        Args:
            role: One of 'user', 'assistant', 'error', 'system'.
            text: Message content (may contain code fences).

        Returns:
            Styled QFrame widget.
        """
        label, obj_name = _ROLE_CONFIG.get(
            role, ("Jarvis", "botBubble")
        )

        bubble = QFrame()
        bubble.setObjectName(obj_name)
        layout = QVBoxLayout(bubble)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        # Role + timestamp header
        header = QHBoxLayout()
        header.setSpacing(8)

        role_label = QLabel(label)
        role_label.setProperty("class", "bubbleRole")
        header.addWidget(role_label)

        time_label = QLabel(datetime.now(timezone.utc).strftime("%H:%M"))
        time_label.setProperty("class", "bubbleTime")
        header.addStretch()
        header.addWidget(time_label)
        layout.addLayout(header)

        # Parse content for code blocks
        parts = _CODE_BLOCK_RE.split(text)
        if len(parts) == 1:
            # No code blocks — plain rich text
            text_label = QLabel(self._to_rich_text(text))
            text_label.setProperty("class", "bubbleText")
            text_label.setWordWrap(True)
            text_label.setTextFormat(Qt.TextFormat.RichText)
            text_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
                | Qt.TextInteractionFlag.LinksAccessibleByMouse
            )
            text_label.setOpenExternalLinks(True)
            layout.addWidget(text_label)
        else:
            # Interleaved text and code blocks
            i = 0
            while i < len(parts):
                if i + 2 < len(parts):
                    # Check if this is a code block match
                    pre_text = parts[i]
                    lang = parts[i + 1]
                    code = parts[i + 2]

                    if pre_text.strip():
                        lbl = QLabel(self._to_rich_text(pre_text))
                        lbl.setProperty("class", "bubbleText")
                        lbl.setWordWrap(True)
                        lbl.setTextFormat(Qt.TextFormat.RichText)
                        lbl.setTextInteractionFlags(
                            Qt.TextInteractionFlag.TextSelectableByMouse
                        )
                        layout.addWidget(lbl)

                    layout.addWidget(self._make_code_block(code, lang))
                    i += 3
                else:
                    if parts[i].strip():
                        lbl = QLabel(self._to_rich_text(parts[i]))
                        lbl.setProperty("class", "bubbleText")
                        lbl.setWordWrap(True)
                        lbl.setTextFormat(Qt.TextFormat.RichText)
                        lbl.setTextInteractionFlags(
                            Qt.TextInteractionFlag.TextSelectableByMouse
                        )
                        layout.addWidget(lbl)
                    i += 1

        return bubble

    @staticmethod
    def _to_rich_text(text: str) -> str:
        """Convert markdown-like formatting to HTML.

        Handles: **bold**, *italic*, `inline code`, and URLs.
        """
        # Inline code
        text = re.sub(
            r"`([^`]+)`",
            r'<code style="background: rgba(255,255,255,0.06); '
            r'padding: 2px 5px; border-radius: 3px;">\1</code>',
            text,
        )
        # Bold
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        # Italic
        text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
        # URLs
        text = re.sub(
            r"(https?://[^\s<]+)",
            r'<a href="\1" style="color: #58a6ff;">\1</a>',
            text,
        )
        # Newlines
        text = text.replace("\n", "<br>")
        return text

    @staticmethod
    def _make_code_block(code: str, lang: str = "") -> QFrame:
        """Create a styled code block with a copy button.

        Args:
            code: The source code text.
            lang: Optional language label.

        Returns:
            A QFrame containing the code display and copy button.
        """
        frame = QFrame()
        frame.setObjectName("codeBlock")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header with language label and copy button
        header = QHBoxLayout()
        header.setContentsMargins(12, 6, 6, 0)
        if lang:
            lang_label = QLabel(lang)
            lang_label.setProperty("class", "bubbleTime")
            header.addWidget(lang_label)
        header.addStretch()

        copy_btn = QPushButton("Copy")
        copy_btn.setObjectName("copyBtn")
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.clicked.connect(
            lambda: ChatWidget._copy_code(code, copy_btn)
        )
        header.addWidget(copy_btn)
        layout.addLayout(header)

        # Code content
        editor = QTextEdit()
        editor.setObjectName("codeContent")
        editor.setPlainText(code.strip())
        editor.setReadOnly(True)
        # Auto-height based on line count
        lines = code.strip().count("\n") + 1
        editor.setFixedHeight(min(max(lines * 20 + 16, 48), 300))
        layout.addWidget(editor)

        return frame

    @staticmethod
    def _copy_code(code: str, btn: QPushButton) -> None:
        """Copy code to clipboard and show feedback."""
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(code.strip())
        btn.setText("Copied!")
        QTimer.singleShot(2000, lambda: btn.setText("Copy"))

    # ── Animation helper ─────────────────────────────────────

    @staticmethod
    def _animate_fade_in(widget: QWidget) -> None:
        """Apply a fade-in animation to a widget."""
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", widget)
        anim.setDuration(250)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    # ── Public slots ─────────────────────────────────────────

    @Slot(str, str)
    def append_message(self, role: str, text: str) -> None:
        """Append a message bubble with fade-in animation.

        Args:
            role: One of 'user', 'assistant', 'error', 'system'.
            text: Message body.
        """
        bubble = self._make_bubble(role, text)
        count = self._history_layout.count()
        self._history_layout.insertWidget(count - 1, bubble)
        self._animate_fade_in(bubble)
        QTimer.singleShot(10, self._scroll_to_bottom)

    def add_widget(self, widget: QWidget) -> None:
        """Add an arbitrary widget (e.g. task cards) to the chat flow.

        Args:
            widget: Widget to insert into the history.
        """
        count = self._history_layout.count()
        self._history_layout.insertWidget(count - 1, widget)
        self._animate_fade_in(widget)
        QTimer.singleShot(10, self._scroll_to_bottom)

    @Slot()
    def clear_messages(self) -> None:
        """Remove all message bubbles from history."""
        while self._history_layout.count() > 1:
            item = self._history_layout.takeAt(0)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

    # ── Internal ─────────────────────────────────────────────

    def _scroll_to_bottom(self) -> None:
        vbar = self._scroll.verticalScrollBar()
        vbar.setValue(vbar.maximum())
