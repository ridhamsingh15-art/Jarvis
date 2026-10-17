from .mission import Mission, MissionState


class ApprovalManager:
    def require_approval(self, mission: Mission, reason: str) -> None:
        if reason not in mission.pending_approvals:
            mission.pending_approvals.append(reason)
        mission.state = MissionState.WAITING_APPROVAL

    def approve(self, mission: Mission, reason: str) -> None:
        if reason in mission.pending_approvals:
            mission.pending_approvals.remove(reason)
            if reason not in mission.approved_steps:
                mission.approved_steps.append(reason)
            if not mission.pending_approvals:
                mission.state = MissionState.RUNNING
