import logging
import uuid
from typing import Any

from core.models.primitives import Identifier
from core.reasoning.execution_plan import ExecutionPlan

from .dispatcher import TaskDispatcher
from .exceptions import TaskDelegationError
from .interfaces import IAgentRegistry, ICoordinator
from .lifecycle import AgentLifecycleAdapter
from .models import AgentResult, AgentTask, SharedContext

logger = logging.getLogger(__name__)

class MasterCoordinator(ICoordinator):
    """Determines required capabilities and delegates workloads across specialized agents."""

    def __init__(self, registry: IAgentRegistry, lifecycle: AgentLifecycleAdapter) -> None:
        self._registry = registry
        self._lifecycle = lifecycle

    async def execute_plan(self, plan: ExecutionPlan, parent_mission_id: Identifier, initial_context: SharedContext) -> list[AgentResult]:
        """Iterates through an execution plan, sequentially assigning steps to specialized agents."""
        logger.info(f"Master Coordinator executing plan with {len(plan.ordered_steps)} steps")
        results = []
        
        current_context = initial_context
        
        for step in plan.ordered_steps:
            logger.info(f"Coordinating step: {step}")
            result = await self.assign_step(step, current_context, parent_mission_id)
            results.append(result)
            
            if result.status == "FAILED":
                logger.error(f"Execution plan halted at step: {step} due to failure")
                break
                
            # Naive context propagation: merge payload into read-only data for the next agent
            new_data = dict(current_context.read_only_data)
            new_data.update(result.payload)
            current_context = SharedContext(session_id=current_context.session_id, read_only_data=new_data)
            
        return results

    async def assign_step(self, intent: str, context: SharedContext, parent_mission_id: Identifier) -> AgentResult:
        """Assigns a specific step to a matching agent sequentially."""
        required_capability = self._extract_capability(intent)
        
        agents = self._registry.get_agents_by_capability(required_capability)
        if not agents:
            raise TaskDelegationError(f"No agents found for capability: {required_capability}")
            
        selected_agent = agents[0]
        logger.info(f"Assigned '{intent}' to {selected_agent.profile.role.value}")
        
        task_id = Identifier(f"task_{uuid.uuid4().hex[:8]}")
        task = AgentTask(
            id=task_id,
            intent=intent,
            payload=context.read_only_data
        )
        
        # Start Child Mission
        child_mission = self._lifecycle.start_child_mission(task, parent_mission_id, selected_agent.profile.role.value)
        
        # Dispatch the task with retry logic
        result = await TaskDispatcher.dispatch(selected_agent, task, context)
        
        # Complete Child Mission
        self._lifecycle.complete_child_mission(child_mission, result)
        
        return result

    # Standard assign implementation for ICoordinator
    async def assign(self, intent: str, payload: dict[str, Any]) -> AgentResult:
        # Fallback for old single-task logic
        dummy_context = SharedContext(session_id=Identifier("session_0"), read_only_data=payload)
        return await self.assign_step(intent, dummy_context, Identifier("unknown_mission"))

    def _extract_capability(self, intent: str) -> str:
        intent_lower = intent.lower()
        if "plan" in intent_lower:
            return "planning"
        if "image" in intent_lower or "visual" in intent_lower:
            return "image_generation"
        if "storyboard" in intent_lower:
            return "storyboarding"
        if "script" in intent_lower or "write" in intent_lower:
            return "script_writing"
        if "code" in intent_lower:
            return "programming"
        if "anim" in intent_lower:
            return "animation"
        if "voice" in intent_lower or "audio" in intent_lower:
            return "voice_generation"
        if "edit" in intent_lower or "assembl" in intent_lower:
            return "video_assembly"
        if "publish" in intent_lower:
            return "publishing"
        if "search" in intent_lower or "research" in intent_lower:
            return "web_search"
        if "review" in intent_lower:
            return "quality_assurance"
        if "test" in intent_lower:
            return "unit_testing"
            
        return "planning" # default fallback
