from .mission import Mission


class ProgressTracker:
    def completion_rate(self, mission: Mission) -> float:
        if not mission.steps:
            return 0.0
        return len(mission.completed_steps) / len(mission.steps)
