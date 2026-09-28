import json
import threading

from .mission import Mission


class CheckpointEngine:
    def __init__(self) -> None:
        self.storage: dict[str, str] = {}
        self._lock = threading.RLock()

    def checkpoint(self, mission: Mission) -> None:
        with self._lock:
            # We mock full workspace serialization here
            self.storage[mission.id] = json.dumps({
                "state": mission.state.value,
                "completed": mission.completed_steps
            })

    def load(self, mission_id: str) -> dict | None:
        with self._lock:
            data = self.storage.get(mission_id)
            if data:
                return json.loads(data)
            return None
