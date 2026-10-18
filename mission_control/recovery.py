from .checkpoint import CheckpointEngine
from .mission import Mission, MissionState, normalize_step_indexes


class RecoverySystem:
    def __init__(self, checkpoints: CheckpointEngine):
        self.checkpoints = checkpoints

    def recover(self, mission: Mission) -> None:
        data = self.checkpoints.load(mission.id)
        if data:
            mission.state = MissionState(data["state"])
            mission.completed_steps = data["completed"]
            mission.pending_approvals = data.get("pending_approvals", [])
            mission.approved_steps = data.get("approved_steps", [])
            mission.pending_approval_indexes = normalize_step_indexes(
                data.get("pending_approval_indexes", []), len(mission.steps)
            )
            mission.approved_step_indexes = normalize_step_indexes(
                data.get("approved_step_indexes", []), len(mission.steps)
            )
            
        if mission.state in (MissionState.RUNNING, MissionState.PAUSED, MissionState.RECOVERING):
            mission.state = MissionState.RUNNING
