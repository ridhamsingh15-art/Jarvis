import logging
from core.executive.models import ExecutionStrategy, GoalType, Complexity
from providers.capabilities import Capability
from providers.provider_models import InferenceRequirements

logger = logging.getLogger(__name__)

class ModelSelection:
    """Decides the optimal inference requirements based on the execution strategy."""
    
    def apply_selection(self, strategy: ExecutionStrategy) -> InferenceRequirements:
        """Determines capabilities and complexity requirements."""
        
        caps = set()
        
        # Determine base capability
        if strategy.goal == GoalType.CODING:
            caps.add(Capability.CODING)
        elif strategy.goal == GoalType.CREATIVE:
            caps.add(Capability.CHAT) # or creative if it existed
        elif strategy.goal in (GoalType.RESEARCH, GoalType.LONG_RUNNING_PROJECT):
            caps.add(Capability.REASONING)
        else:
            caps.add(Capability.CHAT)
            
        # Determine required task complexity for the router
        task_complexity_score = 1
        if strategy.complexity == Complexity.VERY_COMPLEX:
            task_complexity_score = 9
        elif strategy.complexity == Complexity.COMPLEX:
            task_complexity_score = 7
        elif strategy.complexity == Complexity.MEDIUM:
            task_complexity_score = 5
        else:
            task_complexity_score = 3
            
        reqs = InferenceRequirements(
            capabilities=frozenset(caps),
            task_complexity=task_complexity_score,
            prefer_local=True if task_complexity_score < 7 else False
        )
        
        return reqs
