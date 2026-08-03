import json
import time

from .workspace import WorkspaceState


class SnapshotManager:
    def __init__(self) -> None:
        self.snapshots: dict[str, str] = {}

    def create(self, state: WorkspaceState) -> str:
        snap_id = f"snap_{int(time.time() * 1000)}"
        self.snapshots[snap_id] = json.dumps(state.to_dict())
        return snap_id
        
    def load(self, snap_id: str) -> dict | None:
        data = self.snapshots.get(snap_id)
        if not data:
            return None
        return json.loads(data)
