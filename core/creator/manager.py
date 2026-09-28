import logging
import uuid
from typing import Optional, List

from core.llm import LLMClient
from core.models.primitives import Identifier
from core.mission.manager import MissionManager
from core.mission.models import Mission
from core.mission.enums import MissionPriority, MissionStatus
from core.agents.manager import AgentManager
from core.agents.models import SharedContext
from applications.content_factory.project.manager import ProjectManager

from .objective_parser import ObjectiveParser
from .dependency_graph import GraphBuilder
from .workflow import WorkflowCompiler
from .planner import CreatorPlanner
from .progress_tracker import ProgressTracker
from .recovery import RecoveryManager
from .models import ProductionState, ProgressReport
from .exceptions import ProductionExecutionError

logger = logging.getLogger(__name__)

class CreatorManager:
    """
    High-level orchestrator that transforms a user goal into a full production mission,
    utilizing the Multi-Agent Collaboration framework and Content Factory.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        project_manager: ProjectManager,
        mission_manager: MissionManager,
        agent_manager: AgentManager
    ):
        self._parser = ObjectiveParser(llm_client)
        self._graph_builder = GraphBuilder()
        self._compiler = WorkflowCompiler()
        self._planner = CreatorPlanner()
        self._recovery = RecoveryManager()
        
        self._project_manager = project_manager
        self._mission_manager = mission_manager
        self._agent_manager = agent_manager

    async def create_production(self, user_goal: str, resume_from_project_id: Optional[str] = None) -> ProgressReport:
        """
        Orchestrates the entire content creation pipeline for a given user goal.
        """
        logger.info(f"Creator Agent received goal: '{user_goal}'")
        
        # 1. Parse Objective
        objective = self._parser.parse(user_goal)
        
        # 2. Build Dependency Graph
        dag = self._graph_builder.build(objective)
        
        # 3. Compile Workflow
        workflow_sequence = self._compiler.compile(dag)
        
        # 4. Project Bundle Setup & Recovery
        if resume_from_project_id:
            logger.info(f"Resuming existing production project: {resume_from_project_id}")
            project = self._project_manager.get_project(Identifier(resume_from_project_id))
            if not project:
                raise ProductionExecutionError(f"Cannot resume. Project {resume_from_project_id} not found.")
            
            # Simulated recovery logic: mark nodes complete if project bundle has artifacts
            # Here we just naively pass, in reality we'd inspect `project.assets`
            # For simplicity, we assume recovery is passed via completed_stage_ids (stubbed)
            completed_stages: List[str] = [] 
            workflow_sequence = self._recovery.resume_from_checkpoint(workflow_sequence, completed_stages)
        else:
            logger.info("Initializing new Project Bundle...")
            project = self._project_manager.create_project(
                name=f"{objective.topic} Production",
                description=objective.raw_prompt,
                metadata={"format": objective.target_format}
            )
            
        # 5. Mission Control Setup
        mission_id = Identifier(f"mission_creator_{uuid.uuid4().hex[:8]}")
        parent_mission = Mission(
            mission_id=mission_id,
            title=f"Production: {project.name}",
            description=f"Auto-generated mission for Creator Agent. Goal: {user_goal}",
            priority=MissionPriority.HIGH,
            parent_mission_id=None
        )
        self._mission_manager._repository.save(parent_mission)
        self._mission_manager._transition_status(parent_mission, MissionStatus.RUNNING)
        
        # 6. Plan Execution
        runnable_sequence = self._recovery.filter_runnable_sequence(workflow_sequence)
        execution_plan = self._planner.create_execution_plan(runnable_sequence)
        
        # 7. Execute via Multi-Agent Collaboration
        tracker = ProgressTracker(mission_id.value, workflow_sequence)
        
        agent_context = SharedContext(
            session_id=mission_id,
            read_only_data={
                "project_id": project.id.value,
                "objective_topic": objective.topic,
                "objective_format": objective.target_format,
                "raw_goal": objective.raw_prompt
            }
        )
        
        logger.info(f"Dispatching Multi-Agent Execution Plan ({len(runnable_sequence)} stages)...")
        
        # We manually step through or just pass the whole plan to the agent manager
        # AgentManager.execute_plan takes the whole plan and executes it sequentially.
        # But to track progress per node, we need to map results back to our tracker.
        
        results = await self._agent_manager.execute_plan(execution_plan, mission_id, agent_context)
        
        # Map results back to nodes
        for node, result in zip(runnable_sequence, results):
            if result.status == "COMPLETED":
                node.state = ProductionState.COMPLETED
            else:
                node.state = ProductionState.FAILED
                node.error_message = result.metrics.get("error", "Unknown error")
                
            tracker.log_progress()
        
        # Finalize Mission
        final_report = tracker.generate_report()
        final_status = MissionStatus.COMPLETED if final_report.overall_progress_percent == 100.0 else MissionStatus.FAILED
        self._mission_manager._transition_status(parent_mission, final_status)
        
        return final_report
