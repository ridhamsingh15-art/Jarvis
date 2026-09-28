from .mission import Mission, MissionState


class MissionExecutor:
    def step(self, mission: Mission) -> None:
        if mission.state != MissionState.RUNNING:
            return
            
        uncompleted = [s for s in mission.steps if s not in mission.completed_steps]
        if not uncompleted:
            mission.state = MissionState.COMPLETED
            return
            
        # Execute one step
        current_step = uncompleted[0]
        
        # Simulate approval required for "deploy"
        if "deploy" in current_step and current_step not in mission.approved_steps:
            mission.approved_steps.append(current_step)
            mission.state = MissionState.WAITING_APPROVAL
            return
            
        mission.completed_steps.append(current_step)
        if len(mission.completed_steps) == len(mission.steps):
            mission.state = MissionState.COMPLETED
