from .mission import Mission, MissionState


class ApprovalManager:
    def require_approval(self, mission: Mission, reason: str) -> None:
        mission.state = MissionState.WAITING_APPROVAL
        mission.pending_approvals.append(reason)

    def approve(self, mission: Mission, reason: str) -> None:
        if reason in mission.pending_approvals:
            mission.pending_approvals.remove(reason)
            if not mission.pending_approvals:
                mission.state = MissionState.RUNNING
