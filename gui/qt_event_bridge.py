"""Thread-safe bridge from the core EventBus into the Qt GUI thread."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Signal


class QtEventBridge(QObject):
    """Forward EventBus events through a Qt signal instead of calling widgets.

    The EventBus invokes ``_forward`` on whichever thread publishes an event.
    Emitting a Qt signal is thread-safe; GUI receivers should connect with
    ``Qt.ConnectionType.QueuedConnection`` so their slots run on the GUI thread.
    """

    event_received = Signal(object)

    def __init__(self, event_bus: Any, parent: QObject | None = None) -> None:
        super().__init__(parent)
        if not callable(getattr(event_bus, "subscribe", None)):
            raise TypeError("event_bus must provide subscribe()")
        if not callable(getattr(event_bus, "unsubscribe", None)):
            raise TypeError("event_bus must provide unsubscribe()")
        self._event_bus = event_bus
        self._subscription_id = event_bus.subscribe("**", self._forward)
        self._closed = False

    def _forward(self, event: object) -> None:
        """Emit the event; never access a widget from the publisher thread."""
        if not self._closed:
            self.event_received.emit(event)

    def close(self) -> None:
        """Unsubscribe idempotently to avoid retaining the GUI after shutdown."""
        if self._closed:
            return
        self._closed = True
        self._event_bus.unsubscribe(self._subscription_id)
