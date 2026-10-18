from __future__ import annotations

import os
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, Qt, QThread, Slot
from PySide6.QtWidgets import QApplication

from core.events import EventBus
from core.models import Event
from gui.qt_event_bridge import QtEventBridge


class _Logger:
    def error(self, message, error):
        pass


class _Receiver(QObject):
    def __init__(self):
        super().__init__()
        self.events = []
        self.delivery_thread = None

    @Slot(object)
    def receive(self, event):
        self.events.append(event)
        self.delivery_thread = QThread.currentThread()


def _app():
    return QApplication.instance() or QApplication([])


def test_event_bus_events_are_queued_to_gui_thread():
    app = _app()
    bus = EventBus(_Logger())
    bridge = QtEventBridge(bus)
    receiver = _Receiver()
    bridge.event_received.connect(receiver.receive, Qt.ConnectionType.QueuedConnection)

    publisher = threading.Thread(
        target=lambda: bus.publish(Event(topic="runtime.progress", payload={"step": 1}, source="test"))
    )
    publisher.start()
    publisher.join(timeout=2)
    assert not publisher.is_alive()

    app.processEvents()
    assert len(receiver.events) == 1
    assert receiver.events[0].topic == "runtime.progress"
    assert receiver.delivery_thread == app.thread()

    bridge.close()
    bridge.close()
    bus.publish(Event(topic="runtime.progress", payload={"step": 2}, source="test"))
    app.processEvents()
    assert len(receiver.events) == 1
