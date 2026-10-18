from .mission import Mission, MissionState


class ApprovalManager:
    def require_approval(self, mission: Mission, reason: str) -> None:
        if reason not in mission.pending_approvals:
            mission.pending_approvals.append(reason)
        mission.state = MissionState.WAITING_APPROVAL

    def approve(self, mission: Mission, reason: str) -> None:
        # Text-only approval remains compatible for unique reasons. Duplicate step
        # occurrences must use approve_step so one approval cannot authorize all.
        matching_indexes = [
            index for index in mission.pending_approval_indexes
            if 0 <= index < len(mission.steps) and mission.steps[index] == reason
        ]
        if len(matching_indexes) > 1:
            return
        if reason in mission.pending_approvals:
            mission.pending_approvals.remove(reason)
            if reason not in mission.approved_steps:
                mission.approved_steps.append(reason)
            if matching_indexes:
                self.approve_step(mission, matching_indexes[0])
            elif not mission.pending_approvals and not mission.pending_approval_indexes:
                mission.state = MissionState.RUNNING

    def approve_step(self, mission: Mission, step_index: int) -> None:
        """Approve exactly one zero-based step occurrence."""
        if not isinstance(step_index, int) or isinstance(step_index, bool):
            return
        if not 0 <= step_index < len(mission.steps):
            return
        if step_index not in mission.pending_approval_indexes:
            return
        mission.pending_approval_indexes.remove(step_index)
        if step_index not in mission.approved_step_indexes:
            mission.approved_step_indexes.append(step_index)
        reason = mission.steps[step_index]
        other_same_text_pending = any(
            0 <= index < len(mission.steps) and mission.steps[index] == reason
            for index in mission.pending_approval_indexes
        )
        if not other_same_text_pending and reason in mission.pending_approvals:
            mission.pending_approvals.remove(reason)
        if not mission.pending_approvals and not mission.pending_approval_indexes:
            mission.state = MissionState.RUNNING
