from .mission import Mission, MissionState


class DependencyGraph:
    def is_blocked(self, mission: Mission, active_missions: dict[str, Mission]) -> bool:
        for dep in mission.dependencies:
            dep_mission = active_missions.get(dep)
            if dep_mission is None or dep_mission.state != MissionState.COMPLETED:
                return True
        return False
