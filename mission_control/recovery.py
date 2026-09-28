from .checkpoint import CheckpointEngine
from .mission import Mission, MissionState


class RecoverySystem:
    def __init__(self, checkpoints: CheckpointEngine):
        self.checkpoints = checkpoints

    def recover(self, mission: Mission) -> None:
        data = self.checkpoints.load(mission.id)
        if data:
            mission.state = MissionState(data["state"])
            mission.completed_steps = data["completed"]
            
        if mission.state in (MissionState.RUNNING, MissionState.PAUSED, MissionState.RECOVERING):
            mission.state = MissionState.RUNNING
