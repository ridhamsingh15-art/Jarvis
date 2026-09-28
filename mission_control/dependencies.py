from .mission import Mission


class DependencyGraph:
    def is_blocked(self, mission: Mission, active_missions: dict[str, Mission]) -> bool:
        for dep in mission.dependencies:
            dep_mission = active_missions.get(dep)
            if dep_mission and dep_mission.state != "COMPLETED":
                return True
        return False
